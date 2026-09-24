import math
import wave
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import UUID

from sqlalchemy import select

from api.db.models import (
    PorterCallOutcomeModel,
    PorterCallSessionModel,
    PorterLeadModel,
    PorterPhoneSuppressionModel,
    PorterQualificationAnswerModel,
    PorterTranscriptTurnModel,
)
from api.porter.cold_call_scripts import (
    ALREADY_HAS_FACTOR,
    COLD_CALL_PERMISSION,
    DISCLOSURE,
    EXIT,
    NOT_INTERESTED,
    OPENER,
    PITCH,
    QUALIFIER_FOLLOW_UP,
    QUALIFIER_OPENING,
    RATES,
    WARM_CLOSE,
)
from api.porter.cold_call_flow import NO_RESPONSE_CLOSE, THIRD_HELLO
from api.porter.live_voice import (
    build_default_stt_adapter,
    reset_default_voice_adapters_for_tests,
    run_porter_live_voice_turn,
    run_porter_voice_opener,
)
from api.porter.live_voice import (
    PorterLiveVoiceError,
    PorterLiveVoiceNoSpeechError,
    _build_fast_voice_response,
    prewarm_default_stt_model,
)
from api.porter.llm import MockPorterLLMAdapter
from api.porter.policy import PorterPolicyEngine
from api.porter.state_machine import PorterConversationState
from api.porter.stt import MockSTTAdapter
from api.porter.tts import StubTTSAdapter


def _write_test_wav(path: Path) -> None:
    sample_rate = 16_000
    duration_seconds = 0.5
    frame_count = int(sample_rate * duration_seconds)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        for index in range(frame_count):
            sample = int(32767 * 0.4 * math.sin(2 * math.pi * 440 * index / sample_rate))
            wav_file.writeframesraw(sample.to_bytes(2, byteorder="little", signed=True))


async def test_porter_live_voice_turn_records_real_audio_pipeline(tmp_path, db_session):
    audio_path = tmp_path / "caller.wav"
    _write_test_wav(audio_path)

    async with db_session.async_session() as session:
        result = await run_porter_live_voice_turn(
            session,
            audio_path=audio_path,
            stt_adapter=MockSTTAdapter("I need working capital for payroll."),
            llm_adapter=MockPorterLLMAdapter("I can help capture that for Porter review."),
            tts_adapter=StubTTSAdapter(),
        )
        await session.commit()

    assert result.call_session_id > 0
    assert result.user_text == "I need working capital for payroll."
    assert result.assistant_text
    assert result.assistant_audio_base64
    assert result.assistant_audio_content_type == "audio/wav"
    assert result.vad["speech_segments"]
    assert result.stt["adapter_name"] == "mock"
    assert result.tts["adapter_name"] == "stub"
    assert result.timings_ms["audio_ready"] > 0
    assert result.timings_ms["audio_ready"] <= result.timings_ms["total"]
    assert len(result.transcript) == 2


async def test_porter_live_voice_turn_treats_empty_stt_as_no_speech(tmp_path, db_session):
    audio_path = tmp_path / "caller.wav"
    _write_test_wav(audio_path)

    async with db_session.async_session() as session:
        try:
            await run_porter_live_voice_turn(
                session,
                audio_path=audio_path,
                stt_adapter=MockSTTAdapter(""),
                llm_adapter=MockPorterLLMAdapter("I can help capture that."),
                tts_adapter=StubTTSAdapter(),
            )
        except PorterLiveVoiceNoSpeechError as exc:
            assert "speech" in str(exc).lower()
        else:
            raise AssertionError("Expected empty STT to be treated as no speech.")


async def test_porter_live_voice_route_rejects_non_wav(test_client_factory, db_session):
    from api.tests.test_porter_local_routes import _route_test_user

    user = await _route_test_user(db_session)

    async with test_client_factory(user) as client:
        response = await client.post(
            "/api/v1/porter-local/voice-turns",
            files={"audio": ("caller.txt", b"hello", "text/plain")},
        )

    assert response.status_code == 415


