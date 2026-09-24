import os
import time
from dataclasses import dataclass

from api.porter.cold_call_scripts import (
    ALREADY_HAS_FACTOR,
    BOOKING,
    COLD_CALL_PERMISSION,
    DISCLOSURE,
    EXIT,
    HAPPY_FACTOR_EXPLORE,
    NOT_INTERESTED,
    NOT_INTERESTED_CLOSE,
    OPENER,
    PITCH,
    QUALIFIER_OPENING,
    RATES,
    WARM_CLOSE,
    WRONG_NUMBER_CLOSE,
)
from api.porter.cold_call_flow import (
    ADVISOR_EXPLANATION,
    ADVISOR_OFFER,
    BOOKING_CONFIRMATION,
    CALLBACK_CONFIRMATION,
    CALLBACK_TIME_ONLY_QUESTION,
    CALLBACK_TIME_QUESTION,
    CALL_PURPOSE_ANSWER,
    CASH_FLOW_QUESTION,
    COMPANY_NAME_QUESTION,
    CONNECTION_CLOSE,
    CONTACT_NAME_QUESTION,
    CONTACT_REFERRAL_QUESTION,
    CURRENT_FACTOR_CHALLENGE_QUESTION,
    EMAIL_QUESTION,
    FACTORING_ANSWER,
    FACTOR_SATISFACTION_QUESTION,
    FEES_ANSWER,
    FUNDING_SPEED_ANSWER,
    GATEKEEPER_QUESTION,
    IDENTITY_ANSWER,
    INDUSTRY_ANSWER,
    MONTHLY_INVOICING_QUESTION,
    MONTHLY_VOLUME_UNIT_CLARIFICATION,
    MORE_INFORMATION_ANSWER,
    NO_RESPONSE_CLOSE,
    OPENING_CLARIFICATION,
    OPENING_GREETING_RESPONSE,
    PARTIAL_AMOUNT_CLARIFICATION,
    PHONE_QUESTION,
    SECOND_HELLO,
    TERMS_ANSWER,
    THIRD_HELLO,
    UNCLEAR_RETRY,
    VOICEMAIL_MESSAGE,
)
from api.porter.live_voice import (
    DEFAULT_KOKORO_MODEL_PATH,
    DEFAULT_KOKORO_VOICES_PATH,
    DEFAULT_STT_COMPUTE_TYPE,
    DEFAULT_STT_DEVICE,
    DEFAULT_STT_MODEL,
    DEFAULT_VOICE_NAME,
    PORTER_FAST_VOICE_MODE_ENV,
    PORTER_KOKORO_MODEL_PATH_ENV,
    PORTER_KOKORO_VOICES_PATH_ENV,
    PORTER_STT_COMPUTE_TYPE_ENV,
    PORTER_STT_DEVICE_ENV,
    PORTER_STT_MODEL_ENV,
    PORTER_POCKET_TTS_VOICE_ENV,
    PORTER_TTS_MODE_ENV,
    PORTER_VOICE_NAME_ENV,
    _elapsed_ms,
    _fast_voice_mode_enabled,
    _synthesize_tts_audio,
    build_default_tts_adapter,
)
from api.porter.llm import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    PORTER_OLLAMA_BASE_URL_ENV,
    PORTER_OLLAMA_MODEL_ENV,
)
from api.porter.tts import TTSAdapter


