"""Integration tests for playlist sequencing API endpoint (POST /playlist/sequence)."""

import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

import pytest  # noqa: E402
from fixtures.make_mock_catalog import generate_mock_catalog  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.main import app  # noqa: E402
from app.recsys import CatalogStore  # noqa: E402


@pytest.fixture
def mock_catalog(tmp_path: Path) -> CatalogStore:
    generate_mock_catalog(tmp_path)
    return CatalogStore.load(tmp_path)


@pytest.mark.asyncio
async def test_playlist_sequence_with_candidate_set(mock_catalog: CatalogStore) -> None:
    """Verify playlist sequencing from a cached candidate set."""
    app.state.catalog_store = mock_catalog
    seeds = mock_catalog.track_ids[:3]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Generate recommendations to populate candidate cache
        rec_res = await client.post(
            "/recommendations",
            json={"seed_track_ids": seeds, "n": 30, "discovery": 0.35},
        )
        assert rec_res.status_code == 200
        cand_set_id = rec_res.json()["candidate_set_id"]

        # 2. Sequence playlist with Build arc
        seq_res = await client.post(
            "/playlist/sequence",
            json={
                "candidate_set_id": cand_set_id,
                "arc": "build",
                "length": 15,
            },
        )
        assert seq_res.status_code == 200
        data = seq_res.json()

        assert len(data["tracks"]) == 15
        assert len(data["transitions"]) == 14
        assert len(data["arc_points"]) == 15
        assert data["total_cost"] > 0
        assert data["mean_transition_cost"] > 0
        assert data["arc_correlation"] >= 0.50
        assert "tempo" in data["active_weights"]
        assert "energy" in data["active_weights"]

        # Check track metadata formatting
        first_track = data["tracks"][0]["track"]
        assert "id" in first_track
        assert "title" in first_track
        assert "artist_name" in first_track
        assert "scalars" in first_track

        # Check transition details
        first_trans = data["transitions"][0]
        assert "from_track_id" in first_trans
        assert "to_track_id" in first_trans
        assert "cost" in first_trans
        assert "same_artist" in first_trans


@pytest.mark.asyncio
async def test_playlist_sequence_with_explicit_track_ids(mock_catalog: CatalogStore) -> None:
    """Verify playlist sequencing with explicit list of track UUIDs."""
    app.state.catalog_store = mock_catalog
    track_ids = mock_catalog.track_ids[:12]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        seq_res = await client.post(
            "/playlist/sequence",
            json={
                "track_ids": track_ids,
                "arc": "wind_down",
                "length": 10,
            },
        )
        assert seq_res.status_code == 200
        data = seq_res.json()
        assert len(data["tracks"]) == 10
        assert len(data["transitions"]) == 9
        assert len(data["arc_points"]) == 10


@pytest.mark.asyncio
async def test_playlist_sequence_validation_errors(mock_catalog: CatalogStore) -> None:
    """Verify error handling for invalid payloads."""
    app.state.catalog_store = mock_catalog

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Neither candidate_set_id nor track_ids provided
        res_empty = await client.post(
            "/playlist/sequence",
            json={"arc": "build", "length": 10},
        )
        assert res_empty.status_code == 422

        # Nonexistent candidate set ID
        res_not_found = await client.post(
            "/playlist/sequence",
            json={"candidate_set_id": "nonexistent-uuid-12345", "arc": "build"},
        )
        assert res_not_found.status_code == 404

        # Fewer than 2 tracks provided
        res_insufficient = await client.post(
            "/playlist/sequence",
            json={"track_ids": [mock_catalog.track_ids[0]], "arc": "build"},
        )
        assert res_insufficient.status_code == 400
