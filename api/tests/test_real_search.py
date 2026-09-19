"""Integration tests for search and retrieval on real ingested catalog."""

import time

import pytest
from httpx import AsyncClient
from pipelines.ingest_catalog import run_ingestion


@pytest.fixture(autouse=True)
async def seed_staging_tracks(async_client: AsyncClient) -> None:
    """Seed sample staging tracks into database for search testing."""
    # Run a quick 30-track seed ingestion
    await run_ingestion(target_count=30, batch_size=30, resume=False)


@pytest.mark.asyncio
async def test_search_real_catalog_known_tracks(async_client: AsyncClient) -> None:
    """GET /tracks/search must return well-known classic tracks from staging catalog."""
    # Search for Bohemian Rhapsody
    res = await async_client.get("/tracks/search", params={"q": "Bohemian Rhapsody"})
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) > 0

    first = data["items"][0]
    assert "Bohemian Rhapsody" in first["title"]
    assert first["artist_name"] == "Queen"
    assert first["year"] == 1975
    assert "GBUM71029607" in first["isrcs"]
    assert "rock" in first["tags"]


@pytest.mark.asyncio
async def test_search_multiple_known_classics(async_client: AsyncClient) -> None:
    """Test searching for 5 classic tracks from the real catalog."""
    queries = [
        ("Nirvana", "Smells Like Teen Spirit"),
        ("Michael Jackson", "Billie Jean"),
        ("Fleetwood Mac", "Dreams"),
        ("The Beatles", "Hey Jude"),
        ("David Bowie", "Heroes"),
    ]

    for artist, title in queries:
        res = await async_client.get("/tracks/search", params={"q": title, "limit": 5})
        assert res.status_code == 200
        items = res.json()["items"]
        assert len(items) > 0, f"Expected results for query {title}"
        matched = any(artist.lower() in item["artist_name"].lower() for item in items)
        assert matched, f"Expected {artist} in results for {title}"


@pytest.mark.asyncio
async def test_search_real_catalog_latency_budget(async_client: AsyncClient) -> None:
    """GET /tracks/search response time must stay strictly < 50ms."""
    # Warm up
    await async_client.get("/tracks/search", params={"q": "Queen"})

    t0 = time.perf_counter()
    res = await async_client.get("/tracks/search", params={"q": "Queen", "limit": 20})
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert res.status_code == 200
    assert elapsed_ms < 50.0, f"Search took {elapsed_ms:.2f}ms, exceeding 50ms budget"


@pytest.mark.asyncio
async def test_get_staging_track_by_mbid(async_client: AsyncClient) -> None:
    """GET /tracks/{id} must retrieve staging track by MBID."""
    bohemian_mbid = "736233d6-dd07-4221-a5d2-09859f77f3a7"
    res = await async_client.get(f"/tracks/{bohemian_mbid}")
    assert res.status_code == 200

    data = res.json()
    assert data["mbid"] == bohemian_mbid
    assert data["title"] == "Bohemian Rhapsody"
    assert data["artist_name"] == "Queen"
    assert data["has_t"] is True
    assert "rock" in data["tags"]
