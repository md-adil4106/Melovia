import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

import pytest  # noqa: E402
from fixtures.make_mock_catalog import generate_mock_catalog  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.main import app  # noqa: E402
from app.recsys import CatalogStore  # noqa: E402


@pytest.fixture(scope="module")
def mock_catalog_store(tmp_path_factory: pytest.TempPathFactory) -> CatalogStore:
    """Generate a clean deterministic mock catalog bundle for Why API tests."""
    bundle_dir = tmp_path_factory.mktemp("mock_bundle_why_test")
    generate_mock_catalog(bundle_dir)
    return CatalogStore.load(bundle_dir)


@pytest.mark.asyncio
async def test_get_recommendation_why_endpoint_success(mock_catalog_store: CatalogStore) -> None:
    """Test successful retrieval of why explanation for a recommended item."""
    app.state.catalog_store = mock_catalog_store
    seed_id = mock_catalog_store.get_id(10)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Generate recommendations
        res = await client.post(
            "/recommendations",
            json={
                "seed_track_ids": [seed_id],
                "n": 10,
                "discovery": 0.40,
                "include_signals": True,
            },
        )
        assert res.status_code == 200
        rec_data = res.json()
        candidate_set_id = rec_data["candidate_set_id"]
        assert len(rec_data["items"]) >= 1

        target_item = rec_data["items"][0]
        track_id = target_item["track"]["id"]

        # Also verify discovery_value is present on RecommendedTrackItem
        assert "discovery_value" in target_item
        assert isinstance(target_item["discovery_value"], (int, float))

        # 2. Query Why explanation
        why_res = await client.get(f"/recommendations/{candidate_set_id}/items/{track_id}/why")
        assert why_res.status_code == 200
        why_data = why_res.json()

        assert why_data["candidate_set_id"] == candidate_set_id
        assert why_data["track_id"] == track_id
        assert "signals" in why_data
        assert "reasons" in why_data
        assert len(why_data["reasons"]) >= 1
        assert len(why_data["reasons"]) <= 4
        assert why_data["discovery_value"] == 0.40

        # Check reason schema
        first_reason = why_data["reasons"][0]
        assert "id" in first_reason
        assert "text" in first_reason
        assert len(first_reason["text"]) > 0
        assert "signal_keys" in first_reason
        assert len(first_reason["signal_keys"]) >= 1
        assert "evidence" in first_reason
        assert "weight" in first_reason


@pytest.mark.asyncio
async def test_get_recommendation_why_expired_or_invalid_candidate_set(
    mock_catalog_store: CatalogStore,
) -> None:
    """Querying why with a non-existent candidate set ID must return 404 CANDIDATE_SET_EXPIRED."""
    app.state.catalog_store = mock_catalog_store
    track_id = mock_catalog_store.get_id(1)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(f"/recommendations/non-existent-set-id/items/{track_id}/why")
        assert res.status_code == 404
        data = res.json()
        assert data["error"]["code"] == "CANDIDATE_SET_EXPIRED"


@pytest.mark.asyncio
async def test_get_recommendation_why_track_not_in_pool(
    mock_catalog_store: CatalogStore,
) -> None:
    """Querying why with a track ID not in the candidate pool must return 404 TRACK_NOT_FOUND."""
    app.state.catalog_store = mock_catalog_store
    seed_id = mock_catalog_store.get_id(5)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/recommendations",
            json={"seed_track_ids": [seed_id], "n": 5},
        )
        assert res.status_code == 200
        candidate_set_id = res.json()["candidate_set_id"]

        # Query with seed track itself (seeds are excluded from candidate pool)
        why_res = await client.get(f"/recommendations/{candidate_set_id}/items/{seed_id}/why")
        assert why_res.status_code == 404
        assert why_res.json()["error"]["code"] == "TRACK_NOT_FOUND"
