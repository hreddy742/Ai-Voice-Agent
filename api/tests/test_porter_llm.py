import asyncio
import os

import pytest
from aiohttp import web
from pydantic import BaseModel

from api.porter.llm import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    MockPorterLLMAdapter,
    OllamaLLMAdapter,
    PorterLLMInvalidResponseError,
    PorterLLMMessage,
    PorterLLMTimeoutError,
)
from api.porter.policy import SAFE_RATE_REPLACEMENT


class _StructuredAnswer(BaseModel):
    intent: str
    confidence: float


@pytest.fixture
async def ollama_mock_server():
    state = {"responses": [], "requests": []}

    async def chat(request):
        payload = await request.json()
        state["requests"].append(payload)
        response = state["responses"].pop(0)
        if response.get("delay"):
            await asyncio.sleep(response["delay"])
        return web.json_response(
            response.get("body", {}),
            status=response.get("status", 200),
        )

    app = web.Application()
    app.router.add_post("/api/chat", chat)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    socket = site._server.sockets[0]
    host, port = socket.getsockname()[:2]
    state["base_url"] = f"http://{host}:{port}"

    try:
        yield state
    finally:
        await runner.cleanup()


async def test_ollama_adapter_calls_local_ollama_compatible_server(ollama_mock_server):
    ollama_mock_server["responses"].append(
        {
            "body": {
                "model": "qwen3:4b",
                "message": {"role": "assistant", "content": "I can send this to review."},
            }
        }
    )
    adapter = OllamaLLMAdapter(base_url=ollama_mock_server["base_url"], model="qwen3:4b")

    response = await adapter.generate(
        [
            PorterLLMMessage(role="system", content="Use Porter-safe language."),
            PorterLLMMessage(role="user", content="Can Porter help?"),
        ]
    )

    assert response.allowed is True
    assert response.safe_text == "I can send this to review."
    assert ollama_mock_server["requests"][0]["model"] == "qwen3:4b"
    assert ollama_mock_server["requests"][0]["stream"] is False


async def test_ollama_adapter_defaults_to_local_qwen_model():
    adapter = OllamaLLMAdapter()

    expected_base_url = (
        "http://host.docker.internal:11434"
        if os.path.exists("/.dockerenv")
        else DEFAULT_OLLAMA_BASE_URL
    )
    assert adapter.base_url == expected_base_url
    assert adapter.model == DEFAULT_OLLAMA_MODEL


async def test_ollama_adapter_timeout_is_handled(ollama_mock_server):
    ollama_mock_server["responses"].append(
        {
            "delay": 0.2,
            "body": {"model": "qwen3:4b", "message": {"content": "Too late."}},
        }
    )
    adapter = OllamaLLMAdapter(
        base_url=ollama_mock_server["base_url"],
        timeout_seconds=0.01,
        retries=0,
    )

    with pytest.raises(PorterLLMTimeoutError):
        await adapter.generate([PorterLLMMessage(role="user", content="Hello")])


async def test_ollama_adapter_invalid_response_is_handled(ollama_mock_server):
    ollama_mock_server["responses"].append({"body": {"model": "qwen3:4b"}})
    adapter = OllamaLLMAdapter(base_url=ollama_mock_server["base_url"], retries=0)

    with pytest.raises(PorterLLMInvalidResponseError):
        await adapter.generate([PorterLLMMessage(role="user", content="Hello")])


async def test_policy_engine_receives_output_before_final_response(ollama_mock_server):
    ollama_mock_server["responses"].append(
        {
            "body": {
                "model": "qwen3:4b",
                "message": {"role": "assistant", "content": "Your rate will be 2%."},
            }
        }
    )
    adapter = OllamaLLMAdapter(base_url=ollama_mock_server["base_url"], retries=0)

    response = await adapter.generate([PorterLLMMessage(role="user", content="Rates?")])

    assert response.allowed is False
    assert response.raw_text == "Your rate will be 2%."
    assert response.safe_text == SAFE_RATE_REPLACEMENT
    assert [v.violation_type for v in response.policy_result.violations] == ["rate_claim"]


async def test_mock_adapter_also_cannot_bypass_policy():
    response = await MockPorterLLMAdapter("Funding is guaranteed.").generate(
        [PorterLLMMessage(role="user", content="Can you fund me?")]
    )

    assert response.allowed is False
    assert "guaranteed" not in response.safe_text.lower()


async def test_structured_output_is_validated_with_pydantic(ollama_mock_server):
    ollama_mock_server["responses"].append(
        {
            "body": {
                "model": "qwen3:4b",
                "message": {
                    "role": "assistant",
                    "content": '{"intent": "callback_requested", "confidence": 0.91}',
                },
            }
        }
    )
    adapter = OllamaLLMAdapter(base_url=ollama_mock_server["base_url"], retries=0)

    structured = await adapter.generate_structured(
        [PorterLLMMessage(role="user", content="Call me later.")],
        _StructuredAnswer,
    )

    assert structured.intent == "callback_requested"
    assert structured.confidence == 0.91
    assert ollama_mock_server["requests"][0]["format"] == "json"
