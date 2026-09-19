"""Tests for health check endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint_returns_expected_payload(async_client: AsyncClient) -> None:
    """GET /health must return 200 with status, version, and catalog: null."""
    response = await async_client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert data["catalog"] is None

    # Verify X-Request-ID is attached
    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) > 0


@pytest.mark.asyncio
async def test_health_endpoint_preserves_incoming_request_id(async_client: AsyncClient) -> None:
    """Incoming X-Request-ID must be preserved in the response header."""
    custom_id = "test-custom-request-id-12345"
    response = await async_client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == custom_id
