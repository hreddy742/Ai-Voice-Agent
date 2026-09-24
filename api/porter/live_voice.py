import asyncio
import base64
import hashlib
import os
import time
import wave
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import (
    PorterCallSessionModel,
    PorterLeadModel,
    PorterTranscriptTurnModel,
)
from api.porter.call_finalization import (
    finalize_porter_call,
    porter_disposition_for_intent,
)
from api.porter.cold_call_scripts import (
    ALREADY_HAS_FACTOR,
    BOOKING,
    DISCLOSURE,
    EXIT,
    NOT_INTERESTED,
    OPENER,
    PITCH,
    QUALIFIER_FOLLOW_UP,
    QUALIFIER_OPENING,
    RATES,
)
from api.porter.cold_call_flow import (
    PorterCallerIntent,
    PorterColdCallContext,
    PorterColdCallDecision,
    PorterColdCallStage,
    decide_porter_cold_call_turn,
)
from api.porter.knowledge_base import PORTER_KB_VERSION, seed_porter_knowledge_base
from api.porter.llm import (
    MockPorterLLMAdapter,
    OllamaLLMAdapter,
    PorterLLMAdapter,
    PorterLLMError,
    PorterLLMResponse,
)
from api.porter.semantic_fallback import interpret_ambiguous_turn
from api.porter.local_text_demo import (
    PROMPT_VERSION,
    _assistant_metadata,
    _capture_fields,
    _generate_agent_text,
)
from api.porter.mock_leads import load_mock_porter_leads
from api.porter.policy import PorterPolicyEngine
from api.porter.state_machine import (
    PorterConversationContext,
    PorterConversationState,
    PorterDisposition,
    PorterSalesStateMachine,
    record_porter_transcript_turn,
)
from api.porter.suppression import (
    is_porter_phone_suppressed,
    normalize_porter_phone,
    suppress_porter_phone,
)
from api.porter.stt import (
    FasterWhisperSTTAdapter,
    STTAdapter,
    STTRequest,
    STTResult,
    safe_transcribe_file,
)
from api.porter.tts import (
    KokoroTTSAdapter,
    PocketTTSAdapter,
    SafeTTSAdapter,
    StubTTSAdapter,
    TTSAdapter,
    TTSRequest,
)
from api.porter.vad import EnergyVADAdapter, VADAdapter, VADResult


PORTER_STT_MODEL_ENV = "PORTER_STT_MODEL"
PORTER_STT_DEVICE_ENV = "PORTER_STT_DEVICE"
PORTER_STT_COMPUTE_TYPE_ENV = "PORTER_STT_COMPUTE_TYPE"
PORTER_TTS_MODE_ENV = "PORTER_TTS_MODE"
PORTER_POCKET_TTS_VOICE_ENV = "PORTER_POCKET_TTS_VOICE"
PORTER_POCKET_TTS_LANGUAGE_ENV = "PORTER_POCKET_TTS_LANGUAGE"
PORTER_FAST_VOICE_MODE_ENV = "PORTER_FAST_VOICE_MODE"
PORTER_KOKORO_MODEL_PATH_ENV = "PORTER_KOKORO_MODEL_PATH"
PORTER_KOKORO_VOICES_PATH_ENV = "PORTER_KOKORO_VOICES_PATH"
PORTER_VOICE_NAME_ENV = "PORTER_VOICE_NAME"

DEFAULT_STT_MODEL = "base.en"
DEFAULT_STT_DEVICE = "cpu"
DEFAULT_STT_COMPUTE_TYPE = "int8"
DEFAULT_VOICE_NAME = "af_heart"
DEFAULT_LOCAL_MODEL_DIR = Path(__file__).resolve().parents[1] / ".local_models" / "porter"
DEFAULT_KOKORO_MODEL_PATH = DEFAULT_LOCAL_MODEL_DIR / "kokoro-v1.0.int8.onnx"
DEFAULT_KOKORO_VOICES_PATH = DEFAULT_LOCAL_MODEL_DIR / "voices-v1.0.bin"
DEFAULT_TTS_CACHE_DIR = DEFAULT_LOCAL_MODEL_DIR / "tts-cache"
_DEFAULT_STT_ADAPTER: STTAdapter | None = None
_DEFAULT_TTS_ADAPTER: TTSAdapter | None = None
_DEFAULT_LLM_ADAPTER: PorterLLMAdapter | None = None


class PorterLiveVoiceError(RuntimeError):
    pass


class PorterLiveVoiceNoSpeechError(PorterLiveVoiceError):
    pass


