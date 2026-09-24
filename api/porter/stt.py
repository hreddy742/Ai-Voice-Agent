import os
import sys
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from api.porter.state_machine import (
    PorterConversationState,
    record_porter_transcript_turn,
)

PORTER_STT_HOTWORDS = (
    "Porter Capital Aiva invoice factoring factor invoices receivables "
    "working capital financing advisor B2B payroll transportation staffing "
    "manufacturing distribution government contracting IT consulting"
)
_WINDOWS_CUDA_DLL_HANDLES: list[object] = []


class PorterSTTError(RuntimeError):
    pass


class PorterSTTDependencyError(PorterSTTError):
    pass


class PorterEmptyAudioError(PorterSTTError):
    pass


@dataclass(frozen=True)
class STTRequest:
    audio_path: Path
    language: str = "en"
    prompt: str | None = None


@dataclass(frozen=True)
class STTResult:
    text: str
    confidence: float | None
    language: str
    duration_seconds: float | None
    adapter_name: str
    metadata: dict[str, object]
    error: str | None = None

    @property
    def failed(self) -> bool:
        return self.error is not None


class STTAdapter(ABC):
    @abstractmethod
    async def transcribe_file(self, request: STTRequest) -> STTResult:
        pass


class MockSTTAdapter(STTAdapter):
    def __init__(self, text: str, *, confidence: float | None = 0.99) -> None:
        self.text = text
        self.confidence = confidence

    async def transcribe_file(self, request: STTRequest) -> STTResult:
        duration = inspect_wav_duration(request.audio_path)
        if not self.text.strip():
            raise PorterEmptyAudioError("Mock STT text cannot be empty.")
        return STTResult(
            text=self.text.strip(),
            confidence=self.confidence,
            language=request.language,
            duration_seconds=duration,
            adapter_name="mock",
            metadata={"audio_path": str(request.audio_path)},
        )


class FasterWhisperSTTAdapter(STTAdapter):
    def __init__(
        self,
        *,
        model_name: str = "base.en",
        device: str = "cpu",
        compute_type: str = "int8",
        hotwords: str = PORTER_STT_HOTWORDS,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.hotwords = hotwords
        self._model = None

    def prewarm(self) -> None:
        self._load_model()

    async def transcribe_file(self, request: STTRequest) -> STTResult:
        duration = inspect_wav_duration(request.audio_path)
        model = self._load_model()
        try:
            segment_stream, info = model.transcribe(
                str(request.audio_path),
                language=request.language,
                initial_prompt=request.prompt,
                hotwords=self.hotwords,
                beam_size=1,
                best_of=1,
                condition_on_previous_text=False,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 300},
            )
            segments = list(segment_stream)
            usable_segments = [
                segment
                for segment in segments
                if getattr(segment, "no_speech_prob", 0.0) < 0.6
            ]
            text = " ".join(segment.text.strip() for segment in usable_segments).strip()
        except Exception as exc:
            raise PorterSTTError(f"faster-whisper transcription failed: {exc}") from exc
        if not text:
            raise PorterEmptyAudioError("STT returned empty text.")
        return STTResult(
            text=text,
            confidence=getattr(info, "language_probability", None),
            language=getattr(info, "language", request.language),
            duration_seconds=duration,
            adapter_name="faster-whisper",
            metadata={
                "model_name": self.model_name,
                "device": self.device,
                "compute_type": self.compute_type,
                "segment_count": len(segments),
                "rejected_no_speech_segments": len(segments) - len(usable_segments),
                "domain_hotwords_enabled": bool(self.hotwords),
            },
        )

    def _load_model(self):
        if self._model is not None:
            return self._model
        _register_windows_cuda_dlls(device=self.device)
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise PorterSTTDependencyError(
                "faster-whisper is not installed. Install faster-whisper or run a "
                "Speaches-compatible local STT server before using this adapter."
            ) from exc
        self._model = WhisperModel(
            self.model_name,
            device=self.device,
            compute_type=self.compute_type,
        )
        return self._model


def _register_windows_cuda_dlls(*, device: str) -> None:
    if device != "cuda" or os.name != "nt" or _WINDOWS_CUDA_DLL_HANDLES:
        return
    nvidia_root = Path(sys.executable).parent.parent / "Lib" / "site-packages" / "nvidia"
    directories = []
    for package in ("cuda_nvrtc", "cublas", "cudnn"):
        directory = nvidia_root / package / "bin"
        if directory.is_dir():
            directories.append(str(directory))
            _WINDOWS_CUDA_DLL_HANDLES.append(os.add_dll_directory(str(directory)))
    if directories:
        os.environ["PATH"] = os.pathsep.join((*directories, os.environ.get("PATH", "")))


async def safe_transcribe_file(adapter: STTAdapter, request: STTRequest) -> STTResult:
    try:
        return await adapter.transcribe_file(request)
    except PorterSTTError as exc:
        return STTResult(
            text="",
            confidence=None,
            language=request.language,
            duration_seconds=_safe_duration(request.audio_path),
            adapter_name=adapter.__class__.__name__,
            metadata={"audio_path": str(request.audio_path)},
            error=str(exc),
        )


async def record_stt_transcript_turn(
    session: AsyncSession,
    *,
    call_session_id: int,
    result: STTResult,
    state: PorterConversationState,
    raw_metadata: Mapping[str, object] | None = None,
):
    if result.failed:
        raise PorterSTTError(f"Cannot record failed STT result: {result.error}")
    metadata = {
        "adapter_name": result.adapter_name,
        "confidence": result.confidence,
        "duration_seconds": result.duration_seconds,
        **dict(raw_metadata or {}),
    }
    return await record_porter_transcript_turn(
        session,
        call_session_id=call_session_id,
        speaker="user",
        text=result.text,
        state=state,
        raw_metadata=metadata,
    )


def inspect_wav_duration(path: Path) -> float:
    if not path.exists():
        raise PorterEmptyAudioError(f"Audio file does not exist: {path}")
    if path.stat().st_size == 0:
        raise PorterEmptyAudioError("Audio file is empty.")
    try:
        with wave.open(str(path), "rb") as wav_file:
            frame_count = wav_file.getnframes()
            frame_rate = wav_file.getframerate()
            if frame_count <= 0 or frame_rate <= 0:
                raise PorterEmptyAudioError("Audio file has no usable frames.")
            return frame_count / float(frame_rate)
    except wave.Error as exc:
        raise PorterEmptyAudioError(f"Audio file is not a valid WAV: {path}") from exc


def _safe_duration(path: Path) -> float | None:
    try:
        return inspect_wav_duration(path)
    except PorterSTTError:
        return None
