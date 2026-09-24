from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, WebSocketException

from api.services.auth.depends import get_user_ws


class FakeWebSocket:
    close = AsyncMock()


async def test_websocket_auth_rejects_invalid_token_with_policy_close(monkeypatch):
    async def reject_token(_authorization, _api_key):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    monkeypatch.setattr("api.services.auth.depends.get_user", reject_token)

    with pytest.raises(WebSocketException) as exc_info:
        await get_user_ws(FakeWebSocket(), token="stale-token")

    assert exc_info.value.code == 1008
    assert exc_info.value.reason == "Invalid or expired token"
