import asyncio
import math
import re
import threading
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

from api.porter.policy import PorterPolicyEngine


DEFAULT_TTS_SAMPLE_RATE = 24_000
ELLIPSIS_PAUSE_MS = 320
EM_DASH_PAUSE_MS = 180


class PorterTTSError(RuntimeError):
    pass


class PorterTTSDependencyError(PorterTTSError):
    pass


class UnsafeTextForTTSError(PorterTTSError):
    pass


@dataclass(frozen=True)
class TTSRequest:
    text: str
    output_path: Path
    voice: str = "af_heart"
    sample_rate: int = DEFAULT_TTS_SAMPLE_RATE


@dataclass(frozen=True)
class TTSResult:
    output_path: Path
    text: str
    voice: str
    sample_rate: int
    duration_seconds: float
    adapter_name: str
    metadata: dict[str, object]


class TTSAdapter(ABC):
    @property
    def cache_identity(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    async def synthesize(self, request: TTSRequest) -> TTSResult:
        pass

    @property
    def supports_streaming_audio(self) -> bool:
        return False


class SafeTTSAdapter(TTSAdapter):
    def __init__(
        self,
        adapter: TTSAdapter,
        *,
        policy_engine: PorterPolicyEngine | None = None,
    ) -> None:
        self._adapter = adapter
        self._policy_engine = policy_engine or PorterPolicyEngine()

    @property
    def cache_identity(self) -> str:
        return self._adapter.cache_identity

    async def synthesize(self, request: TTSRequest) -> TTSResult:
        policy_result = self._policy_engine.check_response(request.text)
        if not policy_result.allowed:
            raise UnsafeTextForTTSError(policy_result.safe_text)
        return await self._adapter.synthesize(request)

    @property
    def supports_streaming_audio(self) -> bool:
        return self._adapter.supports_streaming_audio

    async def synthesize_stream(
        self,
        request: TTSRequest,
        on_chunk: Callable[[bytes, int], Awaitable[None]],
    ) -> TTSResult:
        policy_result = self._policy_engine.check_response(request.text)
        if not policy_result.allowed:
            raise UnsafeTextForTTSError(policy_result.safe_text)
        if not self._adapter.supports_streaming_audio:
            raise PorterTTSError("This TTS adapter does not support audio streaming.")
        return await self._adapter.synthesize_stream(request, on_chunk)


class StubTTSAdapter(TTSAdapter):
    """Deterministic local WAV generator used until Kokoro is installed."""

    def __init__(self, *, tone_hz: int = 440) -> None:
        self.tone_hz = tone_hz

    @property
    def cache_identity(self) -> str:
        return f"stub-tone:{self.tone_hz}"

    async def synthesize(self, request: TTSRequest) -> TTSResult:
        return await asyncio.to_thread(self._synthesize, request)

    def _synthesize(self, request: TTSRequest) -> TTSResult:
        text = request.text.strip()
        if not text:
            raise PorterTTSError("TTS text cannot be empty.")
        if request.sample_rate <= 0:
            raise PorterTTSError("TTS sample rate must be greater than zero.")

        duration_seconds = _duration_for_text(text)
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        _write_tone_wav(
            request.output_path,
            sample_rate=request.sample_rate,
            duration_seconds=duration_seconds,
            tone_hz=self.tone_hz,
        )
        return TTSResult(
            output_path=request.output_path,
            text=text,
            voice=request.voice,
            sample_rate=request.sample_rate,
            duration_seconds=duration_seconds,
            adapter_name="stub",
            metadata={"synthetic": True, "tone_hz": self.tone_hz},
        )


class KokoroTTSAdapter(TTSAdapter):
    def __init__(self, *, model_path: Path, voices_path: Path) -> None:
        self.model_path = model_path
        self.voices_path = voices_path
        self._kokoro = None

    def prewarm(self) -> None:
        self._load_kokoro()

    @property
    def cache_identity(self) -> str:
        return "|".join(
            (
                "kokoro-onnx-v2-explicit-prosody",
                _asset_identity(self.model_path),
                _asset_identity(self.voices_path),
            )
        )

    async def synthesize(self, request: TTSRequest) -> TTSResult:
        text = request.text.strip()
        if not text:
            raise PorterTTSError("TTS text cannot be empty.")

        kokoro = self._load_kokoro()
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            samples, sample_rate, segment_count = _synthesize_with_explicit_pauses(
                kokoro,
                text=text,
                voice=request.voice,
                fallback_sample_rate=request.sample_rate,
            )
        except Exception as exc:
            raise PorterTTSError(f"Kokoro synthesis failed: {exc}") from exc

        _write_float_samples_wav(
            request.output_path,
            samples=samples,
            sample_rate=int(sample_rate or request.sample_rate),
        )
        duration_seconds = _wav_duration_seconds(request.output_path)
        return TTSResult(
            output_path=request.output_path,
            text=text,
            voice=request.voice,
            sample_rate=int(sample_rate or request.sample_rate),
            duration_seconds=duration_seconds,
            adapter_name="kokoro",
            metadata={
                "model_path": str(self.model_path),
                "voices_path": str(self.voices_path),
                "prosody": "explicit-marker-pauses-v1",
                "segment_count": segment_count,
                "ellipsis_pause_ms": ELLIPSIS_PAUSE_MS,
                "em_dash_pause_ms": EM_DASH_PAUSE_MS,
            },
        )

    def _load_kokoro(self):
        if self._kokoro is not None:
            return self._kokoro
        try:
            from kokoro_onnx import Kokoro
        except ImportError as exc:
            raise PorterTTSDependencyError(
                "Kokoro is not installed. Install kokoro-onnx and provide "
                "PORTER_KOKORO_MODEL_PATH and PORTER_KOKORO_VOICES_PATH before "
                "using KokoroTTSAdapter."
            ) from exc
        if not self.model_path.exists():
            raise PorterTTSDependencyError(f"Kokoro model not found: {self.model_path}")
        if not self.voices_path.exists():
            raise PorterTTSDependencyError(f"Kokoro voices not found: {self.voices_path}")
        self._kokoro = Kokoro(str(self.model_path), str(self.voices_path))
        return self._kokoro


class PocketTTSAdapter(TTSAdapter):
    """Local, streaming-capable Pocket TTS adapter for low-latency replies."""

    def __init__(self, *, voice_prompt: str = "bill_boerst", language: str | None = None) -> None:
        self.voice_prompt = voice_prompt
        self.language = language
        self._model = None
        self._voice_state = None
        self._lock = threading.RLock()

    @property
    def cache_identity(self) -> str:
        language = self.language or "english"
        return f"pocket-tts-v2:{language}:{self.voice_prompt}"

    def prewarm(self) -> None:
        self._load_model_and_voice()

    @property
    def supports_streaming_audio(self) -> bool:
        return True

    async def synthesize(self, request: TTSRequest) -> TTSResult:
        return await asyncio.to_thread(self._synthesize, request)

    async def synthesize_stream(
        self,
        request: TTSRequest,
        on_chunk: Callable[[bytes, int], Awaitable[None]],
    ) -> TTSResult:
        loop = asyncio.get_running_loop()
        return await asyncio.to_thread(self._synthesize_stream, request, loop, on_chunk)

    def _synthesize(self, request: TTSRequest) -> TTSResult:
        text = request.text.strip()
        if not text:
            raise PorterTTSError("TTS text cannot be empty.")

        with self._lock:
            model, voice_state = self._load_model_and_voice()
            try:
                audio = model.generate_audio(voice_state, text)
                samples = audio.detach().cpu().numpy().reshape(-1)
            except Exception as exc:
                raise PorterTTSError(f"Pocket TTS synthesis failed: {exc}") from exc

        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        _write_float_samples_wav(
            request.output_path,
            samples=samples,
            sample_rate=model.sample_rate,
        )
        duration_seconds = _wav_duration_seconds(request.output_path)
        return TTSResult(
            output_path=request.output_path,
            text=text,
            voice=self.voice_prompt,
            sample_rate=model.sample_rate,
            duration_seconds=duration_seconds,
            adapter_name="pocket-tts",
            metadata={
                "voice_prompt": self.voice_prompt,
                "language": self.language or "english",
                "streaming_capable": True,
            },
        )

    def _synthesize_stream(
        self,
        request: TTSRequest,
        loop: asyncio.AbstractEventLoop,
        on_chunk: Callable[[bytes, int], Awaitable[None]],
    ) -> TTSResult:
        text = request.text.strip()
        if not text:
            raise PorterTTSError("TTS text cannot be empty.")

        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            model, voice_state = self._load_model_and_voice()
            sample_rate = int(model.sample_rate)
            try:
                with wave.open(str(request.output_path), "wb") as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(sample_rate)
                    for audio in model.generate_audio_stream(voice_state, text):
                        samples = audio.detach().cpu().numpy().reshape(-1)
                        pcm16 = _float_samples_to_pcm16(samples)
                        if not pcm16:
                            continue
                        wav_file.writeframesraw(pcm16)
                        asyncio.run_coroutine_threadsafe(
                            on_chunk(pcm16, sample_rate), loop
                        ).result()
            except Exception as exc:
                raise PorterTTSError(f"Pocket TTS streaming synthesis failed: {exc}") from exc

        duration_seconds = _wav_duration_seconds(request.output_path)
        return TTSResult(
            output_path=request.output_path,
            text=text,
            voice=self.voice_prompt,
            sample_rate=sample_rate,
            duration_seconds=duration_seconds,
            adapter_name="pocket-tts",
            metadata={
                "voice_prompt": self.voice_prompt,
                "language": self.language or "english",
                "streaming_capable": True,
                "streamed": True,
            },
        )

    def _load_model_and_voice(self):
        with self._lock:
            if self._model is None:
                try:
                    from pocket_tts import TTSModel
                except ImportError as exc:
                    raise PorterTTSDependencyError(
                        "Pocket TTS is not installed. Install pocket-tts before using "
                        "PORTER_TTS_MODE=pocket."
                    ) from exc
                try:
                    self._model = TTSModel.load_model(language=self.language)
                    self._voice_state = self._model.get_state_for_audio_prompt(self.voice_prompt)
                except Exception as exc:
                    raise PorterTTSError(f"Pocket TTS initialization failed: {exc}") from exc
            return self._model, self._voice_state


def _synthesize_with_explicit_pauses(
    kokoro,
    *,
    text: str,
    voice: str,
    fallback_sample_rate: int,
) -> tuple[list[float], int, int]:
    rendered_samples: list[float] = []
    output_sample_rate: int | None = None
    segments = _split_spoken_segments(text)
    for segment_text, pause_ms in segments:
        segment_samples, segment_sample_rate = kokoro.create(
            segment_text,
            voice=voice,
            speed=1.0,
            lang="en-us",
        )
        current_sample_rate = int(segment_sample_rate or fallback_sample_rate)
        if output_sample_rate is None:
            output_sample_rate = current_sample_rate
        elif current_sample_rate != output_sample_rate:
            raise PorterTTSError("Kokoro returned inconsistent sample rates.")
        rendered_samples.extend(float(sample) for sample in segment_samples)
        if pause_ms:
            rendered_samples.extend(
                0.0 for _ in range(round(output_sample_rate * pause_ms / 1000))
            )
    return rendered_samples, output_sample_rate or fallback_sample_rate, len(segments)


def _split_spoken_segments(text: str) -> tuple[tuple[str, int], ...]:
    marker_pauses = {"...": ELLIPSIS_PAUSE_MS, "—": EM_DASH_PAUSE_MS}
    segments: list[tuple[str, int]] = []
    cursor = 0
    for match in re.finditer(r"\.\.\.|—", text):
        spoken_text = text[cursor : match.start()].strip()
        if spoken_text:
            segments.append((spoken_text, marker_pauses[match.group(0)]))
        elif segments:
            previous_text, previous_pause = segments[-1]
            segments[-1] = (
                previous_text,
                max(previous_pause, marker_pauses[match.group(0)]),
            )
        cursor = match.end()
    trailing_text = text[cursor:].strip()
    if trailing_text:
        segments.append((trailing_text, 0))
    return tuple(segments or ((text.strip(), 0),))


def _duration_for_text(text: str) -> float:
    return min(max(len(text) / 80.0, 0.25), 3.0)


def _asset_identity(path: Path) -> str:
    try:
        stat = path.stat()
    except OSError:
        return f"{path}:missing"
    return f"{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}"


def _write_tone_wav(
    output_path: Path,
    *,
    sample_rate: int,
    duration_seconds: float,
    tone_hz: int,
) -> None:
    frame_count = int(sample_rate * duration_seconds)
    amplitude = 0.15
    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        for index in range(frame_count):
            sample = int(
                32767
                * amplitude
                * math.sin(2 * math.pi * tone_hz * index / sample_rate)
            )
            wav_file.writeframesraw(sample.to_bytes(2, byteorder="little", signed=True))


def _write_float_samples_wav(output_path: Path, *, samples, sample_rate: int) -> None:
    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        for sample in samples:
            clipped = max(min(float(sample), 1.0), -1.0)
            pcm = int(clipped * 32767)
            wav_file.writeframesraw(pcm.to_bytes(2, byteorder="little", signed=True))


def _float_samples_to_pcm16(samples) -> bytes:
    return (samples.clip(-1.0, 1.0) * 32767).astype("<i2", copy=False).tobytes()


def _wav_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as wav_file:
        return wav_file.getnframes() / float(wav_file.getframerate())
