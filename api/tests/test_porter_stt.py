from types import SimpleNamespace

import pytest
from sqlalchemy import select

from api.db.models import PorterCallSessionModel, PorterTranscriptTurnModel
from api.porter.mock_leads import load_mock_porter_leads
from api.porter.stt import (
    FasterWhisperSTTAdapter,
    MockSTTAdapter,
    PorterEmptyAudioError,
    PorterSTTDependencyError,
    STTRequest,
    record_stt_transcript_turn,
    safe_transcribe_file,
)
from api.porter.state_machine import PorterConversationState
from api.porter.tts import StubTTSAdapter, TTSRequest


async def _sample_wav(tmp_path):
    path = tmp_path / "sample.wav"
    await StubTTSAdapter().synthesize(
        TTSRequest(text="sample audio", output_path=path)
    )
    return path


async def test_mock_stt_adapter_transcribes_sample_audio(tmp_path):
    audio_path = await _sample_wav(tmp_path)

    result = await MockSTTAdapter("We need payroll funding.").transcribe_file(
        STTRequest(audio_path=audio_path)
    )

    assert result.text == "We need payroll funding."
    assert result.confidence == 0.99
    assert result.duration_seconds and result.duration_seconds > 0


async def test_empty_audio_is_handled(tmp_path):
    empty_path = tmp_path / "empty.wav"
    empty_path.write_bytes(b"")

    with pytest.raises(PorterEmptyAudioError):
        await MockSTTAdapter("hello").transcribe_file(STTRequest(audio_path=empty_path))


async def test_adapter_failure_does_not_crash_call_session(tmp_path):
    empty_path = tmp_path / "empty.wav"
    empty_path.write_bytes(b"")

    result = await safe_transcribe_file(
        MockSTTAdapter("hello"),
        STTRequest(audio_path=empty_path),
    )

    assert result.failed is True
    assert result.text == ""
    assert "empty" in result.error.lower()


async def test_transcript_turn_can_be_created_from_stt_output(async_session, tmp_path):
    audio_path = await _sample_wav(tmp_path)
    leads = await load_mock_porter_leads(async_session, replace=True)
    call_session = PorterCallSessionModel(
        lead=leads[0],
        destination_phone=leads[0].phone,
        status="in_progress",
        prompt_version="porter-local-v1",
        knowledge_base_version="porter-kb-v1",
        human_review_required=True,
        crm_sync_status="not_ready",
    )
    async_session.add(call_session)
    await async_session.flush()

    result = await MockSTTAdapter("We invoice B2B customers.").transcribe_file(
        STTRequest(audio_path=audio_path)
    )
    await record_stt_transcript_turn(
        async_session,
        call_session_id=call_session.id,
        result=result,
        state=PorterConversationState.INVOICE_AR_FIT,
    )
    await async_session.commit()

    row = await async_session.scalar(
        select(PorterTranscriptTurnModel).where(
            PorterTranscriptTurnModel.call_session_id == call_session.id
        )
    )

    assert row.text == "We invoice B2B customers."
    assert row.speaker == "user"
    assert row.conversation_state == "invoice_ar_fit"
    assert row.raw_metadata["adapter_name"] == "mock"


async def test_faster_whisper_adapter_boundary_handles_runtime_state(tmp_path):
    audio_path = await _sample_wav(tmp_path)

    try:
        result = await FasterWhisperSTTAdapter(model_name="tiny.en").transcribe_file(
            STTRequest(audio_path=audio_path)
        )
    except PorterSTTDependencyError:
        return
    except PorterEmptyAudioError:
        return

    assert result.adapter_name == "faster-whisper"


async def test_faster_whisper_uses_vad_and_rejects_no_speech_segments(tmp_path):
    audio_path = await _sample_wav(tmp_path)
    transcribe_kwargs = {}

    class FakeWhisperModel:
        def transcribe(self, _path, **kwargs):
            transcribe_kwargs.update(kwargs)
            return (
                iter([SimpleNamespace(text="Yeah.", no_speech_prob=0.92)]),
                SimpleNamespace(language="en", language_probability=0.99),
            )

    adapter = FasterWhisperSTTAdapter(model_name="tiny.en")
    adapter._model = FakeWhisperModel()

    with pytest.raises(PorterEmptyAudioError, match="empty text"):
        await adapter.transcribe_file(STTRequest(audio_path=audio_path))

    assert transcribe_kwargs["vad_filter"] is True
    assert transcribe_kwargs["vad_parameters"] == {"min_silence_duration_ms": 300}
    assert "invoice factoring" in transcribe_kwargs["hotwords"]


def test_faster_whisper_prewarm_loads_model_once(monkeypatch):
    adapter = FasterWhisperSTTAdapter(model_name="base.en")
    loaded_model = object()
    load_count = 0

    def fake_load_model():
        nonlocal load_count
        load_count += 1
        return loaded_model

    monkeypatch.setattr(adapter, "_load_model", fake_load_model)

    adapter.prewarm()

    assert load_count == 1