@dataclass(frozen=True)
class PorterLiveVoiceTurnResult:
    call_session_id: int
    lead_id: int
    attempt_id: str
    destination_phone: str
    user_text: str
    assistant_text: str
    assistant_audio_base64: str
    assistant_audio_content_type: str
    audio_streamed: bool
    vad: dict[str, object]
    stt: dict[str, object]
    tts: dict[str, object]
    llm: dict[str, object]
    timings_ms: dict[str, float]
    transcript: tuple[dict[str, object], ...]
    should_close: bool


@dataclass(frozen=True)
class PorterVoiceOpenerResult:
    call_session_id: int
    lead_id: int
    attempt_id: str
    destination_phone: str
    assistant_text: str
    assistant_audio_base64: str
    assistant_audio_content_type: str
    tts: dict[str, object]
    transcript: tuple[dict[str, object], ...]


async def run_porter_voice_opener(
    session: AsyncSession,
    *,
    lead_id: int | None = None,
    destination_phone: str | None = None,
    tts_adapter: TTSAdapter | None = None,
    voice: str | None = None,
) -> PorterVoiceOpenerResult:
    if tts_adapter is None:
        await _prewarm_default_tts_model()
    call_session = await _get_or_create_live_call_session(
        session,
        call_session_id=None,
        lead_id=lead_id,
        destination_phone=destination_phone,
    )
    lead = await session.get(PorterLeadModel, call_session.lead_id)
    if lead is None:
        raise PorterLiveVoiceError(f"Porter lead {call_session.lead_id} was not found.")
    cold_call_context = PorterColdCallContext(
        stage=PorterColdCallStage.CONNECTION_CHECK,
        awaiting_field="connection",
        last_agent_act="connection_check",
        lead_name=lead.contact_name,
        lead_company=lead.company_name,
    )
    should_use_tts_cache = tts_adapter is None
    adapter = SafeTTSAdapter(tts_adapter or build_default_tts_adapter())
    voice_name = voice or os.getenv(PORTER_VOICE_NAME_ENV) or DEFAULT_VOICE_NAME
    audio_bytes, tts_payload, _ = await _synthesize_tts_audio(
        adapter, text=OPENER, voice=voice_name, use_cache=should_use_tts_cache
    )
    await record_porter_transcript_turn(
        session,
        call_session_id=call_session.id,
        speaker="assistant",
        text=OPENER,
        state=PorterColdCallStage.CONNECTION_CHECK,
        raw_metadata={
            "source": "cold_call_opener",
            "scripted": True,
            "cold_call_context": cold_call_context.to_metadata(),
        },
    )
    await session.flush()
    return PorterVoiceOpenerResult(
        call_session_id=call_session.id,
        lead_id=call_session.lead_id,
        attempt_id=call_session.attempt_id,
        destination_phone=call_session.destination_phone,
        assistant_text=OPENER,
        assistant_audio_base64=base64.b64encode(audio_bytes).decode("ascii"),
        assistant_audio_content_type="audio/wav",
        tts=tts_payload,
        transcript=await _load_transcript(session, call_session.id),
    )


