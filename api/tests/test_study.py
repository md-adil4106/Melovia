"""Tests for Study Mode endpoints and double-blind protocol (Phase 15)."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_study_session_blindness_and_structure():
    """Verify study trial session returns blind playlists with zero leakage of arm."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/study/session")
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert "session_id" in data
        assert "seed_set_id" in data
        assert "seed_tracks" in data
        assert len(data["seed_tracks"]) > 0

        assert "playlist_a" in data
        assert "playlist_b" in data
        assert len(data["playlist_a"]) > 0
        assert len(data["playlist_b"]) > 0

        # Verify strict blindness: No signals, discovery scores, scores, or arm tags leaked
        for track in data["playlist_a"] + data["playlist_b"]:
            assert "score" not in track
            assert "signals" not in track
            assert "discovery_value" not in track
            assert "arm" not in track
            assert "hybrid" not in str(track).lower()
            assert "baseline" not in str(track).lower()


@pytest.mark.anyio
async def test_study_rate_submission_and_validation():
    """Verify study rating submission validates Likert ranges and records rating."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Get a session
        sess_resp = await client.get("/study/session")
        assert sess_resp.status_code == 200
        session_id = sess_resp.json()["session_id"]

        # 2. Submit valid ratings
        valid_payload = {
            "session_id": session_id,
            "relevance_a": 4,
            "discovery_a": 5,
            "flow_a": 4,
            "satisfaction_a": 4,
            "relevance_b": 3,
            "discovery_b": 2,
            "flow_b": 3,
            "satisfaction_b": 3,
            "preferred_overall": "playlist_a",
            "feedback_text": "Playlist A had much better discovery and coherent flow.",
        }
        rate_resp = await client.post("/study/rate", json=valid_payload)
        assert rate_resp.status_code == 200, rate_resp.text
        rate_data = rate_resp.json()
        assert rate_data["status"] == "ok"
        assert "rating_id" in rate_data

        # 3. Validation: Likert out of range (>5)
        invalid_payload = dict(valid_payload)
        invalid_payload["relevance_a"] = 6
        bad_resp = await client.post("/study/rate", json=invalid_payload)
        assert bad_resp.status_code == 422

        # 4. Validation: Invalid preferred_overall
        invalid_pref = dict(valid_payload)
        invalid_pref["preferred_overall"] = "playlist_c"
        bad_pref_resp = await client.post("/study/rate", json=invalid_pref)
        assert bad_pref_resp.status_code == 422


@pytest.mark.anyio
async def test_study_export_security_and_format():
    """Verify /study/export requires admin token and exports unblinded CSV."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. First submit a rating to ensure at least one record exists
        sess_resp = await client.get("/study/session")
        session_id = sess_resp.json()["session_id"]
        await client.post(
            "/study/rate",
            json={
                "session_id": session_id,
                "relevance_a": 5,
                "discovery_a": 4,
                "flow_a": 5,
                "satisfaction_a": 5,
                "relevance_b": 2,
                "discovery_b": 3,
                "flow_b": 2,
                "satisfaction_b": 2,
                "preferred_overall": "playlist_a",
                "feedback_text": "Export test submission",
            },
        )

        # 2. Missing token -> 401
        unauth_resp = await client.get("/study/export")
        assert unauth_resp.status_code == 401

        # 3. Wrong token -> 401
        wrong_resp = await client.get("/study/export?token=wrong-secret")
        assert wrong_resp.status_code == 401

        # 4. Correct token via query param -> 200
        from app.config import get_settings

        admin_token = get_settings().STUDY_ADMIN_TOKEN
        auth_resp = await client.get(f"/study/export?token={admin_token}")
        assert auth_resp.status_code == 200
        assert "text/csv" in auth_resp.headers["content-type"]
        csv_text = auth_resp.text
        assert "rating_id,session_id,participant_id" in csv_text
        assert "relevance_hybrid,discovery_hybrid" in csv_text
        assert "relevance_baseline,discovery_baseline" in csv_text
        assert "preferred_overall_arm" in csv_text

        # 5. Correct token via Bearer header -> 200
        bearer_resp = await client.get(
            "/study/export", headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert bearer_resp.status_code == 200
        assert "relevance_hybrid" in bearer_resp.text
