"""Tests for health check endpoint."""

import pytest
from httpx import AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint_with_mounted_catalog(async_client: AsyncClient) -> None:
    """GET /health must return 200 with status, version, and catalog details."""
    response = await async_client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"

    # Catalog is mounted in test fixture
    assert data["catalog"] is not None
    assert data["catalog"]["version"] == "v1"
    assert data["catalog"]["track_count"] == 3000
    assert data["catalog"]["plan"] == "mock"

    # Verify X-Request-ID is attached
    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) > 0


@pytest.mark.asyncio
async def test_health_endpoint_with_unmounted_catalog(async_client: AsyncClient) -> None:
    """GET /health must return catalog: null when catalog is unmounted."""
    prev_store = getattr(app.state, "catalog_store", None)
    app.state.catalog_store = None
    try:
        response = await async_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["catalog"] is None
    finally:
        app.state.catalog_store = prev_store


@pytest.mark.asyncio
async def test_health_endpoint_preserves_incoming_request_id(async_client: AsyncClient) -> None:
    """Incoming X-Request-ID must be preserved in the response header."""
    custom_id = "test-custom-request-id-12345"
    response = await async_client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == custom_id