async def run_porter_live_voice_turn(
    session: AsyncSession,
    *,
    audio_path: Path | None = None,
    call_session_id: int | None = None,
    lead_id: int | None = None,
    destination_phone: str | None = None,
    llm_adapter: PorterLLMAdapter | None = None,
    stt_adapter: STTAdapter | None = None,
    tts_adapter: TTSAdapter | None = None,
    vad_adapter: VADAdapter | None = None,
    voice: str | None = None,
    user_text_override: str | None = None,
    event_source: str = "browser_microphone",
    on_tts_audio_chunk: Callable[[bytes, int], Awaitable[None]] | None = None,
) -> PorterLiveVoiceTurnResult:
    started_at = time.perf_counter()
    timings: dict[str, float] = {}
    policy_engine = PorterPolicyEngine()
    if user_text_override is not None:
        vad_result = VADResult(
            speech_segments=(),
            sample_rate=16_000,
            duration_seconds=0.0,
            adapter_name="conversation-event",
        )
        stt_result = STTResult(
            text=user_text_override,
            confidence=None,
            language="en",
            duration_seconds=0.0,
            adapter_name="conversation-event",
            metadata={"event_source": event_source},
        )
        timings["vad"] = 0.0
        timings["stt"] = 0.0
    else:
        if audio_path is None or not audio_path.exists() or audio_path.stat().st_size == 0:
            raise PorterLiveVoiceError("Uploaded audio is empty.")
        vad_adapter = vad_adapter or EnergyVADAdapter()
        vad_started_at = time.perf_counter()
        vad_result = await vad_adapter.detect_speech(audio_path)
        timings["vad"] = _elapsed_ms(vad_started_at)
        if not vad_result.has_speech:
            raise PorterLiveVoiceNoSpeechError("No speech was detected in the uploaded audio.")

        stt_adapter = stt_adapter or build_default_stt_adapter()
        stt_started_at = time.perf_counter()
        stt_result = await safe_transcribe_file(
            stt_adapter,
            STTRequest(audio_path=audio_path),
        )
        timings["stt"] = _elapsed_ms(stt_started_at)
        if stt_result.failed:
            error_text = (stt_result.error or "").lower()
            if "empty text" in error_text or "cannot be empty" in error_text:
                raise PorterLiveVoiceNoSpeechError("No usable speech was transcribed.")
            raise PorterLiveVoiceError(stt_result.error or "Speech transcription failed.")
        if not stt_result.text.strip():
            raise PorterLiveVoiceNoSpeechError("Speech transcription returned no text.")

    db_started_at = time.perf_counter()
    call_session = await _get_or_create_live_call_session(
        session,
        call_session_id=call_session_id,
        lead_id=lead_id,
        destination_phone=destination_phone,
    )
    lead = await session.get(PorterLeadModel, call_session.lead_id)
    if lead is None:
        raise PorterLiveVoiceError(f"Porter lead {call_session.lead_id} was not found.")

    use_fast_voice = _fast_voice_mode_enabled() and llm_adapter is None
    context = PorterConversationContext()

    cold_call_context: PorterColdCallContext | None = None
    cold_call_decision: PorterColdCallDecision | None = None
    closing_disposition: PorterDisposition | None = None
    if use_fast_voice:
        cold_call_context = await _cold_call_context_from_existing_turns(
            session, call_session.id
        )
        user_state = cold_call_context.stage
        cold_call_decision = decide_porter_cold_call_turn(
            cold_call_context, stt_result.text
        )
        if cold_call_decision.intent == PorterCallerIntent.UNCLEAR:
            try:
                interpretation = await interpret_ambiguous_turn(
                    user_text=stt_result.text,
                    stage=cold_call_context.stage,
                )
            except PorterLLMError:
                interpretation = None
            if interpretation is not None:
                cold_call_decision = decide_porter_cold_call_turn(
                    cold_call_context,
                    interpretation.canonical_utterance,
                )
        cold_call_decision.apply(cold_call_context)
        if cold_call_decision.should_close:
            closing_disposition = porter_disposition_for_intent(
                current=PorterDisposition.UNKNOWN,
                intent=cold_call_decision.intent,
                context=cold_call_context,
            )
        captured_fields = dict(cold_call_context.captured_fields)
    else:
        context = await _context_from_existing_turns(session, call_session.id)
        user_state = context.state
        _capture_fields(context, stt_result.text)
        captured_fields = dict(context.captured_fields)
    timings["db_context"] = _elapsed_ms(db_started_at)

    await record_porter_transcript_turn(
        session,
        call_session_id=call_session.id,
        speaker="user",
        text=stt_result.text,
        state=user_state,
        raw_metadata={
            "source": event_source,
            "stt": _stt_metadata(stt_result),
            "vad": _vad_metadata(vad_result),
            "captured_fields": captured_fields,
            **(
                {
                    "classified_intent": cold_call_decision.intent.value,
                    "captured_updates": dict(cold_call_decision.captured_updates),
                }
                if cold_call_decision is not None
                else {}
            ),
        },
    )

    llm_started_at = time.perf_counter()
    if cold_call_decision is not None:
        response = _response_from_cold_call_decision(
            policy_engine=policy_engine,
            decision=cold_call_decision,
        )
    else:
        llm_adapter = llm_adapter or build_default_llm_adapter(policy_engine=policy_engine)
        try:
            response = await _generate_agent_text(
                session,
                llm_adapter=llm_adapter,
                lead=lead,
                state=context.state,
                user_text=stt_result.text,
            )
        except PorterLLMError as exc:
            raise PorterLiveVoiceError(f"Local LLM failed during voice turn: {exc}") from exc
    timings["llm"] = _elapsed_ms(llm_started_at)
    await policy_engine.log_violations(
        session,
        call_session_id=call_session.id,
        result=response.policy_result,
    )

    if cold_call_decision is not None and cold_call_context is not None:
        assistant_text = response.safe_text
        assistant_state = cold_call_context.stage
        transition_reason = cold_call_decision.intent.value
        human_handoff_required = False
        assistant_context_metadata = {
            "cold_call_context": cold_call_context.to_metadata(),
            "should_close": cold_call_decision.should_close,
        }
    else:
        transition = PorterSalesStateMachine(policy_engine=policy_engine).transition(
            context,
            stt_result.text,
            agent_draft=response.raw_text,
        )
        assistant_text = transition.policy_safe_text or response.safe_text
        assistant_state = transition.next_state
        transition_reason = transition.reason
        human_handoff_required = transition.human_handoff_required
        assistant_context_metadata = {}
        if transition.is_terminal:
            closing_disposition = transition.disposition or PorterDisposition.UNKNOWN

    if (
        cold_call_decision is not None
        and cold_call_decision.intent == PorterCallerIntent.STOP
    ):
        await suppress_porter_phone(
            session,
            lead=lead,
            call_session_id=call_session.id,
        )
        # A compliance opt-out must survive later TTS or response failures.
        await session.commit()
        await session.refresh(lead)
        await session.refresh(call_session)

    should_use_tts_cache = tts_adapter is None
    tts_adapter = SafeTTSAdapter(tts_adapter or build_default_tts_adapter())
    voice_name = voice or os.getenv(PORTER_VOICE_NAME_ENV) or DEFAULT_VOICE_NAME
    tts_started_at = time.perf_counter()
    audio_bytes, tts_payload, audio_streamed = await _synthesize_tts_audio(
        tts_adapter,
        text=assistant_text,
        voice=voice_name,
        use_cache=should_use_tts_cache,
        on_chunk=on_tts_audio_chunk,
    )
    timings["tts"] = _elapsed_ms(tts_started_at)
    timings["audio_ready"] = _elapsed_ms(started_at)

    await record_porter_transcript_turn(
        session,
        call_session_id=call_session.id,
        speaker="assistant",
        text=assistant_text,
        state=assistant_state,
        raw_metadata={
            **_assistant_metadata(response, approved_text=assistant_text),
            "transition_reason": transition_reason,
            "source": "live_voice_turn",
            **assistant_context_metadata,
        },
    )

    if closing_disposition is not None:
        await finalize_porter_call(
            session,
            call_session_id=call_session.id,
            context=cold_call_context,
            disposition=closing_disposition,
            completion_reason="natural_conversation_close",
        )
    else:
        call_session.status = "in_progress"
    call_session.human_review_required = (
        bool(call_session.human_review_required) or human_handoff_required
    )
    call_session.updated_at = datetime.now(UTC)

    persist_started_at = time.perf_counter()
    await session.flush()
    transcript = await _load_transcript(session, call_session.id)
    timings["persist"] = _elapsed_ms(persist_started_at)
    timings["total"] = _elapsed_ms(started_at)
    return PorterLiveVoiceTurnResult(
        call_session_id=call_session.id,
        lead_id=lead.id,
        attempt_id=call_session.attempt_id,
        destination_phone=call_session.destination_phone,
        user_text=stt_result.text,
        assistant_text=assistant_text,
        assistant_audio_base64=base64.b64encode(audio_bytes).decode("ascii"),
        assistant_audio_content_type="audio/wav",
        audio_streamed=audio_streamed,
        vad=_vad_metadata(vad_result),
        stt=_stt_metadata(stt_result),
        tts={
            **tts_payload,
        },
        llm={
            "model": response.model,
            "allowed": response.allowed,
            "policy_violation_count": len(response.policy_result.violations),
        },
        timings_ms=timings,
        transcript=transcript,
        should_close=closing_disposition is not None,
    )


