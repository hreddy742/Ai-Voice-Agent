import wave

import numpy as np
import pytest

from api.porter import live_voice
from api.porter.live_voice import _tts_cache_path
from api.porter.live_voice import PorterLiveVoiceError
from api.porter.tts import (
    ELLIPSIS_PAUSE_MS,
    EM_DASH_PAUSE_MS,
    KokoroTTSAdapter,
    PocketTTSAdapter,
    PorterTTSError,
    PorterTTSDependencyError,
    SafeTTSAdapter,
    StubTTSAdapter,
    TTSRequest,
    UnsafeTextForTTSError,
    _split_spoken_segments,
    _synthesize_with_explicit_pauses,
)


async def test_stub_tts_adapter_generates_audio_file_from_safe_text(tmp_path):
    output_path = tmp_path / "safe.wav"
    result = await SafeTTSAdapter(StubTTSAdapter()).synthesize(
        TTSRequest(
            text="I can send this to the Porter team for review.",
            output_path=output_path,
        )
    )

    assert result.output_path == output_path
    assert result.adapter_name == "stub"
    assert output_path.exists()
    with wave.open(str(output_path), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getframerate() == result.sample_rate
        assert wav_file.getnframes() > 0


async def test_empty_text_fails_cleanly(tmp_path):
    with pytest.raises(PorterTTSError, match="cannot be empty"):
        await StubTTSAdapter().synthesize(
            TTSRequest(text=" ", output_path=tmp_path / "empty.wav")
        )


async def test_unsafe_text_cannot_be_sent_to_tts(tmp_path):
    with pytest.raises(UnsafeTextForTTSError) as exc_info:
        await SafeTTSAdapter(StubTTSAdapter()).synthesize(
            TTSRequest(text="Your rate will be 2%.", output_path=tmp_path / "unsafe.wav")
        )

    assert "Rates depend on qualification and review." in str(exc_info.value)
    assert not (tmp_path / "unsafe.wav").exists()


async def test_tts_failure_is_handled_gracefully(tmp_path):
    class FailingTTSAdapter(StubTTSAdapter):
        async def synthesize(self, request):
            raise PorterTTSError("synthetic failure")

    with pytest.raises(PorterTTSError, match="synthetic failure"):
        await SafeTTSAdapter(FailingTTSAdapter()).synthesize(
            TTSRequest(
                text="I can send this to the Porter team for review.",
                output_path=tmp_path / "failure.wav",
            )
        )


async def test_kokoro_adapter_reports_missing_dependency_or_assets(tmp_path):
    adapter = KokoroTTSAdapter(
        model_path=tmp_path / "missing-model.onnx",
        voices_path=tmp_path / "missing-voices.bin",
    )

    with pytest.raises(PorterTTSDependencyError):
        await adapter.synthesize(
            TTSRequest(
                text="I can send this to the Porter team for review.",
                output_path=tmp_path / "kokoro.wav",
            )
        )


def test_pocket_tts_cache_identity_is_scoped_to_its_voice():
    assert PocketTTSAdapter(voice_prompt="bill_boerst").cache_identity != PocketTTSAdapter(
        voice_prompt="george"
    ).cache_identity


async def test_pocket_tts_streams_pcm16_before_returning_final_wav(tmp_path):
    class FakeTensor:
        def __init__(self, samples):
            self.samples = samples

        def detach(self):
            return self

        def cpu(self):
            return self

        def numpy(self):
            return self.samples

    class FakePocketModel:
        sample_rate = 24_000

        def generate_audio_stream(self, _voice_state, _text):
            yield FakeTensor(np.array([0.25, -0.25], dtype=np.float32))
            yield FakeTensor(np.array([0.5, -0.5], dtype=np.float32))

    adapter = PocketTTSAdapter()
    adapter._model = FakePocketModel()
    adapter._voice_state = object()
    chunks: list[tuple[bytes, int]] = []

    async def on_chunk(pcm16: bytes, sample_rate: int) -> None:
        chunks.append((pcm16, sample_rate))

    output_path = tmp_path / "streamed.wav"
    result = await adapter.synthesize_stream(
        TTSRequest(text="Porter Capital", output_path=output_path),
        on_chunk,
    )

    assert [sample_rate for _, sample_rate in chunks] == [24_000, 24_000]
    assert [len(pcm16) for pcm16, _ in chunks] == [4, 4]
    assert result.metadata["streamed"] is True
    with wave.open(str(output_path), "rb") as wav_file:
        assert wav_file.getnframes() == 4


def test_default_tts_adapter_supports_pocket_mode(monkeypatch):
    monkeypatch.setenv("PORTER_TTS_MODE", "pocket")
    monkeypatch.setenv("PORTER_POCKET_TTS_VOICE", "bill_boerst")
    live_voice.reset_default_voice_adapters_for_tests()

    adapter = live_voice.build_default_tts_adapter()

    assert isinstance(adapter, PocketTTSAdapter)
    assert adapter.voice_prompt == "bill_boerst"
    live_voice.reset_default_voice_adapters_for_tests()


def test_tts_cache_key_is_scoped_to_the_adapter():
    text = "This cache entry must not reuse test audio."

    tone_path = _tts_cache_path(
        text=text,
        voice="af_heart",
        adapter=SafeTTSAdapter(StubTTSAdapter()),
    )
    kokoro_path = _tts_cache_path(
        text=text,
        voice="af_heart",
        adapter=SafeTTSAdapter(
            KokoroTTSAdapter(
                model_path=tone_path.parent / "model.onnx",
                voices_path=tone_path.parent / "voices.bin",
            )
        ),
    )

    assert tone_path != kokoro_path


def test_default_voice_runtime_fails_closed_without_kokoro(monkeypatch, tmp_path):
    monkeypatch.delenv("PORTER_TTS_MODE", raising=False)
    monkeypatch.setattr(
        live_voice,
        "DEFAULT_KOKORO_MODEL_PATH",
        tmp_path / "missing-model.onnx",
    )
    monkeypatch.setattr(
        live_voice,
        "DEFAULT_KOKORO_VOICES_PATH",
        tmp_path / "missing-voices.bin",
    )

    with pytest.raises(PorterLiveVoiceError, match="requires Kokoro"):
        live_voice._build_default_tts_adapter()


def test_spoken_markers_are_split_into_enforced_pause_segments():
    segments = _split_spoken_segments(
        "I hear you... just so I understand the scale — roughly how much?"
    )

    assert segments == (
        ("I hear you", ELLIPSIS_PAUSE_MS),
        ("just so I understand the scale", EM_DASH_PAUSE_MS),
        ("roughly how much?", 0),
    )


def test_kokoro_renderer_inserts_silence_samples_for_pause_markers():
    class FakeKokoro:
        def create(self, text, **kwargs):
            return [0.25, 0.25], 1_000

    samples, sample_rate, segment_count = _synthesize_with_explicit_pauses(
        FakeKokoro(),
        text="First... second — third.",
        voice="af_heart",
        fallback_sample_rate=1_000,
    )

    assert sample_rate == 1_000
    assert segment_count == 3
    assert samples.count(0.0) == ELLIPSIS_PAUSE_MS + EM_DASH_PAUSE_MS
