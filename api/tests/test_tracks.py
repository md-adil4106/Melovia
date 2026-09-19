"""Tests for track search and track detail endpoints."""

import time

import pytest
from httpx import AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_search_tracks_success(async_client: AsyncClient) -> None:
    """GET /tracks/search must return matching tracks and adhere to limit."""
    response = await async_client.get("/tracks/search", params={"q": "neon", "limit": 10})
    assert response.status_code == 200

    data = response.json()
    assert data["query"] == "neon"
    assert data["limit"] == 10
    assert isinstance(data["items"], list)
    assert len(data["items"]) <= 10
    assert len(data["items"]) > 0

    first_item = data["items"][0]
    assert "id" in first_item
    assert "title" in first_item
    assert "artist_name" in first_item
    assert "popularity_pct" in first_item
    assert "has_a" in first_item
    assert "has_t" in first_item
    assert "scalars" in first_item


@pytest.mark.asyncio
async def test_search_tracks_case_insensitive(async_client: AsyncClient) -> None:
    """GET /tracks/search must return identical results regardless of query casing."""
    res_lower = await async_client.get("/tracks/search", params={"q": "drift"})
    res_upper = await async_client.get("/tracks/search", params={"q": "DRIFT"})

    assert res_lower.status_code == 200
    assert res_upper.status_code == 200

    items_lower = res_lower.json()["items"]
    items_upper = res_upper.json()["items"]

    assert len(items_lower) == len(items_upper)
    if items_lower:
        assert items_lower[0]["id"] == items_upper[0]["id"]


@pytest.mark.asyncio
async def test_search_tracks_latency_budget(async_client: AsyncClient) -> None:
    """Search query budget: response time must be < 50ms for limit=20."""
    # Warm up call
    await async_client.get("/tracks/search", params={"q": "starlight", "limit": 20})

    start_time = time.perf_counter()
    response = await async_client.get("/tracks/search", params={"q": "starlight", "limit": 20})
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    assert response.status_code == 200
    # Search is in-memory over 3k tracks, expected < 15ms; budget is 50ms
    assert elapsed_ms < 50.0, f"Search took {elapsed_ms:.2f}ms, exceeding 50ms budget"


@pytest.mark.asyncio
async def test_search_tracks_validation_error(async_client: AsyncClient) -> None:
    """Search query with empty q parameter must return 422 with error envelope."""
    response = await async_client.get("/tracks/search", params={"q": ""})
    assert response.status_code == 422

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_get_track_by_id_success(async_client: AsyncClient) -> None:
    """GET /tracks/{id} must return complete track metadata including scalars and tags."""
    # First search to get a valid track ID
    search_res = await async_client.get("/tracks/search", params={"q": "a", "limit": 1})
    assert search_res.status_code == 200
    valid_track = search_res.json()["items"][0]
    track_id = valid_track["id"]

    response = await async_client.get(f"/tracks/{track_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == track_id
    assert data["title"] == valid_track["title"]
    assert data["artist_name"] == valid_track["artist_name"]
    assert "track_idx" in data
    assert "scalars" in data
    assert data["scalars"] is not None
    assert "bpm" in data["scalars"]
    assert "energy" in data["scalars"]
    assert isinstance(data["tags"], list)
    assert len(data["tags"]) > 0


@pytest.mark.asyncio
async def test_get_track_by_id_missing_channel_a(async_client: AsyncClient) -> None:
    """Verify that tracks with missing channel a accurately report has_a: False."""
    store = getattr(app.state, "catalog_store", None)
    assert store is not None

    # Find a track with has_a == False
    missing_indices = [i for i, has_a in enumerate(store.mask_a) if not has_a]
    assert len(missing_indices) > 0

    target_id = store.get_id(missing_indices[0])
    response = await async_client.get(f"/tracks/{target_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["has_a"] is False
    assert data["has_t"] is True


@pytest.mark.asyncio
async def test_get_track_by_id_not_found(async_client: AsyncClient) -> None:
    """GET /tracks/{id} with unknown ID must return 404 with error envelope."""
    response = await async_client.get("/tracks/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"
    assert "request_id" in data["error"]


@pytest.mark.asyncio
async def test_tracks_catalog_unmounted_returns_503(async_client: AsyncClient) -> None:
    """When catalog is unmounted, track endpoints must return 503 CATALOG_UNAVAILABLE."""
    prev_store = getattr(app.state, "catalog_store", None)
    app.state.catalog_store = None
    try:
        res = await async_client.get("/tracks/search", params={"q": "test"})
        assert res.status_code == 503
        data = res.json()
        assert data["error"]["code"] == "CATALOG_UNAVAILABLE"
    finally:
        app.state.catalog_store = prev_store