def build_default_stt_adapter() -> STTAdapter:
    global _DEFAULT_STT_ADAPTER
    if _DEFAULT_STT_ADAPTER is not None:
        return _DEFAULT_STT_ADAPTER
    _DEFAULT_STT_ADAPTER = FasterWhisperSTTAdapter(
        model_name=os.getenv(PORTER_STT_MODEL_ENV) or DEFAULT_STT_MODEL,
        device=os.getenv(PORTER_STT_DEVICE_ENV) or DEFAULT_STT_DEVICE,
        compute_type=os.getenv(PORTER_STT_COMPUTE_TYPE_ENV) or DEFAULT_STT_COMPUTE_TYPE,
    )
    return _DEFAULT_STT_ADAPTER


def reset_default_voice_adapters_for_tests() -> None:
    global _DEFAULT_STT_ADAPTER, _DEFAULT_TTS_ADAPTER, _DEFAULT_LLM_ADAPTER
    _DEFAULT_STT_ADAPTER = None
    _DEFAULT_TTS_ADAPTER = None
    _DEFAULT_LLM_ADAPTER = None


def build_default_llm_adapter(
    *,
    policy_engine: PorterPolicyEngine | None = None,
) -> PorterLLMAdapter:
    global _DEFAULT_LLM_ADAPTER
    if _DEFAULT_LLM_ADAPTER is None:
        _DEFAULT_LLM_ADAPTER = OllamaLLMAdapter(policy_engine=policy_engine)
    return _DEFAULT_LLM_ADAPTER