APPROVED_VOICE_SCRIPT_MAP = {
    "opener": OPENER,
    "cold_call_permission": COLD_CALL_PERMISSION,
    "pitch": PITCH,
    "qualifier_opening": QUALIFIER_OPENING,
    "already_has_factor": ALREADY_HAS_FACTOR,
    "not_interested": NOT_INTERESTED,
    "rates": RATES,
    "booking": BOOKING,
    "disclosure": DISCLOSURE,
    "exit": EXIT,
    "happy_factor_explore": HAPPY_FACTOR_EXPLORE,
    "warm_close": WARM_CLOSE,
    "not_interested_close": NOT_INTERESTED_CLOSE,
    "wrong_number_close": WRONG_NUMBER_CLOSE,
    "advisor_explanation": ADVISOR_EXPLANATION,
    "advisor_offer": ADVISOR_OFFER,
    "booking_confirmation": BOOKING_CONFIRMATION,
    "callback_confirmation": CALLBACK_CONFIRMATION,
    "callback_time_only_question": CALLBACK_TIME_ONLY_QUESTION,
    "callback_time_question": CALLBACK_TIME_QUESTION,
    "call_purpose_answer": CALL_PURPOSE_ANSWER,
    "cash_flow_question": CASH_FLOW_QUESTION,
    "company_name_question": COMPANY_NAME_QUESTION,
    "connection_close": CONNECTION_CLOSE,
    "contact_name_question": CONTACT_NAME_QUESTION,
    "contact_referral_question": CONTACT_REFERRAL_QUESTION,
    "current_factor_challenge_question": CURRENT_FACTOR_CHALLENGE_QUESTION,
    "email_question": EMAIL_QUESTION,
    "factoring_answer": FACTORING_ANSWER,
    "factor_satisfaction_question": FACTOR_SATISFACTION_QUESTION,
    "fees_answer": FEES_ANSWER,
    "funding_speed_answer": FUNDING_SPEED_ANSWER,
    "gatekeeper_question": GATEKEEPER_QUESTION,
    "identity_answer": IDENTITY_ANSWER,
    "industry_answer": INDUSTRY_ANSWER,
    "monthly_invoicing_question": MONTHLY_INVOICING_QUESTION,
    "monthly_volume_unit_clarification": MONTHLY_VOLUME_UNIT_CLARIFICATION,
    "more_information_answer": MORE_INFORMATION_ANSWER,
    "no_response_close": NO_RESPONSE_CLOSE,
    "opening_clarification": OPENING_CLARIFICATION,
    "opening_greeting_response": OPENING_GREETING_RESPONSE,
    "partial_amount_clarification": PARTIAL_AMOUNT_CLARIFICATION,
    "phone_question": PHONE_QUESTION,
    "second_hello": SECOND_HELLO,
    "terms_answer": TERMS_ANSWER,
    "third_hello": THIRD_HELLO,
    "unclear_retry": UNCLEAR_RETRY,
    "voicemail_message": VOICEMAIL_MESSAGE,
}

# These are the replies a normal cold call needs before the caller reaches discovery.
# The wider map remains available to the explicit prewarm endpoint.
STARTUP_VOICE_SCRIPT_NAMES = (
    "opener",
    "cold_call_permission",
    "pitch",
    "qualifier_opening",
    "already_has_factor",
    "not_interested",
    "rates",
    "booking",
    "disclosure",
    "exit",
    "happy_factor_explore",
    "warm_close",
    "not_interested_close",
    "wrong_number_close",
)


@dataclass(frozen=True)
class PorterRuntimeComponent:
    name: str
    provider: str
    model: str
    ready: bool
    production_recommended: bool
    details: dict[str, object]


@dataclass(frozen=True)
class PorterRuntimeReadiness:
    components: tuple[PorterRuntimeComponent, ...]
    fast_voice_mode: bool
    default_voice: str
    recommended_target_ms: int
    notes: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return all(component.ready for component in self.components)


@dataclass(frozen=True)
class PorterVoiceScriptWarmResult:
    script_name: str
    text: str
    cache_hit: bool
    elapsed_ms: float
    tts: dict[str, object]


@dataclass(frozen=True)
class PorterVoiceRuntimeWarmResult:
    voice: str
    warmed_count: int
    cache_hit_count: int
    total_elapsed_ms: float
    scripts: tuple[PorterVoiceScriptWarmResult, ...]


