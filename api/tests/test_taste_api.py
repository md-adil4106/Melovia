"""Integration tests for Taste Profile, Blindspots, and ListenBrainz API endpoints (Phase 11)."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.recsys import CatalogStore


@pytest.fixture
def test_app():
    app = create_app()
    repo_root = Path(__file__).resolve().parent.parent.parent
    bundle_path = repo_root / "data" / "bundles" / "v1"
    store = CatalogStore.load(bundle_path)
    app.state.catalog_store = store
    return app


@pytest.mark.asyncio
async def test_get_taste_profile_endpoint(test_app):
    """GET /taste/profile returns 200 with complete TasteProfileResponse schema."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://testserver"
    ) as client:
        # Pass 3 seeds -> low confidence
        seed_id_0 = test_app.state.catalog_store.get_id(0)
        seed_id_1 = test_app.state.catalog_store.get_id(1)
        seed_id_2 = test_app.state.catalog_store.get_id(2)

        resp = await client.get(
            f"/taste/profile?seed_ids={seed_id_0}&seed_ids={seed_id_1}&seed_ids={seed_id_2}"
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["known_track_count"] == 3
        assert data["confidence"] == "low"
        assert "breadth" in data["dimensions"]
        assert "rarity" in data["dimensions"]
        assert "cohesion" in data["dimensions"]
        assert "range" in data["dimensions"]
        assert "archetype" in data
        assert "id" in data["archetype"]
        assert "name" in data["archetype"]
        assert len(data["region_exposures"]) == 24


@pytest.mark.asyncio
async def test_get_taste_blindspots_endpoint(test_app):
    """GET /taste/blindspots returns 200 with ranked blindspots and bridge tags."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://testserver"
    ) as client:
        seed_id_0 = test_app.state.catalog_store.get_id(0)
        resp = await client.get(f"/taste/blindspots?seed_ids={seed_id_0}")
        assert resp.status_code == 200
        data = resp.json()

        assert "blindspots" in data
        assert isinstance(data["blindspots"], list)
        if data["blindspots"]:
            first = data["blindspots"][0]
            assert "region_id" in first
            assert "adjacency_score" in first
            assert "rank_score" in first
            assert "bridge_tags" in first


@pytest.mark.asyncio
async def test_recommendations_with_region_id(test_app):
    """POST /recommendations with region_id restricts candidates and attaches bridge signals."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://testserver"
    ) as client:
        seed_id_0 = test_app.state.catalog_store.get_id(0)
        target_region = 1

        payload = {
            "seed_track_ids": [seed_id_0],
            "region_id": target_region,
            "n": 10,
            "discovery": 0.35,
        }
        resp = await client.post("/recommendations", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert len(data["items"]) > 0
        first_item = data["items"][0]
        # Verify bridge signals
        assert first_item["signals"] is not None
        assert first_item["signals"]["region_id"] == target_region
        assert "bridge_region_name" in first_item["signals"]
        assert "bridge_reason" in first_item["signals"]


@pytest.mark.asyncio
async def test_import_listenbrainz_mocked(test_app):
    """POST /profile/import-listenbrainz maps upstream recordings to catalog tracks."""
    mock_listenbrainz_response = {
        "payload": {
            "count": 2,
            "listens": [
                {
                    "track_metadata": {
                        "track_name": test_app.state.catalog_store.get_track_dict(0)["title"],
                        "artist_name": test_app.state.catalog_store.get_track_dict(0)[
                            "artist_name"
                        ],
                        "additional_info": {
                            "recording_mbid": "00000000-0000-0000-0000-000000000001",
                        },
                    }
                }
            ],
        }
    }

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json = lambda: mock_listenbrainz_response

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://testserver"
        ) as client:
            resp = await client.post(
                "/profile/import-listenbrainz",
                json={"username": "testuser", "limit": 10},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["username"] == "testuser"
            assert data["total_listens"] == 1
