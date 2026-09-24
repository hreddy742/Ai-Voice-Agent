import audioop
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import PorterAgentEventModel


class PorterVADError(RuntimeError):
    pass


class PorterVADDependencyError(PorterVADError):
    pass


class PorterInterruptionEventType(StrEnum):
    USER_STARTED_SPEAKING = "user_started_speaking"
    AGENT_AUDIO_INTERRUPTED = "agent_audio_interrupted"
    AGENT_RESPONSE_CANCELLED = "agent_response_cancelled"


@dataclass(frozen=True)
class SpeechSegment:
    start_seconds: float
    end_seconds: float
    confidence: float


@dataclass(frozen=True)
class VADResult:
    speech_segments: tuple[SpeechSegment, ...]
    sample_rate: int
    duration_seconds: float
    adapter_name: str

    @property
    def has_speech(self) -> bool:
        return bool(self.speech_segments)


class VADAdapter(ABC):
    @abstractmethod
    async def detect_speech(self, audio_path: Path) -> VADResult:
        pass


class EnergyVADAdapter(VADAdapter):
    def __init__(self, *, frame_ms: int = 30, rms_threshold: int = 350) -> None:
        self.frame_ms = frame_ms
        self.rms_threshold = rms_threshold

    async def detect_speech(self, audio_path: Path) -> VADResult:
        if not audio_path.exists() or audio_path.stat().st_size == 0:
            raise PorterVADError(f"Audio file is missing or empty: {audio_path}")

        with wave.open(str(audio_path), "rb") as wav_file:
            sample_rate = wav_file.getframerate()
            sample_width = wav_file.getsampwidth()
            total_frames = wav_file.getnframes()
            channels = wav_file.getnchannels()
            if sample_rate <= 0 or sample_width <= 0 or total_frames <= 0:
                raise PorterVADError("Audio file has no usable PCM frames.")
            frame_size = max(1, int(sample_rate * self.frame_ms / 1000))
            voiced_ranges = []
            frame_index = 0
            while True:
                data = wav_file.readframes(frame_size)
                if not data:
                    break
                if channels > 1:
                    data = audioop.tomono(data, sample_width, 0.5, 0.5)
                rms = audioop.rms(data, sample_width)
                if rms >= self.rms_threshold:
                    start = frame_index / sample_rate
                    end = min((frame_index + frame_size) / sample_rate, total_frames / sample_rate)
                    voiced_ranges.append((start, end, rms))
                frame_index += frame_size

        merged = _merge_voiced_ranges(voiced_ranges)
        max_rms = max((rms for _, _, rms in voiced_ranges), default=0)
        segments = tuple(
            SpeechSegment(
                start_seconds=start,
                end_seconds=end,
                confidence=min(rms / max(max_rms, self.rms_threshold), 1.0),
            )
            for start, end, rms in merged
        )
        return VADResult(
            speech_segments=segments,
            sample_rate=sample_rate,
            duration_seconds=total_frames / float(sample_rate),
            adapter_name="energy",
        )


class SileroVADAdapter(VADAdapter):
    async def detect_speech(self, audio_path: Path) -> VADResult:
        try:
            import torch  # noqa: F401
        except ImportError as exc:
            raise PorterVADDependencyError(
                "Silero VAD dependencies are not installed. Use EnergyVADAdapter "
                "for local tests or install torch plus silero-vad intentionally."
            ) from exc
        raise PorterVADDependencyError(
            "SileroVADAdapter boundary is present, but realtime Silero wiring is "
            "not enabled for Porter local validation yet."
        )


async def log_interruption_event(
    session: AsyncSession,
    *,
    call_session_id: int,
    event_type: PorterInterruptionEventType,
    payload: dict[str, object] | None = None,
) -> PorterAgentEventModel:
    event = PorterAgentEventModel(
        call_session_id=call_session_id,
        event_type=event_type.value,
        event_payload=dict(payload or {}),
    )
    session.add(event)
    await session.flush()
    return event


async def cancel_agent_response_for_interruption(
    session: AsyncSession,
    *,
    call_session_id: int,
    reason: str = "user_started_speaking",
) -> Sequence[PorterAgentEventModel]:
    interrupted = await log_interruption_event(
        session,
        call_session_id=call_session_id,
        event_type=PorterInterruptionEventType.AGENT_AUDIO_INTERRUPTED,
        payload={"reason": reason},
    )
    cancelled = await log_interruption_event(
        session,
        call_session_id=call_session_id,
        event_type=PorterInterruptionEventType.AGENT_RESPONSE_CANCELLED,
        payload={"reason": reason},
    )
    return (interrupted, cancelled)


def _merge_voiced_ranges(ranges: list[tuple[float, float, int]]) -> list[tuple[float, float, int]]:
    if not ranges:
        return []
    merged = [ranges[0]]
    for start, end, rms in ranges[1:]:
        previous_start, previous_end, previous_rms = merged[-1]
        if start <= previous_end + 0.12:
            merged[-1] = (previous_start, end, max(previous_rms, rms))
        else:
            merged.append((start, end, rms))
    return merged