def inspect_porter_voice_runtime() -> PorterRuntimeReadiness:
    model_path = os.getenv(PORTER_KOKORO_MODEL_PATH_ENV) or str(DEFAULT_KOKORO_MODEL_PATH)
    voices_path = os.getenv(PORTER_KOKORO_VOICES_PATH_ENV) or str(DEFAULT_KOKORO_VOICES_PATH)
    tts_mode = (os.getenv(PORTER_TTS_MODE_ENV) or "").strip().lower()
    has_kokoro_assets = os.path.exists(model_path) and os.path.exists(voices_path)
    environment = (os.getenv("ENVIRONMENT") or "").strip().lower()
    stub_enabled = tts_mode == "stub" and environment == "test"
    if tts_mode == "pocket":
        tts_provider = "pocket-tts"
    elif tts_mode == "kokoro" or (not tts_mode and has_kokoro_assets):
        tts_provider = "kokoro"
    elif stub_enabled:
        tts_provider = "stub"
    else:
        tts_provider = "unavailable"

    components = (
        PorterRuntimeComponent(
            name="stt",
            provider="faster-whisper",
            model=os.getenv(PORTER_STT_MODEL_ENV) or DEFAULT_STT_MODEL,
            ready=True,
            production_recommended=True,
            details={
                "device": os.getenv(PORTER_STT_DEVICE_ENV) or DEFAULT_STT_DEVICE,
                "compute_type": os.getenv(PORTER_STT_COMPUTE_TYPE_ENV) or DEFAULT_STT_COMPUTE_TYPE,
                "streaming": False,
                "note": "Current path is turn audio upload, not true streaming STT.",
            },
        ),
        PorterRuntimeComponent(
            name="tts",
            provider=tts_provider,
            model=(
                "pocket-tts-v2"
                if tts_provider == "pocket-tts"
                else "kokoro-onnx"
                if tts_provider == "kokoro"
                else "stub-tone" if tts_provider == "stub" else "not-configured"
            ),
            ready=(tts_provider == "kokoro" and has_kokoro_assets)
            or tts_provider == "pocket-tts"
            or stub_enabled,
            production_recommended=(tts_provider == "kokoro" and has_kokoro_assets)
            or tts_provider == "pocket-tts",
            details={
                "model_path": model_path,
                "voices_path": voices_path,
                "model_exists": os.path.exists(model_path),
                "voices_exist": os.path.exists(voices_path),
                "cacheable_scripts": len(APPROVED_VOICE_SCRIPT_MAP),
                "voice_prompt": os.getenv(PORTER_POCKET_TTS_VOICE_ENV) or "bill_boerst"
                if tts_provider == "pocket-tts"
                else None,
            },
        ),
        PorterRuntimeComponent(
            name="llm",
            provider="deterministic-router" if _fast_voice_mode_enabled() else "ollama",
            model=(
                "porter-fast-local"
                if _fast_voice_mode_enabled()
                else os.getenv(PORTER_OLLAMA_MODEL_ENV) or DEFAULT_OLLAMA_MODEL
            ),
            ready=True,
            production_recommended=_fast_voice_mode_enabled(),
            details={
                "ollama_base_url": os.getenv(PORTER_OLLAMA_BASE_URL_ENV) or DEFAULT_OLLAMA_BASE_URL,
                "fast_voice_mode_env": os.getenv(PORTER_FAST_VOICE_MODE_ENV),
                "note": "Deterministic router is preferred for sub-500ms scripted cold-call turns.",
            },
        ),
    )

    notes = (
        "Useful Voicebox pattern adopted: explicit runtime/model readiness and cacheable local voice assets.",
        "Voicebox itself is not used as the call engine because Porter needs telephony-grade streaming and compliance control.",
        "For the 500ms goal, prewarm approved scripts and keep deterministic routing on for common cold-call turns.",
    )
    return PorterRuntimeReadiness(
        components=components,
        fast_voice_mode=_fast_voice_mode_enabled(),
        default_voice=os.getenv(PORTER_VOICE_NAME_ENV) or DEFAULT_VOICE_NAME,
        recommended_target_ms=500,
        notes=notes,
    )


async def prewarm_porter_voice_scripts(
    *,
    voice: str | None = None,
    script_names: tuple[str, ...] | None = None,
    tts_adapter: TTSAdapter | None = None,
) -> PorterVoiceRuntimeWarmResult:
    selected_voice = voice or os.getenv(PORTER_VOICE_NAME_ENV) or DEFAULT_VOICE_NAME
    names = script_names or tuple(APPROVED_VOICE_SCRIPT_MAP)
    unknown = tuple(name for name in names if name not in APPROVED_VOICE_SCRIPT_MAP)
    if unknown:
        raise ValueError(f"Unknown Porter voice script(s): {', '.join(unknown)}")

    adapter = tts_adapter or build_default_tts_adapter()
    started_at = time.perf_counter()
    results: list[PorterVoiceScriptWarmResult] = []
    for name in names:
        text = APPROVED_VOICE_SCRIPT_MAP[name]
        script_started_at = time.perf_counter()
        _, payload, _ = await _synthesize_tts_audio(
            adapter,
            text=text,
            voice=selected_voice,
            use_cache=True,
        )
        results.append(
            PorterVoiceScriptWarmResult(
                script_name=name,
                text=text,
                cache_hit=payload.get("adapter_name") == "tts-cache",
                elapsed_ms=_elapsed_ms(script_started_at),
                tts=payload,
            )
        )

    return PorterVoiceRuntimeWarmResult(
        voice=selected_voice,
        warmed_count=len(results),
        cache_hit_count=sum(1 for result in results if result.cache_hit),
        total_elapsed_ms=_elapsed_ms(started_at),
        scripts=tuple(results),
    )
