from api.porter.runtime import (
    APPROVED_VOICE_SCRIPT_MAP,
    STARTUP_VOICE_SCRIPT_NAMES,
    inspect_porter_voice_runtime,
    prewarm_porter_voice_scripts,
)
from api.porter.tts import StubTTSAdapter


def test_porter_runtime_readiness_reports_components():
    readiness = inspect_porter_voice_runtime()

    assert readiness.recommended_target_ms == 500
    assert {component.name for component in readiness.components} == {"stt", "tts", "llm"}
    assert readiness.fast_voice_mode is True
    assert any("Voicebox" in note for note in readiness.notes)


def test_porter_runtime_reports_pocket_tts(monkeypatch):
    monkeypatch.setenv("PORTER_TTS_MODE", "pocket")

    readiness = inspect_porter_voice_runtime()
    tts = next(component for component in readiness.components if component.name == "tts")

    assert tts.provider == "pocket-tts"
    assert tts.model == "pocket-tts-v2"
    assert tts.ready is True


async def test_prewarm_porter_voice_scripts_generates_and_hits_cache():
    first = await prewarm_porter_voice_scripts(
        script_names=("opener", "rates"),
        tts_adapter=StubTTSAdapter(),
    )
    second = await prewarm_porter_voice_scripts(
        script_names=("opener", "rates"),
        tts_adapter=StubTTSAdapter(),
    )

    assert first.warmed_count == 2
    assert first.cache_hit_count >= 0
    assert second.warmed_count == 2
    assert second.cache_hit_count == 2
    assert all(script.tts for script in second.scripts)


def test_prewarm_script_map_covers_static_fast_call_responses():
    assert "funding_speed_answer" in APPROVED_VOICE_SCRIPT_MAP
    assert "factoring_answer" in APPROVED_VOICE_SCRIPT_MAP
    assert "cash_flow_question" in APPROVED_VOICE_SCRIPT_MAP
    assert "monthly_invoicing_question" in APPROVED_VOICE_SCRIPT_MAP


def test_startup_prewarm_is_limited_to_the_critical_call_path():
    assert len(STARTUP_VOICE_SCRIPT_NAMES) < len(APPROVED_VOICE_SCRIPT_MAP)
    assert all(name in APPROVED_VOICE_SCRIPT_MAP for name in STARTUP_VOICE_SCRIPT_NAMES)


async def test_prewarm_porter_voice_scripts_rejects_unknown_script():
    try:
        await prewarm_porter_voice_scripts(
            script_names=("opener", "unknown"),
            tts_adapter=StubTTSAdapter(),
        )
    except ValueError as exc:
        assert "unknown" in str(exc)
    else:
        raise AssertionError("Expected unknown script names to be rejected.")
