"""Integration tests for feedback and persistent profile APIs."""

import logging
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

import pytest  # noqa: E402
from fixtures.make_mock_catalog import generate_mock_catalog  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.db.models import Profile  # noqa: E402
from app.db.session import async_session_factory  # noqa: E402
from app.main import app  # noqa: E402
from app.recsys import CatalogStore  # noqa: E402


@pytest.fixture
def mock_catalog(tmp_path: Path) -> CatalogStore:
    generate_mock_catalog(tmp_path)
    return CatalogStore.load(tmp_path)


@pytest.mark.asyncio
async def test_feedback_api_flow(mock_catalog: CatalogStore) -> None:
    """End-to-end flow: generate recommendations -> like -> dislike (exclusion)."""
    app.state.catalog_store = mock_catalog
    seeds = mock_catalog.track_ids[:3]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Generate recommendations
        rec_res = await client.post(
            "/recommendations",
            json={"seed_track_ids": seeds, "n": 30, "discovery": 0.35},
        )
        assert rec_res.status_code == 200
        cand_set_id = rec_res.json()["candidate_set_id"]
        initial_items = rec_res.json()["items"]
        assert len(initial_items) > 0

        target_like_id = initial_items[0]["track"]["id"]
        target_dislike_id = initial_items[1]["track"]["id"]

        # 2. Submit 'like' feedback
        fb_like_res = await client.post(
            "/feedback",
            json={
                "track_id": target_like_id,
                "event": "like",
                "candidate_set_id": cand_set_id,
            },
        )
        assert fb_like_res.status_code == 200
        like_data = fb_like_res.json()
        assert like_data["status"] == "ok"
        assert like_data["event"] == "like"
        assert like_data["mode_shifted"] is True
        assert len(like_data["items"]) > 0

        # 3. Submit 'dislike' feedback
        fb_dislike_res = await client.post(
            "/feedback",
            json={
                "track_id": target_dislike_id,
                "event": "dislike",
                "candidate_set_id": cand_set_id,
            },
        )
        assert fb_dislike_res.status_code == 200
        dislike_data = fb_dislike_res.json()
        assert dislike_data["status"] == "ok"
        assert dislike_data["applied_negatives_count"] >= 1

        # The disliked track must NOT be in the updated recommendations list
        updated_ids = [it["track"]["id"] for it in dislike_data["items"]]
        assert target_dislike_id not in updated_ids


@pytest.mark.asyncio
async def test_cookie_generation_and_flags(mock_catalog: CatalogStore) -> None:
    """Anonymous device ID cookie is generated with httpOnly and SameSite=Lax flags."""
    app.state.catalog_store = mock_catalog

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/profile")
        assert res.status_code == 200

        # Verify Set-Cookie header
        set_cookie = res.headers.get("set-cookie", "")
        assert "melovia_device_id=" in set_cookie
        assert "httponly" in set_cookie.lower()
        assert "samesite=lax" in set_cookie.lower()


@pytest.mark.asyncio
async def test_session_vs_persistent_isolation(mock_catalog: CatalogStore) -> None:
    """Feedback during a session leaves the persistent profile table unmutated until remember."""
    app.state.catalog_store = mock_catalog
    seeds = mock_catalog.track_ids[:3]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create session
        rec_res = await client.post(
            "/recommendations",
            json={"seed_track_ids": seeds, "n": 30, "discovery": 0.35},
        )
        assert rec_res.status_code == 200
        device_id = client.cookies.get("melovia_device_id")

        # Submit like feedback
        target_id = mock_catalog.track_ids[10]
        fb_res = await client.post(
            "/feedback",
            json={"track_id": target_id, "event": "like"},
        )
        assert fb_res.status_code == 200

        # Verify database profile table is empty for this device
        if device_id:
            async with async_session_factory() as db:
                stmt = select(Profile).where(Profile.device_id == device_id)
                res = await db.execute(stmt)
                assert res.scalar_one_or_none() is None

        # Now explicitly remember the session taste
        rem_res = await client.post("/profile/remember")
        assert rem_res.status_code == 200
        rem_data = rem_res.json()
        assert rem_data["status"] == "ok"
        assert rem_data["num_modes"] > 0

        # Now verify database profile table HAS a record
        device_id = client.cookies.get("melovia_device_id")
        assert device_id is not None
        async with async_session_factory() as db:
            stmt = select(Profile).where(Profile.device_id == device_id)
            res = await db.execute(stmt)
            profile_row = res.scalar_one_or_none()
            assert profile_row is not None
            assert len(profile_row.persistent_modes["weights"]) > 0


@pytest.mark.asyncio
async def test_profile_export_and_delete(mock_catalog: CatalogStore) -> None:
    """Profile export produces valid portable JSON, and DELETE purges profile completely."""
    app.state.catalog_store = mock_catalog
    seeds = mock_catalog.track_ids[:3]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/recommendations",
            json={"seed_track_ids": seeds, "n": 30, "discovery": 0.35},
        )
        await client.post("/profile/remember")

        # 1. GET /profile/export
        exp_res = await client.get("/profile/export")
        assert exp_res.status_code == 200
        exp_data = exp_res.json()
        assert exp_data["schema_version"] == "1.0.0"
        assert "persistent_modes" in exp_data
        assert "channel_vectors" in exp_data["persistent_modes"]
        assert "known_track_ids" in exp_data

        # 2. DELETE /profile
        del_res = await client.delete("/profile")
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "ok"

        # 3. GET /profile after delete
        status_res = await client.get("/profile")
        assert status_res.status_code == 200
        assert status_res.json()["has_profile"] is False


@pytest.mark.asyncio
async def test_start_from_saved_taste(mock_catalog: CatalogStore) -> None:
    """POST /recommendations with use_saved_taste=True succeeds using saved persistent modes."""
    app.state.catalog_store = mock_catalog
    seeds = mock_catalog.track_ids[:3]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Initial recommendation and remember
        await client.post(
            "/recommendations",
            json={"seed_track_ids": seeds, "n": 30, "discovery": 0.35},
        )
        await client.post("/profile/remember")

        # Generate recommendations using saved taste (empty seed_track_ids)
        saved_rec_res = await client.post(
            "/recommendations",
            json={"use_saved_taste": True, "n": 30, "discovery": 0.35},
        )
        assert saved_rec_res.status_code == 200
        data = saved_rec_res.json()
        assert len(data["items"]) == 30
        assert data["candidate_set_id"] is not None


@pytest.mark.asyncio
async def test_no_raw_device_id_in_logs(
    mock_catalog: CatalogStore, caplog: pytest.LogCaptureFixture
) -> None:
    """Raw device_id must never appear in log messages; only hashed device_id is permitted."""
    app.state.catalog_store = mock_catalog
    seeds = mock_catalog.track_ids[:2]

    caplog.set_level(logging.INFO)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/recommendations",
            json={"seed_track_ids": seeds, "n": 30},
        )
        dev_id = client.cookies.get("melovia_device_id")
        assert dev_id is not None

        await client.post(
            "/feedback",
            json={"track_id": seeds[0], "event": "like"},
        )
        await client.post("/profile/remember")

        # Verify that the raw UUID string never appears in any Melovia application log output
        for record in caplog.records:
            if record.name.startswith(("app", "melovia")):
                assert dev_id not in record.getMessage(), (
                    f"Security breach: raw device_id '{dev_id}' leaked in log message: "
                    f"'{record.getMessage()}'"
                )
