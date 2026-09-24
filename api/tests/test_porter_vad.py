import wave

import pytest
from sqlalchemy import select

from api.db.models import PorterAgentEventModel, PorterCallSessionModel
from api.porter.mock_leads import load_mock_porter_leads
from api.porter.vad import (
    EnergyVADAdapter,
    PorterInterruptionEventType,
    PorterVADDependencyError,
    SileroVADAdapter,
    cancel_agent_response_for_interruption,
    log_interruption_event,
)


def _write_pcm_wav(path, *, amplitude: int, seconds: float = 0.4, sample_rate: int = 16000):
    frame_count = int(seconds * sample_rate)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        for _ in range(frame_count):
            wav_file.writeframesraw(
                int(amplitude).to_bytes(2, byteorder="little", signed=True)
            )


async def _call_session(async_session):
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
    return call_session


async def test_vad_identifies_speech_segment(tmp_path):
    audio_path = tmp_path / "speech.wav"
    _write_pcm_wav(audio_path, amplitude=1800)

    result = await EnergyVADAdapter(rms_threshold=350).detect_speech(audio_path)

    assert result.has_speech is True
    assert result.speech_segments[0].start_seconds == 0
    assert result.speech_segments[0].end_seconds > 0


async def test_vad_handles_silence_without_crashing(tmp_path):
    audio_path = tmp_path / "silence.wav"
    _write_pcm_wav(audio_path, amplitude=0)

    result = await EnergyVADAdapter(rms_threshold=350).detect_speech(audio_path)

    assert result.has_speech is False
    assert result.speech_segments == ()


async def test_interruption_event_can_be_logged(async_session):
    call_session = await _call_session(async_session)

    event = await log_interruption_event(
        async_session,
        call_session_id=call_session.id,
        event_type=PorterInterruptionEventType.USER_STARTED_SPEAKING,
        payload={"state": "funding_need"},
    )
    await async_session.commit()

    row = await async_session.get(PorterAgentEventModel, event.id)
    assert row.event_type == "user_started_speaking"
    assert row.event_payload == {"state": "funding_need"}


async def test_agent_can_cancel_response_in_simulation(async_session):
    call_session = await _call_session(async_session)

    events = await cancel_agent_response_for_interruption(
        async_session,
        call_session_id=call_session.id,
    )
    await async_session.commit()

    rows = (
        await async_session.execute(
            select(PorterAgentEventModel)
            .where(PorterAgentEventModel.call_session_id == call_session.id)
            .order_by(PorterAgentEventModel.id)
        )
    ).scalars().all()

    assert len(events) == 2
    assert [row.event_type for row in rows] == [
        "agent_audio_interrupted",
        "agent_response_cancelled",
    ]


async def test_silero_adapter_reports_missing_or_disabled_dependency(tmp_path):
    audio_path = tmp_path / "speech.wav"
    _write_pcm_wav(audio_path, amplitude=1800)

    with pytest.raises(PorterVADDependencyError):
        await SileroVADAdapter().detect_speech(audio_path)
