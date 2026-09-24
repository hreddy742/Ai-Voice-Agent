import asyncio
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal, Sequence, TypeVar

import aiohttp
from pydantic import BaseModel, ValidationError

from api.porter.policy import PorterPolicyEngine, PolicyCheckResult


PORTER_OLLAMA_BASE_URL_ENV = "PORTER_OLLAMA_BASE_URL"
PORTER_OLLAMA_MODEL_ENV = "PORTER_OLLAMA_MODEL"
PORTER_OLLAMA_TIMEOUT_SECONDS_ENV = "PORTER_OLLAMA_TIMEOUT_SECONDS"

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5:0.5b"
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 90.0
DEFAULT_OLLAMA_RETRIES = 1
DEFAULT_OLLAMA_KEEP_ALIVE = "15m"
DEFAULT_OLLAMA_NUM_PREDICT = 32

Role = Literal["system", "user", "assistant"]
StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


class PorterLLMError(RuntimeError):
    pass


class PorterLLMTimeoutError(PorterLLMError):
    pass


class PorterLLMInvalidResponseError(PorterLLMError):
    pass


@dataclass(frozen=True)
class PorterLLMMessage:
    role: Role
    content: str

    def to_ollama(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass(frozen=True)
class PorterLLMResponse:
    raw_text: str
    safe_text: str
    allowed: bool
    model: str
    policy_result: PolicyCheckResult
    raw_response: dict[str, Any]


class PorterLLMAdapter(ABC):
    @abstractmethod
    async def generate(self, messages: Sequence[PorterLLMMessage]) -> PorterLLMResponse:
        pass


class OllamaLLMAdapter(PorterLLMAdapter):
    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        retries: int = DEFAULT_OLLAMA_RETRIES,
        policy_engine: PorterPolicyEngine | None = None,
    ) -> None:
        self.base_url = (
            base_url
            or os.getenv(PORTER_OLLAMA_BASE_URL_ENV)
            or _default_ollama_base_url()
        ).rstrip("/")
        self.model = model or os.getenv(PORTER_OLLAMA_MODEL_ENV) or DEFAULT_OLLAMA_MODEL
        self.timeout_seconds = _timeout_from_env(timeout_seconds)
        self.retries = retries
        self.policy_engine = policy_engine or PorterPolicyEngine()
        self._session: aiohttp.ClientSession | None = None

    async def generate(
        self,
        messages: Sequence[PorterLLMMessage],
        *,
        format: str | dict[str, Any] | None = None,
        think: bool | None = None,
    ) -> PorterLLMResponse:
        if not messages:
            raise PorterLLMInvalidResponseError("At least one message is required.")

        raw_response = await self._post_chat(messages, format=format, think=think)
        raw_text = _extract_ollama_content(raw_response)
        policy_result = self.policy_engine.check_response(raw_text)
        return PorterLLMResponse(
            raw_text=raw_text,
            safe_text=policy_result.safe_text,
            allowed=policy_result.allowed,
            model=str(raw_response.get("model") or self.model),
            policy_result=policy_result,
            raw_response=raw_response,
        )

    async def generate_structured(
        self,
        messages: Sequence[PorterLLMMessage],
        schema: type[StructuredModel],
    ) -> StructuredModel:
        response = await self.generate(messages, format="json")
        try:
            payload = json.loads(response.safe_text)
        except json.JSONDecodeError as exc:
            raise PorterLLMInvalidResponseError("Ollama returned invalid JSON.") from exc

        try:
            return schema.model_validate(payload)
        except ValidationError as exc:
            raise PorterLLMInvalidResponseError(
                "Ollama JSON did not match the expected schema."
            ) from exc

    async def _post_chat(
        self,
        messages: Sequence[PorterLLMMessage],
        *,
        format: str | dict[str, Any] | None,
        think: bool | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [message.to_ollama() for message in messages],
            "stream": False,
            "keep_alive": DEFAULT_OLLAMA_KEEP_ALIVE,
            "options": {
                "temperature": 0.0,
                "num_predict": DEFAULT_OLLAMA_NUM_PREDICT,
                "num_ctx": 1024,
            },
        }
        if format:
            payload["format"] = format
        if think is not None:
            payload["think"] = think

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                session = self._get_session(timeout)
                async with session.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                ) as response:
                    body = await response.text()
                    if response.status >= 500 and attempt < self.retries:
                        last_error = PorterLLMError(
                            f"Ollama transient error {response.status}: {body}"
                        )
                        await asyncio.sleep(0.1 * (attempt + 1))
                        continue
                    if response.status >= 400:
                        raise PorterLLMError(
                            f"Ollama request failed {response.status}: {body}"
                        )
                    try:
                        parsed = json.loads(body)
                    except json.JSONDecodeError as exc:
                        raise PorterLLMInvalidResponseError(
                            "Ollama response was not valid JSON."
                        ) from exc
                    if not isinstance(parsed, dict):
                        raise PorterLLMInvalidResponseError(
                            "Ollama response must be a JSON object."
                        )
                    return parsed
            except TimeoutError as exc:
                raise PorterLLMTimeoutError("Ollama request timed out.") from exc
            except aiohttp.ClientError as exc:
                last_error = exc
                if attempt < self.retries:
                    await asyncio.sleep(0.1 * (attempt + 1))
                    continue
                raise PorterLLMError(f"Ollama request failed: {exc}") from exc

        raise PorterLLMError(f"Ollama request failed: {last_error}")

    def _get_session(self, timeout: aiohttp.ClientTimeout) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session


class MockPorterLLMAdapter(PorterLLMAdapter):
    def __init__(
        self,
        response_text: str,
        *,
        model: str = "mock-porter-llm",
        policy_engine: PorterPolicyEngine | None = None,
    ) -> None:
        self.response_text = response_text
        self.model = model
        self.policy_engine = policy_engine or PorterPolicyEngine()

    async def generate(self, messages: Sequence[PorterLLMMessage]) -> PorterLLMResponse:
        if not messages:
            raise PorterLLMInvalidResponseError("At least one message is required.")
        policy_result = self.policy_engine.check_response(self.response_text)
        return PorterLLMResponse(
            raw_text=self.response_text,
            safe_text=policy_result.safe_text,
            allowed=policy_result.allowed,
            model=self.model,
            policy_result=policy_result,
            raw_response={"model": self.model, "message": {"content": self.response_text}},
        )


def _extract_ollama_content(response: dict[str, Any]) -> str:
    message = response.get("message")
    if not isinstance(message, dict):
        raise PorterLLMInvalidResponseError("Ollama response missing message object.")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise PorterLLMInvalidResponseError("Ollama response missing message content.")
    return content.strip()


def _default_ollama_base_url() -> str:
    if os.path.exists("/.dockerenv"):
        return "http://host.docker.internal:11434"
    return DEFAULT_OLLAMA_BASE_URL


def _timeout_from_env(timeout_seconds: float | None) -> float:
    if timeout_seconds is not None:
        return timeout_seconds
    env_value = os.getenv(PORTER_OLLAMA_TIMEOUT_SECONDS_ENV)
    if not env_value:
        return DEFAULT_OLLAMA_TIMEOUT_SECONDS
    try:
        parsed = float(env_value)
    except ValueError as exc:
        raise PorterLLMInvalidResponseError(
            f"{PORTER_OLLAMA_TIMEOUT_SECONDS_ENV} must be a number."
        ) from exc
    if parsed <= 0:
        raise PorterLLMInvalidResponseError(
            f"{PORTER_OLLAMA_TIMEOUT_SECONDS_ENV} must be greater than zero."
        )
    return parsed