def build_default_tts_adapter() -> TTSAdapter:
    global _DEFAULT_TTS_ADAPTER
    if _DEFAULT_TTS_ADAPTER is not None:
        return _DEFAULT_TTS_ADAPTER
    _DEFAULT_TTS_ADAPTER = _build_default_tts_adapter()
    return _DEFAULT_TTS_ADAPTER


async def _prewarm_default_tts_model() -> None:
    tts_adapter = build_default_tts_adapter()
    if isinstance(tts_adapter, (KokoroTTSAdapter, PocketTTSAdapter)):
        await asyncio.to_thread(tts_adapter.prewarm)


async def prewarm_default_stt_model() -> None:
    stt_adapter = build_default_stt_adapter()
    if isinstance(stt_adapter, FasterWhisperSTTAdapter):
        await asyncio.to_thread(stt_adapter.prewarm)


def _build_default_tts_adapter() -> TTSAdapter:
    mode = (os.getenv(PORTER_TTS_MODE_ENV) or "").strip().lower()
    environment = (os.getenv("ENVIRONMENT") or "").strip().lower()
    model_path = os.getenv(PORTER_KOKORO_MODEL_PATH_ENV) or (
        str(DEFAULT_KOKORO_MODEL_PATH) if DEFAULT_KOKORO_MODEL_PATH.exists() else None
    )
    voices_path = os.getenv(PORTER_KOKORO_VOICES_PATH_ENV) or (
        str(DEFAULT_KOKORO_VOICES_PATH) if DEFAULT_KOKORO_VOICES_PATH.exists() else None
    )
    if mode == "stub":
        if environment != "test":
            raise PorterLiveVoiceError(
                "Stub TTS is allowed only in an explicit test environment."
            )
        return StubTTSAdapter()
    if mode == "pocket":
        return PocketTTSAdapter(
            voice_prompt=os.getenv(PORTER_POCKET_TTS_VOICE_ENV) or "bill_boerst",
            language=os.getenv(PORTER_POCKET_TTS_LANGUAGE_ENV) or None,
        )
    if mode not in {"", "kokoro"}:
        raise PorterLiveVoiceError(f"Unsupported Porter TTS mode: {mode}")
    if mode == "kokoro" or (model_path and voices_path):
        if not model_path or not voices_path:
            raise PorterLiveVoiceError(
                "Kokoro TTS requires PORTER_KOKORO_MODEL_PATH and "
                "PORTER_KOKORO_VOICES_PATH."
            )
        return KokoroTTSAdapter(
            model_path=Path(model_path),
            voices_path=Path(voices_path),
        )
    raise PorterLiveVoiceError(
        "Porter voice requires Kokoro model and voice assets. Set explicit "
        "PORTER_TTS_MODE=stub only for automated tests."
    )


def _elapsed_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 2)


def _fast_voice_mode_enabled() -> bool:
    return (os.getenv(PORTER_FAST_VOICE_MODE_ENV) or "true").strip().lower() not in {
        "0",
        "false",
        "no",
    }


def _response_from_cold_call_decision(
    *,
    policy_engine: PorterPolicyEngine,
    decision: PorterColdCallDecision,
) -> PorterLLMResponse:
    policy_result = policy_engine.check_response(decision.response_text)
    return PorterLLMResponse(
        raw_text=decision.response_text,
        safe_text=policy_result.safe_text,
        allowed=policy_result.allowed,
        model="porter-cold-call-flow-v1",
        policy_result=policy_result,
        raw_response={
            "model": "porter-cold-call-flow-v1",
            "message": {"content": decision.response_text},
            "intent": decision.intent.value,
            "next_stage": decision.next_stage.value,
        },
    )


