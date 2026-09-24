import wave
from pathlib import Path


PCM_SAMPLE_RATE = 16_000
PCM_CHANNELS = 1
PCM_SAMPLE_WIDTH = 2
MAX_PCM_CHUNK_BYTES = 64 * 1024
MAX_PCM_TURN_BYTES = PCM_SAMPLE_RATE * PCM_SAMPLE_WIDTH * 20
MIN_PCM_TURN_BYTES = int(PCM_SAMPLE_RATE * PCM_SAMPLE_WIDTH * 0.15)


class PorterPCMStreamError(ValueError):
    pass


class PorterPCMStreamBuffer:
    def __init__(self) -> None:
        self._audio = bytearray()

    @property
    def size(self) -> int:
        return len(self._audio)

    def append(self, chunk: bytes) -> None:
        if not chunk or len(chunk) > MAX_PCM_CHUNK_BYTES or len(chunk) % PCM_SAMPLE_WIDTH:
            raise PorterPCMStreamError("Invalid PCM audio chunk.")
        if len(self._audio) + len(chunk) > MAX_PCM_TURN_BYTES:
            self.reset()
            raise PorterPCMStreamError("PCM turn exceeds the 20 second limit.")
        self._audio.extend(chunk)

    def commit(self) -> bytes:
        if len(self._audio) < MIN_PCM_TURN_BYTES:
            self.reset()
            raise PorterPCMStreamError("PCM turn is too short.")
        audio = bytes(self._audio)
        self.reset()
        return audio

    def reset(self) -> None:
        self._audio.clear()


def write_pcm16_wav(audio: bytes, path: Path) -> None:
    if not audio or len(audio) % PCM_SAMPLE_WIDTH:
        raise PorterPCMStreamError("PCM audio must contain complete 16-bit samples.")
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(PCM_CHANNELS)
        wav_file.setsampwidth(PCM_SAMPLE_WIDTH)
        wav_file.setframerate(PCM_SAMPLE_RATE)
        wav_file.writeframes(audio)
