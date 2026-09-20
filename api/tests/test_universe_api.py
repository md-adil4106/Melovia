"""Unit and integration tests for 3D & 2D Taste Universe endpoints (Phase 12).

Verifies:
- Int16 quantization / dequantization roundtrip precision.
- GET /universe payload structure, region centroids, and trustworthiness >= 0.70.
- Payload size budget (< 600 KB for 15k points).
- POST /universe/place deterministic kNN placement within [-1.0, 1.0].
- GET /universe/neighbors/{track_id} high-dimensional similarity and distortion disclaimer.
- Error handling for nonexistent tracks.
"""

import json
from pathlib import Path

from httpx import ASGITransport, AsyncClient
import numpy as np
import pytest

from app.main import app
from app.recsys.catalog import CatalogStore
from app.recsys.universe import dequantize_points, quantize_points


@pytest.fixture
def catalog_store() -> CatalogStore:
    """Load catalog store from data/bundles/v1."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    bundle_path = repo_root / "data" / "bundles" / "v1"
    return CatalogStore.load(bundle_path)


def test_quantization_and_dequantization_roundtrip():
    """Verify Int16 quantization and dequantization preserves coordinates within precision tolerance."""
    rng = np.random.default_rng(42)
    n = 100
    points = rng.uniform(-1.0, 1.0, size=(n, 3)).astype(np.float32)
    regions = rng.integers(0, 24, size=n).tolist()
    tracks = list(range(n))

    # Quantize
    flat = quantize_points(points, regions, tracks)
    assert len(flat) == 5 * n

    # Check Int16 range
    for i in range(0, len(flat), 5):
        assert -32767 <= flat[i] <= 32767
        assert -32767 <= flat[i + 1] <= 32767
        assert -32767 <= flat[i + 2] <= 32767
        assert 0 <= flat[i + 3] < 24

    # Dequantize
    recovered_points, recovered_regions, recovered_tracks = dequantize_points(flat)
    assert recovered_regions == regions
    assert recovered_tracks == tracks
    np.testing.assert_allclose(recovered_points, points, atol=1.0 / 32767.0 + 1e-5)


def test_universe_payload_size_budget():
    """Verify that a 15,000-point quantized universe payload is strictly under 600 KB."""
    rng = np.random.default_rng(42)
    n = 15000
    points = rng.uniform(-1.0, 1.0, size=(n, 3)).astype(np.float32)
    regions = rng.integers(0, 24, size=n).tolist()
    tracks = list(range(n))

    flat = quantize_points(points, regions, tracks)
    mock_payload = {
        "points": flat,
        "point_count": n,
        "scale": 32767.0,
        "regions": [
            {
                "id": r,
                "label": f"Region {r}",
                "genre_focus": "Genre Focus",
                "description": "Description",
                "centroid_3d": [0.1, -0.2, 0.3],
                "centroid_2d": [0.1, -0.2],
                "color": "#38bdf8",
                "exposure": 0.05,
                "top_tags": ["tag1", "tag2", "tag3"],
                "track_count": 625,
            }
            for r in range(24)
        ],
        "metrics": {
            "trustworthiness_k15": 0.98,
            "continuity_k15": 0.98,
            "method_3d": "pca-3d",
            "method_2d": "pca-2d",
            "sample_count": n,
        },
    }

    raw_json = json.dumps(mock_payload)
    size_kb = len(raw_json.encode("utf-8")) / 1024.0
    print(f"\n15k Points Quantized Universe Payload Size: {size_kb:.1f} KB (budget: < 600 KB)")
    assert size_kb < 600.0, f"Payload size {size_kb:.1f} KB exceeded 600 KB budget"


@pytest.mark.asyncio
async def test_get_universe_endpoint(catalog_store: CatalogStore):
    """Verify GET /universe returns valid quantized points, 24 regions, and layout metrics."""
    app.state.catalog_store = catalog_store

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/universe")
        assert res.status_code == 200
        data = res.json()

        assert "points" in data
        assert "point_count" in data
        assert data["point_count"] == len(data["points"]) // 5
        assert len(data["regions"]) == 24
        assert "metrics" in data

        metrics = data["metrics"]
        assert metrics["trustworthiness_k15"] >= 0.70
        assert metrics["method_3d"] in ("umap-3d", "pca-3d")
        assert metrics["method_2d"] == "pca-2d"

        # Check first region structure
        reg0 = data["regions"][0]
        assert "centroid_3d" in reg0
        assert len(reg0["centroid_3d"]) == 3
        assert "color" in reg0
        assert reg0["color"].startswith("#")


@pytest.mark.asyncio
async def test_universe_place_endpoint_determinism(catalog_store: CatalogStore):
    """Verify POST /universe/place deterministically places tracks and mode vectors."""
    app.state.catalog_store = catalog_store
    target_ids = catalog_store.track_ids[:3]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Place existing track IDs
        res1 = await client.post("/universe/place", json={"track_ids": target_ids})
        assert res1.status_code == 200
        data1 = res1.json()
        assert len(data1["items"]) == 3

        # Place again and verify exact byte-determinism
        res2 = await client.post("/universe/place", json={"track_ids": target_ids})
        assert res2.status_code == 200
        data2 = res2.json()
        assert data1 == data2

        # 2. Place dynamic mode vector (128d)
        v_mode = catalog_store.vectors_t[0].tolist()
        res_mode = await client.post(
            "/universe/place",
            json={"mode_vectors": [v_mode], "k": 10},
        )
        assert res_mode.status_code == 200
        data_mode = res_mode.json()
        assert len(data_mode["items"]) == 1

        placed = data_mode["items"][0]
        assert placed["type"] == "taste_mode"
        assert len(placed["position_3d"]) == 3
        for coord in placed["position_3d"]:
            assert -1.0 <= coord <= 1.0
        assert len(placed["nearest_track_ids"]) == 10
        assert sum(placed["weights"]) == pytest.approx(1.0, abs=1e-3)


@pytest.mark.asyncio
async def test_universe_neighbors_endpoint(catalog_store: CatalogStore):
    """Verify GET /universe/neighbors/{track_id} returns true original-space neighbors with distortion disclosure."""
    app.state.catalog_store = catalog_store
    target_id = catalog_store.track_ids[0]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(f"/universe/neighbors/{target_id}")
        assert res.status_code == 200
        data = res.json()

        assert data["target_track_id"] == target_id
        assert len(data["neighbors"]) > 0
        assert "distortion_disclaimer" in data
        assert "non-linear" in data["distortion_disclaimer"].lower()

        # Verify neighbor structure
        first_nb = data["neighbors"][0]
        assert first_nb["track_id"] != target_id  # Cannot be self
        assert "similarity_combined" in first_nb
        assert "similarity_t" in first_nb
        assert -1.0 <= first_nb["similarity_t"] <= 1.0


@pytest.mark.asyncio
async def test_universe_neighbors_404_for_invalid_track(catalog_store: CatalogStore):
    """Verify GET /universe/neighbors/{invalid_id} returns 404 with domain error envelope."""
    app.state.catalog_store = catalog_store

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/universe/neighbors/nonexistent-track-uuid")
        assert res.status_code == 404
        data = res.json()
        assert "error" in data
        assert data["error"]["code"] == "TRACK_NOT_FOUND"
