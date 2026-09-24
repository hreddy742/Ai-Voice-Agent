from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from api.app import app


@pytest.mark.asyncio
async def test_health_does_not_resolve_tunnel_for_local_backend_endpoint():
    with (
        patch("api.constants.BACKEND_API_ENDPOINT", "http://localhost:18000"),
        patch(
            "api.utils.common.TunnelURLProvider.get_tunnel_urls",
            new_callable=AsyncMock,
        ) as get_tunnel_urls,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["backend_api_endpoint"] == "http://localhost:18000"
    assert data["tunnel_url"] is None
    get_tunnel_urls.assert_not_awaited()