def _build_fast_voice_response(
    *,
    policy_engine: PorterPolicyEngine,
    user_text: str,
    state: PorterConversationState = PorterConversationState.OPENING,
) -> PorterLLMResponse:
    lowered = user_text.lower()
    normalized = " ".join(
        "".join(character if character.isalnum() else " " for character in lowered).split()
    )
    tokens = set(normalized.split())
    if any(phrase in lowered for phrase in ("are you ai", "are you an ai", "robot", "real person")):
        text = DISCLOSURE
    elif any(phrase in lowered for phrase in ("rate", "rates", "pricing", "cost")):
        text = RATES
    elif (
        any(phrase in lowered for phrase in ("already have a factor", "current factor", "we factor"))
        and not normalized.startswith(("no current factor", "no factor", "we do not factor", "we dont factor"))
    ):
        text = ALREADY_HAS_FACTOR
    elif any(phrase in lowered for phrase in ("stop calling", "remove me", "do not call", "hang up")):
        text = EXIT
    elif any(phrase in lowered for phrase in ("not interested", "no thanks", "we are good")):
        text = NOT_INTERESTED
    elif any(phrase in lowered for phrase in ("who are you", "who is this")):
        text = "Yeah — I'm Aiva, an AI agent with Porter Capital."
    elif normalized in {"hello", "hi", "hey"}:
        text = "Hey — can you hear me okay?"
    elif normalized in {"i want you", "want you"}:
        text = "Yeah — what did you want to ask me?"
    elif state == PorterConversationState.PERMISSION_CHECK and any(
        phrase in lowered for phrase in ("yes", "yeah", "sure", "go ahead", "sounds good")
    ):
        text = QUALIFIER_OPENING
    elif any(phrase in lowered for phrase in ("yes", "30 seconds", "go ahead", "what is this about")):
        text = PITCH
    elif any(phrase in lowered for phrase in ("worth a chat", "sounds good")):
        text = QUALIFIER_OPENING
    elif any(phrase in lowered for phrase in ("talk to someone", "advisor", "book", "set that up")):
        text = BOOKING
    elif any(
        phrase in lowered
        for phrase in (
            "know more",
            "tell me more",
            "more about",
            "what do you do",
            "what is porter",
        )
    ):
        text = "Yeah, Porter helps B2B businesses turn unpaid invoices into working capital."
    elif any(phrase in lowered for phrase in ("fee", "fees")):
        text = "Yeah, fees depend on how the program is structured."
    elif (
        any(phrase in lowered for phrase in ("how fast", "how soon", "how long", "funding speed", "24", "48"))
        or ("funding" in tokens and bool(tokens & {"take", "time", "when", "long", "soon", "fast"}))
    ):
        text = "Yeah, once you're set up with Porter, funding is usually under 48 hours after you submit an invoice."
    elif any(phrase in lowered for phrase in ("construction", "trucking", "industry", "eligible", "qualify")):
        text = "Yeah, that depends on the details — one of our financing advisors can look at it with you."
    elif any(phrase in lowered for phrase in ("selective", "full factoring", "contract", "terms")):
        text = "Yeah, that depends on your setup — one of our financing advisors can dig into it with you."
    elif any(phrase in lowered for phrase in ("call me later", "call back", "tomorrow")):
        text = "Got it. I can mark this for a callback."
    elif any(
        phrase in lowered
        for phrase in ("what do you mean", "mean by what part", "mean by 'what part'", "what part do you mean")
    ):
        text = "Yeah \N{EM DASH} I mean how invoice factoring could help your business."
    elif any(
        phrase in lowered
        for phrase in (
            "how does it work",
            "how factoring works",
            "what is factoring",
            "invoice factoring",
            "unpaid invoice",
            "unpaid invoices",
            "working capital",
        )
    ) or (
        bool(tokens & {"factor", "factoring"})
        and not normalized.startswith(
            (
                "we factor",
                "already have a factor",
                "current factor",
                "no current factor",
                "no factor",
                "we do not factor",
                "we dont factor",
            )
        )
    ):
        text = "So, it helps B2B businesses turn unpaid invoices into working capital."
    elif any(
        phrase in lowered
        for phrase in (
            "who do you serve",
            "what businesses",
            "what companies",
            "b2b",
            "government clients",
        )
    ):
        text = "Yeah, Porter works with B2B companies that invoice businesses or government clients."
    elif any(
        phrase in lowered
        for phrase in (
            "why porter",
            "different",
            "better",
            "experience",
            "service",
            "dedicated",
        )
    ):
        text = "Yeah, Porter has been doing this for decades and is big on dedicated service."
    elif any(
        phrase in lowered
        for phrase in (
            "interested",
            "next step",
            "sign up",
            "talk to someone",
            "advisor",
            "follow up",
        )
    ):
        text = "Got it — I can get one of our financing advisors to follow up."
    elif any(phrase in lowered for phrase in ("cash flow", "challenge", "payroll", "waiting to get paid")):
        text = "Right, cash flow timing is exactly the kind of thing Porter tries to understand first."
    elif any(phrase in lowered for phrase in ("name", "email", "phone", "best time", "monthly invoicing", "volume")):
        text = "Got it — those details help a financing advisor follow up the right way."
    elif state == PorterConversationState.REASON_FOR_CALL:
        text = QUALIFIER_FOLLOW_UP.format(
            natural_reaction="that helps"
        )
    else:
        text = "Sure — what part are you trying to figure out first?"
    policy_result = policy_engine.check_response(text)
    return PorterLLMResponse(
        raw_text=text,
        safe_text=policy_result.safe_text,
        allowed=policy_result.allowed,
        model="porter-fast-local",
        policy_result=policy_result,
        raw_response={"model": "porter-fast-local", "message": {"content": text}},
    )


