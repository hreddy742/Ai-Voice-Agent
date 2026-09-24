import math
import wave

from api.porter.pcm_stream import (
    MAX_PCM_CHUNK_BYTES,
    PorterPCMStreamBuffer,
    PorterPCMStreamError,
    write_pcm16_wav,
)


def _pcm(duration_seconds: float = 0.2) -> bytes:
    samples = bytearray()
    for index in range(int(16_000 * duration_seconds)):
        sample = int(32767 * 0.25 * math.sin(2 * math.pi * 440 * index / 16_000))
        samples.extend(sample.to_bytes(2, "little", signed=True))
    return bytes(samples)


def test_pcm_stream_commits_bounded_audio_and_writes_valid_wav(tmp_path):
    stream = PorterPCMStreamBuffer()
    stream.append(_pcm())

    audio = stream.commit()
    output = tmp_path / "turn.wav"
    write_pcm16_wav(audio, output)

    assert stream.size == 0
    with wave.open(str(output), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getframerate() == 16_000
        assert wav_file.getsampwidth() == 2


def test_pcm_stream_rejects_invalid_and_oversized_chunks():
    stream = PorterPCMStreamBuffer()
    for chunk in (b"\x00", b"\x00\x00" * (MAX_PCM_CHUNK_BYTES // 2 + 1)):
        try:
            stream.append(chunk)
        except PorterPCMStreamError:
            pass
        else:
            raise AssertionError("Expected invalid PCM chunk to be rejected.")
