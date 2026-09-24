"""Local semantic recovery for ambiguous Porter cold-call turns."""

from __future__ import annotations

import os
import json
from typing import Literal, Protocol, Sequence

from pydantic import BaseModel, Field, ValidationError

from api.porter.cold_call_flow import PorterColdCallStage
from api.porter.llm import OllamaLLMAdapter, PorterLLMError, PorterLLMMessage


PORTER_SEMANTIC_FALLBACK_ENABLED_ENV = "PORTER_SEMANTIC_FALLBACK_ENABLED"
PORTER_SEMANTIC_MODEL_ENV = "PORTER_SEMANTIC_MODEL"
PORTER_SEMANTIC_TIMEOUT_SECONDS_ENV = "PORTER_SEMANTIC_TIMEOUT_SECONDS"

DEFAULT_SEMANTIC_MODEL = "qwen3:4b"
DEFAULT_SEMANTIC_TIMEOUT_SECONDS = 2.0
MINIMUM_SEMANTIC_CONFIDENCE = 0.80

CanonicalUtterance = Literal[
    "yes",
    "no",
    "not interested",
    "what do you do?",
    "what are your rates?",
    "how fast is funding?",
    "what is invoice factoring?",
    "are you an ai?",
    "talk to a person",
    "we have no business",
    "we already factor invoices",
    "we do not factor invoices",
    "customers pay upfront",
    "please repeat that",
    "unknown",
]


class SemanticInterpretation(BaseModel):
    canonical_utterance: CanonicalUtterance
    confidence: float = Field(ge=0.0, le=1.0)


class StructuredInterpreter(Protocol):
    async def generate_structured(
        self,
        messages: Sequence[PorterLLMMessage],
        schema: type[SemanticInterpretation],
    ) -> SemanticInterpretation: ...


_DEFAULT_INTERPRETER: OllamaLLMAdapter | None = None


def semantic_fallback_enabled() -> bool:
    return (os.getenv(PORTER_SEMANTIC_FALLBACK_ENABLED_ENV) or "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }


async def interpret_ambiguous_turn(
    *,
    user_text: str,
    stage: PorterColdCallStage,
    interpreter: StructuredInterpreter | None = None,
) -> SemanticInterpretation | None:
    """Return a safe canonical turn, or None when the caller's meaning is uncertain."""
    if not semantic_fallback_enabled():
        return None

    messages = [
        PorterLLMMessage(
            role="system",
            content=(
                "Classify one noisy phone-call transcript for a Porter Capital cold call. "
                "Return exactly one JSON object with canonical_utterance and confidence. "
                "canonical_utterance MUST be one of the allowed values, never the caller's "
                "original wording. Examples: 'sounds good, keep going' becomes "
                "{\"canonical_utterance\":\"yes\",\"confidence\":0.95}; 'not for me' "
                "becomes {\"canonical_utterance\":\"not interested\",\"confidence\":0.95}; "
                "'uh' becomes {\"canonical_utterance\":\"unknown\",\"confidence\":0.1}. "
                "Use unknown for filler, garbled speech, partial phrases, or anything you "
                "cannot safely infer. Never create a sales response or infer facts."
            ),
        ),
        PorterLLMMessage(
            role="user",
            content=(
                f"Current stage: {stage.value}. Caller transcript: {user_text!r}. "
                "Allowed canonical_utterance values: yes, no, not interested, what do you do?, "
                "what are your rates?, how fast is funding?, what is invoice factoring?, "
                "are you an ai?, talk to a person, we have no business, we already factor "
                "invoices, we do not factor invoices, customers pay upfront, please repeat that, unknown."
            ),
        ),
    ]
    try:
        if interpreter is not None:
            result = await interpreter.generate_structured(messages, SemanticInterpretation)
        else:
            response = await _default_interpreter().generate(
                messages,
                format=SemanticInterpretation.model_json_schema(),
                think=False,
            )
            result = _interpret_model_json(response.safe_text)
    except (PorterLLMError, json.JSONDecodeError, ValidationError):
        return None
    if result.canonical_utterance == "unknown" or result.confidence < MINIMUM_SEMANTIC_CONFIDENCE:
        return None
    return result


def _default_interpreter() -> OllamaLLMAdapter:
    global _DEFAULT_INTERPRETER
    if _DEFAULT_INTERPRETER is None:
        _DEFAULT_INTERPRETER = OllamaLLMAdapter(
            model=os.getenv(PORTER_SEMANTIC_MODEL_ENV) or DEFAULT_SEMANTIC_MODEL,
            timeout_seconds=_semantic_timeout_seconds(),
            retries=0,
        )
    return _DEFAULT_INTERPRETER


def _interpret_model_json(raw_text: str) -> SemanticInterpretation:
    payload = json.loads(raw_text)
    if not isinstance(payload, dict):
        raise PorterLLMError("Semantic model response must be a JSON object.")
    raw_intent = str(payload.get("canonical_utterance") or "").strip().lower()
    aliases = {
        "keep going": "yes",
        "go ahead": "yes",
        "continue": "yes",
        "sounds good": "yes",
        "not for me": "not interested",
        "no thanks": "not interested",
    }
    canonical = aliases.get(raw_intent, raw_intent)
    confidence = payload.get("confidence", 0.85 if canonical != raw_intent else 0.0)
    return SemanticInterpretation.model_validate(
        {"canonical_utterance": canonical, "confidence": confidence}
    )


def _semantic_timeout_seconds() -> float:
    value = os.getenv(PORTER_SEMANTIC_TIMEOUT_SECONDS_ENV)
    if not value:
        return DEFAULT_SEMANTIC_TIMEOUT_SECONDS
    try:
        timeout = float(value)
    except ValueError:
        return DEFAULT_SEMANTIC_TIMEOUT_SECONDS
    return timeout if timeout > 0 else DEFAULT_SEMANTIC_TIMEOUT_SECONDS