async def _synthesize_tts_audio(
    adapter: TTSAdapter,
    *,
    text: str,
    voice: str,
    use_cache: bool,
    on_chunk: Callable[[bytes, int], Awaitable[None]] | None = None,
) -> tuple[bytes, dict[str, object], bool]:
    cache_path = _tts_cache_path(text=text, voice=voice, adapter=adapter)
    if use_cache and cache_path.exists():
        return cache_path.read_bytes(), {
            "adapter_name": "tts-cache",
            "voice": voice,
            "duration_seconds": _wav_duration_seconds(cache_path),
            "sample_rate": None,
            "metadata": {"cache_path": str(cache_path)},
        }, False

    with TemporaryDirectory(prefix="porter-live-voice-") as temp_dir:
        output_path = Path(temp_dir) / "assistant.wav"
        request = TTSRequest(
            text=text,
            output_path=output_path,
            voice=voice,
        )
        audio_streamed = bool(on_chunk is not None and adapter.supports_streaming_audio)
        if audio_streamed:
            tts_result = await adapter.synthesize_stream(request, on_chunk)
        else:
            tts_result = await adapter.synthesize(request)
        audio_bytes = output_path.read_bytes()
        if use_cache:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(audio_bytes)
        return audio_bytes, {
            "adapter_name": tts_result.adapter_name,
            "voice": tts_result.voice,
            "duration_seconds": tts_result.duration_seconds,
            "sample_rate": tts_result.sample_rate,
            "metadata": tts_result.metadata,
        }, audio_streamed


def _tts_cache_path(*, text: str, voice: str, adapter: TTSAdapter | None = None) -> Path:
    adapter_identity = adapter.cache_identity if adapter is not None else "legacy"
    digest = hashlib.sha256(
        f"{adapter_identity}\n{voice}\n{text}".encode("utf-8")
    ).hexdigest()
    return DEFAULT_TTS_CACHE_DIR / f"{digest}.wav"