async def test_porter_live_voice_route_finalizes_unexpected_failure(
    tmp_path,
    test_client_factory,
    db_session,
    monkeypatch,
):
    from api.tests.test_porter_local_routes import _route_test_user

    audio_path = tmp_path / "caller.wav"
    _write_test_wav(audio_path)
    user = await _route_test_user(db_session)
    finalizer = AsyncMock()

    async def fail_turn(*args, **kwargs):
        raise RuntimeError("synthetic voice failure")

    monkeypatch.setattr("api.routes.porter_local.run_porter_live_voice_turn", fail_turn)
    monkeypatch.setattr(
        "api.routes.porter_local._finalize_porter_voice_call",
        finalizer,
    )

    async with test_client_factory(user) as client:
        response = await client.post(
            "/api/v1/porter-local/voice-turns",
            data={"call_session_id": "42"},
            files={"audio": ("caller.wav", audio_path.read_bytes(), "audio/wav")},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "Aiva could not complete the voice turn."
    finalizer.assert_awaited_once_with(
        42,
        completion_reason="voice_turn_error",
        status="failed",
    )


async def test_porter_voice_opener_speaks_first_and_records_script(db_session):
    async with db_session.async_session() as session:
        result = await run_porter_voice_opener(
            session,
            tts_adapter=StubTTSAdapter(),
        )
        call_session = await session.get(PorterCallSessionModel, result.call_session_id)
        lead = await session.get(PorterLeadModel, result.lead_id)
        stored_identity = (
            call_session.attempt_id,
            call_session.destination_phone,
            lead.phone,
        )
        await session.commit()

    assert result.assistant_text == OPENER
    assert UUID(result.attempt_id)
    assert result.attempt_id == stored_identity[0]
    assert result.destination_phone == stored_identity[1] == stored_identity[2]
    assert result.assistant_audio_base64
    assert len(result.transcript) == 1
    assert result.transcript[0]["speaker"] == "assistant"
    assert result.transcript[0]["text"] == OPENER


async def test_porter_voice_opener_does_not_prewarm_stt(monkeypatch, tmp_path, db_session):
    def stt_should_not_load():
        raise AssertionError("The opener must not load STT before the caller speaks.")

    monkeypatch.setattr("api.porter.live_voice.build_default_stt_adapter", stt_should_not_load)
    monkeypatch.setattr(
        "api.porter.live_voice.build_default_tts_adapter", lambda: StubTTSAdapter()
    )
    monkeypatch.setattr("api.porter.live_voice.DEFAULT_TTS_CACHE_DIR", tmp_path)

    async with db_session.async_session() as session:
        result = await run_porter_voice_opener(session)

    assert result.assistant_text == OPENER


async def test_porter_stt_prewarm_is_available_after_the_opener(monkeypatch):
    class FakeSTTAdapter:
        def __init__(self):
            self.prewarmed = False

        def prewarm(self):
            self.prewarmed = True

    adapter = FakeSTTAdapter()
    monkeypatch.setattr("api.porter.live_voice.build_default_stt_adapter", lambda: adapter)
    monkeypatch.setattr("api.porter.live_voice.FasterWhisperSTTAdapter", FakeSTTAdapter)

    await prewarm_default_stt_model()

    assert adapter.prewarmed is True


def test_default_stt_adapter_uses_explicit_cuda_configuration(monkeypatch):
    monkeypatch.setenv("PORTER_STT_DEVICE", "cuda")
    monkeypatch.setenv("PORTER_STT_COMPUTE_TYPE", "float16")
    reset_default_voice_adapters_for_tests()

    adapter = build_default_stt_adapter()

    assert adapter.device == "cuda"
    assert adapter.compute_type == "float16"
    reset_default_voice_adapters_for_tests()


async def test_failed_tts_does_not_persist_unsaid_assistant_text(db_session):
    class FailingTTSAdapter(StubTTSAdapter):
        async def synthesize(self, request):
            raise RuntimeError("synthetic TTS failure")

    async with db_session.async_session() as session:
        opener = await run_porter_voice_opener(
            session,
            tts_adapter=StubTTSAdapter(),
        )
        try:
            await run_porter_live_voice_turn(
                session,
                call_session_id=opener.call_session_id,
                user_text_override="Hello",
                tts_adapter=FailingTTSAdapter(),
            )
        except RuntimeError as exc:
            assert "synthetic TTS failure" in str(exc)
        else:
            raise AssertionError("Expected synthetic TTS failure.")
        assistant_turns = (
            await session.execute(
                select(PorterTranscriptTurnModel).where(
                    PorterTranscriptTurnModel.call_session_id == opener.call_session_id,
                    PorterTranscriptTurnModel.speaker == "assistant",
                )
            )
        ).scalars().all()

    assert [turn.text for turn in assistant_turns] == [OPENER]


async def test_live_voice_turn_forwards_streamed_audio_chunks(db_session):
    class StreamingTTSAdapter(StubTTSAdapter):
        @property
        def supports_streaming_audio(self):
            return True

        async def synthesize_stream(self, request, on_chunk):
            await on_chunk(b"\x00\x00\x10\x00", 24_000)
            return await self.synthesize(request)

    received_chunks: list[tuple[bytes, int]] = []

    async def on_chunk(pcm16: bytes, sample_rate: int) -> None:
        received_chunks.append((pcm16, sample_rate))

    async with db_session.async_session() as session:
        opener = await run_porter_voice_opener(session, tts_adapter=StubTTSAdapter())
        result = await run_porter_live_voice_turn(
            session,
            call_session_id=opener.call_session_id,
            user_text_override="Yes.",
            tts_adapter=StreamingTTSAdapter(),
            on_tts_audio_chunk=on_chunk,
        )

    assert received_chunks == [(b"\x00\x00\x10\x00", 24_000)]
    assert result.audio_streamed is True
    assert result.assistant_audio_base64


async def test_policy_approved_text_is_both_returned_and_transcribed(db_session):
    async with db_session.async_session() as session:
        result = await run_porter_live_voice_turn(
            session,
            user_text_override="Can you approve me?",
            llm_adapter=MockPorterLLMAdapter("You are approved."),
            tts_adapter=StubTTSAdapter(),
        )

    assistant_turn = result.transcript[-1]
    assert result.assistant_text == assistant_turn["text"]
    assert result.assistant_text != "You are approved."
    assert assistant_turn["raw_metadata"]["policy_original_text"] == "You are approved."


async def test_live_call_rejects_conflicting_lead_or_destination(db_session):
    async with db_session.async_session() as session:
        opener = await run_porter_voice_opener(
            session,
            tts_adapter=StubTTSAdapter(),
        )

        try:
            await run_porter_live_voice_turn(
                session,
                call_session_id=opener.call_session_id,
                lead_id=opener.lead_id + 1,
                user_text_override="Hello",
                tts_adapter=StubTTSAdapter(),
            )
        except PorterLiveVoiceError as exc:
            assert "belongs to lead" in str(exc)
        else:
            raise AssertionError("Expected a conflicting lead to be rejected.")

        try:
            await run_porter_live_voice_turn(
                session,
                call_session_id=opener.call_session_id,
                destination_phone="+15550109999",
                user_text_override="Hello",
                tts_adapter=StubTTSAdapter(),
            )
        except PorterLiveVoiceError as exc:
            assert "different destination" in str(exc)
        else:
            raise AssertionError("Expected a conflicting destination to be rejected.")


async def test_live_fast_voice_persists_locked_cold_call_context(tmp_path, db_session):
    audio_path = tmp_path / "caller.wav"
    _write_test_wav(audio_path)

    async with db_session.async_session() as session:
        opener = await run_porter_voice_opener(
            session,
            tts_adapter=StubTTSAdapter(),
        )
        turns = []
        for user_text in (
            "Hello.",
            "Yes, speaking.",
            "Yes.",
            "Yes, worth a chat.",
            "IT consulting.",
            "We invoice other businesses.",
            "About 45 days.",
            "Waiting on invoices makes payroll difficult.",
            "We cover it with internal cash.",
            "Yes, connect me with an advisor.",
            "Call me at 205-555-0100 Friday morning.",
            "alex@example.com",
            "Alex Morgan",
            "Morgan Technology Group",
        ):
            turns.append(
                await run_porter_live_voice_turn(
                    session,
                    audio_path=audio_path,
                    call_session_id=opener.call_session_id,
                    stt_adapter=MockSTTAdapter(user_text),
                    tts_adapter=StubTTSAdapter(),
                )
            )
        call_session = await session.get(PorterCallSessionModel, opener.call_session_id)
        outcome = await session.scalar(
            select(PorterCallOutcomeModel).where(
                PorterCallOutcomeModel.call_session_id == opener.call_session_id
            )
        )
        qualification = await session.scalar(
            select(PorterQualificationAnswerModel).where(
                PorterQualificationAnswerModel.call_session_id == opener.call_session_id
            )
        )
        await session.commit()

    assert turns[0].assistant_text.startswith("Hey — is this ")
    assert " with " in turns[0].assistant_text
    assert turns[1].assistant_text == COLD_CALL_PERMISSION
    assert turns[2].assistant_text == PITCH
    assert "kind of business" in turns[3].assistant_text
    assert "bill other businesses" in turns[4].assistant_text
    assert "how long" in turns[5].assistant_text
    assert "main issue" in turns[6].assistant_text
    assert "factoring" in turns[7].assistant_text
    assert "funding specialist" in turns[8].assistant_text
    assert "day and time" in turns[9].assistant_text
    assert "email" in turns[10].assistant_text
    assert "full name" in turns[11].assistant_text
    assert "company" in turns[12].assistant_text
    assert turns[13].should_close is True
    assert call_session.status == "completed"
    assert call_session.ended_at is not None
    assert outcome.disposition == "interested"
    assert qualification.raw_answers["customer_type"] == "business"
    assert turns[13].transcript[-1]["conversation_state"] == "complete"
    context = turns[13].transcript[-1]["raw_metadata"]["cold_call_context"]
    assert context["captured_fields"] == {
        "industry": "IT consulting.",
        "customer_type": "business",
        "payment_timing": "About 45 days.",
        "invoice_funding_need": "yes",
        "operational_impact": "Waiting on invoices makes payroll difficult.",
        "cash_flow_challenge": "Waiting on invoices makes payroll difficult.",
        "current_financing_solution": "We cover it with internal cash.",
        "current_funding_method": "internal_cash",
        "phone": "Call me at 205-555-0100 Friday morning.",
        "best_callback_time": "Call me at 205-555-0100 Friday morning.",
        "best_callback_number_and_time": "Call me at 205-555-0100 Friday morning.",
        "email": "alex@example.com",
        "full_name": "Alex Morgan",
        "company_name": "Morgan Technology Group",
        "next_action": "advisor_callback",
    }


async def test_stop_request_persists_lead_suppression_and_blocks_new_call(
    tmp_path,
    db_session,
):
    audio_path = tmp_path / "caller.wav"
    _write_test_wav(audio_path)

    async with db_session.async_session() as session:
        opener = await run_porter_voice_opener(
            session,
            tts_adapter=StubTTSAdapter(),
        )
        await run_porter_live_voice_turn(
            session,
            audio_path=audio_path,
            call_session_id=opener.call_session_id,
            stt_adapter=MockSTTAdapter("Remove me and do not call again."),
            tts_adapter=StubTTSAdapter(),
        )
        lead = await session.get(PorterLeadModel, opener.lead_id)
        phone_suppression = await session.scalar(
            select(PorterPhoneSuppressionModel).where(
                PorterPhoneSuppressionModel.phone == opener.destination_phone
            )
        )
        try:
            await run_porter_live_voice_turn(
                session,
                call_session_id=opener.call_session_id,
                user_text_override="Hello again.",
                tts_adapter=StubTTSAdapter(),
            )
        except PorterLiveVoiceError as exc:
            same_session_error = str(exc)
        else:
            raise AssertionError("Expected a suppressed lead to block the same call.")
        await session.commit()

    assert lead.do_not_call is True
    assert lead.suppressed_at is not None
    assert lead.suppression_reason == "caller_requested_do_not_call"
    assert phone_suppression is not None
    assert phone_suppression.source_call_session_id == opener.call_session_id
    assert "suppressed" in same_session_error

    async with db_session.async_session() as session:
        lead = await session.get(PorterLeadModel, opener.lead_id)
        lead.do_not_call = False
        await session.flush()
        try:
            await run_porter_voice_opener(
                session,
                lead_id=opener.lead_id,
                tts_adapter=StubTTSAdapter(),
            )
        except PorterLiveVoiceError as exc:
            assert "suppressed" in str(exc)
        else:
            raise AssertionError("Expected the suppressed phone to block a new call.")


async def test_stop_suppression_survives_tts_failure(db_session):
    class FailingTTSAdapter(StubTTSAdapter):
        async def synthesize(self, request):
            raise RuntimeError("synthetic TTS failure")

    async with db_session.async_session() as session:
        opener = await run_porter_voice_opener(
            session,
            tts_adapter=StubTTSAdapter(),
        )
        await session.commit()

        try:
            await run_porter_live_voice_turn(
                session,
                call_session_id=opener.call_session_id,
                user_text_override="Remove me and do not call again.",
                tts_adapter=FailingTTSAdapter(),
            )
        except RuntimeError as exc:
            assert "synthetic TTS failure" in str(exc)
        else:
            raise AssertionError("Expected synthetic TTS failure.")
        lead = await session.get(PorterLeadModel, opener.lead_id)
        phone_suppression = await session.scalar(
            select(PorterPhoneSuppressionModel).where(
                PorterPhoneSuppressionModel.phone == opener.destination_phone
            )
        )

    assert lead.do_not_call is True
    assert lead.suppression_reason == "caller_requested_do_not_call"
    assert phone_suppression is not None
    assert phone_suppression.source_call_session_id == opener.call_session_id


async def test_live_silence_turns_use_bounded_repair_and_close(db_session):
    async with db_session.async_session() as session:
        opener = await run_porter_voice_opener(
            session,
            tts_adapter=StubTTSAdapter(),
        )
        turns = []
        for _ in range(3):
            turns.append(
                await run_porter_live_voice_turn(
                    session,
                    call_session_id=opener.call_session_id,
                    user_text_override="[silence]",
                    event_source="browser_silence",
                    tts_adapter=StubTTSAdapter(),
                )
            )
        outcome = await session.scalar(
            select(PorterCallOutcomeModel).where(
                PorterCallOutcomeModel.call_session_id == opener.call_session_id
            )
        )
        await session.commit()

    assert turns[0].assistant_text == OPENER
    assert turns[1].assistant_text == THIRD_HELLO
    assert turns[2].assistant_text == NO_RESPONSE_CLOSE
    assert turns[2].should_close is True
    assert outcome.disposition == "no_answer"
    assert turns[2].transcript[-2]["raw_metadata"]["source"] == "browser_silence"


def test_fast_voice_preserves_approved_cold_call_scripts():
    cases = {
        "Yes, go ahead": PITCH,
        "That sounds good": QUALIFIER_OPENING,
        "We already have a factor": ALREADY_HAS_FACTOR,
        "Not interested": NOT_INTERESTED,
        "What are your rates?": RATES,
        "Are you an AI?": DISCLOSURE,
        "Remove me and stop calling": EXIT,
    }

    for user_text, expected in cases.items():
        response = _build_fast_voice_response(
            policy_engine=PorterPolicyEngine(),
            user_text=user_text,
        )
        assert response.allowed is True
        assert response.safe_text == expected


def test_fast_voice_answers_general_more_info_from_locked_kb():
    response = _build_fast_voice_response(
        policy_engine=PorterPolicyEngine(),
        user_text="Hey, can I know more?",
    )

    assert response.safe_text == (
        "Yeah, Porter helps B2B businesses turn unpaid invoices into working capital."
    )
    assert response.allowed is True


def test_fast_voice_answers_common_locked_kb_questions():
    cases = {
        "How does it work?": "So, it helps B2B businesses turn unpaid invoices into working capital.",
        "Who do you serve?": "Yeah, Porter works with B2B companies that invoice businesses or government clients.",
        "Why Porter?": "Yeah, Porter has been doing this for decades and is big on dedicated service.",
        "What is the next step?": "Got it — I can get one of our financing advisors to follow up.",
        "Something else": "Sure — what part are you trying to figure out first?",
    }

    for user_text, expected in cases.items():
        response = _build_fast_voice_response(
            policy_engine=PorterPolicyEngine(),
            user_text=user_text,
        )

        assert response.safe_text == expected
        assert response.allowed is True
        assert response.safe_text != "Got it — I can send this to the Porter team."


def test_fast_voice_advances_the_cold_call_script_using_conversation_state():
    policy_engine = PorterPolicyEngine()

    pitch = _build_fast_voice_response(
        policy_engine=policy_engine,
        user_text="Yes, go ahead.",
        state=PorterConversationState.OPENING,
    )
    qualifier = _build_fast_voice_response(
        policy_engine=policy_engine,
        user_text="Yes, that sounds good.",
        state=PorterConversationState.PERMISSION_CHECK,
    )
    follow_up = _build_fast_voice_response(
        policy_engine=policy_engine,
        user_text="We are a manufacturing company.",
        state=PorterConversationState.REASON_FOR_CALL,
    )

    assert pitch.safe_text == PITCH
    assert qualifier.safe_text == QUALIFIER_OPENING
    assert follow_up.safe_text == QUALIFIER_FOLLOW_UP.format(
        natural_reaction="that helps"
    )


def test_fast_voice_does_not_treat_identity_or_unclear_speech_as_qualification():
    policy_engine = PorterPolicyEngine()
    cases = (
        ("Hello.", PorterConversationState.OPENING, "Hey — can you hear me okay?"),
        ("I want you.", PorterConversationState.PERMISSION_CHECK, "Yeah — what did you want to ask me?"),
        (
            "I know who are you.",
            PorterConversationState.REASON_FOR_CALL,
            "Yeah — I'm Aiva, an AI agent with Porter Capital.",
        ),
        (
            "Who are you?",
            PorterConversationState.FUNDING_NEED,
            "Yeah — I'm Aiva, an AI agent with Porter Capital.",
        ),
    )

    for user_text, state, expected in cases:
        response = _build_fast_voice_response(
            policy_engine=policy_engine,
            user_text=user_text,
            state=state,
        )

        assert response.allowed is True
        assert response.safe_text == expected


def test_fast_voice_understands_spoken_funding_and_factoring_variants():
    policy_engine = PorterPolicyEngine()
    state = PorterConversationState.OBJECTION_HANDLING
    cases = {
        "So how long do you take to provide the funding?": (
            "Yeah, once you're set up with Porter, funding is usually under 48 hours after you submit an invoice."
        ),
        "mean by what part?": "Yeah \N{EM DASH} I mean how invoice factoring could help your business.",
        "Inways factor.": "So, it helps B2B businesses turn unpaid invoices into working capital.",
        "and what it's factoring.": "So, it helps B2B businesses turn unpaid invoices into working capital.",
    }

    for user_text, expected in cases.items():
        response = _build_fast_voice_response(
            policy_engine=policy_engine,
            user_text=user_text,
            state=state,
        )

        assert response.allowed is True
        assert response.safe_text == expected
