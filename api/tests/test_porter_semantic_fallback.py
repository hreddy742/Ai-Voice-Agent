from __future__ import annotations

import pytest

from api.porter.cold_call_flow import PorterColdCallStage
from api.porter.semantic_fallback import (
    PORTER_SEMANTIC_FALLBACK_ENABLED_ENV,
    SemanticInterpretation,
    interpret_ambiguous_turn,
)


class _FakeInterpreter:
    def __init__(self, result: SemanticInterpretation) -> None:
        self.result = result
        self.messages = []

    async def generate_structured(self, messages, schema):
        self.messages = list(messages)
        assert schema is SemanticInterpretation
        return self.result


@pytest.mark.asyncio
async def test_semantic_fallback_recovers_a_confident_indirect_yes(monkeypatch):
    monkeypatch.setenv(PORTER_SEMANTIC_FALLBACK_ENABLED_ENV, "true")
    interpreter = _FakeInterpreter(
        SemanticInterpretation(canonical_utterance="yes", confidence=0.96)
    )

    result = await interpret_ambiguous_turn(
        user_text="sounds good to me, keep going",
        stage=PorterColdCallStage.PITCH,
        interpreter=interpreter,
    )

    assert result is not None
    assert result.canonical_utterance == "yes"
    assert "Current stage: pitch" in interpreter.messages[1].content


@pytest.mark.asyncio
async def test_semantic_fallback_refuses_low_confidence_and_unknown_results(monkeypatch):
    monkeypatch.setenv(PORTER_SEMANTIC_FALLBACK_ENABLED_ENV, "true")
    low_confidence = _FakeInterpreter(
        SemanticInterpretation(canonical_utterance="yes", confidence=0.50)
    )
    unknown = _FakeInterpreter(
        SemanticInterpretation(canonical_utterance="unknown", confidence=0.99)
    )

    assert await interpret_ambiguous_turn(
        user_text="uh",
        stage=PorterColdCallStage.PITCH,
        interpreter=low_confidence,
    ) is None
    assert await interpret_ambiguous_turn(
        user_text="ES going on",
        stage=PorterColdCallStage.PITCH,
        interpreter=unknown,
    ) is None


@pytest.mark.asyncio
async def test_semantic_fallback_is_off_without_explicit_local_runtime_setting(monkeypatch):
    monkeypatch.delenv(PORTER_SEMANTIC_FALLBACK_ENABLED_ENV, raising=False)
    interpreter = _FakeInterpreter(
        SemanticInterpretation(canonical_utterance="yes", confidence=0.99)
    )

    result = await interpret_ambiguous_turn(
        user_text="yes, I guess",
        stage=PorterColdCallStage.PITCH,
        interpreter=interpreter,
    )

    assert result is None
    assert interpreter.messages == []