def _wav_duration_seconds(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as wav_file:
            return wav_file.getnframes() / float(wav_file.getframerate())
    except wave.Error:
        return None


async def _get_or_create_live_call_session(
    session: AsyncSession,
    *,
    call_session_id: int | None,
    lead_id: int | None,
    destination_phone: str | None = None,
) -> PorterCallSessionModel:
    if call_session_id is not None:
        call_session = await session.get(PorterCallSessionModel, call_session_id)
        if call_session is None:
            raise PorterLiveVoiceError(f"Porter call session {call_session_id} was not found.")
        if lead_id is not None and lead_id != call_session.lead_id:
            raise PorterLiveVoiceError(
                f"Porter call session {call_session_id} belongs to lead "
                f"{call_session.lead_id}, not lead {lead_id}."
            )
        if (
            destination_phone is not None
            and normalize_porter_phone(destination_phone)
            != call_session.destination_phone
        ):
            raise PorterLiveVoiceError(
                f"Porter call session {call_session_id} is bound to a different "
                "destination phone number."
            )
        lead = await session.get(PorterLeadModel, call_session.lead_id)
        if lead is None:
            raise PorterLiveVoiceError(f"Porter lead {call_session.lead_id} was not found.")
        if lead.do_not_call or await is_porter_phone_suppressed(
            session, call_session.destination_phone
        ):
            raise PorterLiveVoiceError(
                f"Porter lead {lead.id} is suppressed and cannot continue a call."
            )
        if call_session.status in {"completed", "failed", "needs_review"}:
            raise PorterLiveVoiceError(
                f"Porter call session {call_session_id} is already finalized."
            )
        return call_session

    if lead_id is None:
        leads = await load_mock_porter_leads(session)
        lead_id = leads[0].id
    lead = await session.get(PorterLeadModel, lead_id)
    if lead is None:
        raise PorterLiveVoiceError(f"Porter lead {lead_id} was not found.")
    normalized_destination = normalize_porter_phone(destination_phone or lead.phone)
    if lead.do_not_call or await is_porter_phone_suppressed(
        session, normalized_destination
    ):
        raise PorterLiveVoiceError(
            f"Porter lead {lead_id} is suppressed and cannot be called."
        )

    if destination_phone is not None and normalized_destination != normalize_porter_phone(
        lead.phone
    ):
        raise PorterLiveVoiceError(
            f"Destination phone does not match Porter lead {lead.id}."
        )

    await seed_porter_knowledge_base(session)
    call_session = PorterCallSessionModel(
        lead_id=lead.id,
        destination_phone=normalized_destination,
        status="in_progress",
        started_at=datetime.now(UTC),
        prompt_version=PROMPT_VERSION,
        knowledge_base_version=PORTER_KB_VERSION,
        human_review_required=True,
        crm_sync_status="not_ready",
    )
    session.add(call_session)
    await session.flush()
    return call_session


async def _context_from_existing_turns(
    session: AsyncSession,
    call_session_id: int,
) -> PorterConversationContext:
    rows = (
        await session.execute(
            select(PorterTranscriptTurnModel)
            .where(PorterTranscriptTurnModel.call_session_id == call_session_id)
            .order_by(PorterTranscriptTurnModel.timestamp, PorterTranscriptTurnModel.id)
        )
    ).scalars().all()
    context = PorterConversationContext()
    for row in rows:
        if row.conversation_state in PorterConversationState._value2member_map_:
            context.state = PorterConversationState(row.conversation_state)
        if row.speaker == "user":
            _capture_fields(context, row.text)
    return context


async def _cold_call_context_from_existing_turns(
    session: AsyncSession,
    call_session_id: int,
) -> PorterColdCallContext:
    rows = (
        await session.execute(
            select(PorterTranscriptTurnModel)
            .where(
                PorterTranscriptTurnModel.call_session_id == call_session_id,
                PorterTranscriptTurnModel.speaker == "assistant",
            )
            .order_by(
                PorterTranscriptTurnModel.timestamp.desc(),
                PorterTranscriptTurnModel.id.desc(),
            )
            .limit(1)
        )
    ).scalars().all()
    for row in rows:
        metadata = row.raw_metadata or {}
        cold_call_metadata = metadata.get("cold_call_context")
        if isinstance(cold_call_metadata, dict):
            return PorterColdCallContext.from_metadata(cold_call_metadata)

    return PorterColdCallContext(
        stage=PorterColdCallStage.CONNECTION_CHECK,
        awaiting_field="connection",
        last_agent_act="connection_check",
    )


async def _load_transcript(
    session: AsyncSession,
    call_session_id: int,
) -> tuple[dict[str, object], ...]:
    rows = (
        await session.execute(
            select(PorterTranscriptTurnModel)
            .where(PorterTranscriptTurnModel.call_session_id == call_session_id)
            .order_by(PorterTranscriptTurnModel.timestamp, PorterTranscriptTurnModel.id)
        )
    ).scalars().all()
    return tuple(
        {
            "id": row.id,
            "speaker": row.speaker,
            "text": row.text,
            "conversation_state": row.conversation_state,
            "timestamp": row.timestamp.isoformat(),
            "raw_metadata": row.raw_metadata,
        }
        for row in rows
    )


def _vad_metadata(vad_result) -> dict[str, object]:
    return {
        "adapter_name": vad_result.adapter_name,
        "duration_seconds": vad_result.duration_seconds,
        "sample_rate": vad_result.sample_rate,
        "speech_segments": [
            {
                "start_seconds": segment.start_seconds,
                "end_seconds": segment.end_seconds,
                "confidence": segment.confidence,
            }
            for segment in vad_result.speech_segments
        ],
    }


def _stt_metadata(stt_result) -> dict[str, object]:
    return {
        "adapter_name": stt_result.adapter_name,
        "confidence": stt_result.confidence,
        "language": stt_result.language,
        "duration_seconds": stt_result.duration_seconds,
        "metadata": stt_result.metadata,
    }
