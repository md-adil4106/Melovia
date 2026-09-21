"""Integration tests for export endpoints (file download, Spotify OAuth, and playlist creation)."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.routers.export import EXPORT_JOBS, SPOTIFY_SESSIONS, STATE_TO_SESSION


@pytest.fixture(autouse=True)
def clean_export_state():
    SPOTIFY_SESSIONS.clear()
    STATE_TO_SESSION.clear()
    EXPORT_JOBS.clear()
    yield
    SPOTIFY_SESSIONS.clear()
    STATE_TO_SESSION.clear()
    EXPORT_JOBS.clear()


@pytest.mark.asyncio
async def test_get_platforms():
    """Verify GET /export/platforms returns available targets."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/export/platforms")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        platform_ids = [p["id"] for p in data]
        assert "file" in platform_ids
        assert "spotify" in platform_ids


@pytest.mark.asyncio
async def test_export_file_formats():
    """Verify POST /export/file generates CSV, JSON, M3U, and TXT files."""
    sample_tracks = [
        {
            "id": "trk-101",
            "title": "Starlight Echo",
            "artist_name": "Aurora",
            "isrc": "USMLV2600101",
            "year": 2024,
            "scalars": {"bpm": 128.0, "energy": 0.85},
        },
        {
            "id": "trk-102",
            "title": "Ocean Waves",
            "artist_name": "Coast",
            "isrc": "USMLV2600102",
            "year": 2023,
            "scalars": {"bpm": 90.0, "energy": 0.35},
        },
    ]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. CSV
        res_csv = await client.post(
            "/export/file",
            json={"format": "csv", "playlist_name": "Summer Jam", "tracks": sample_tracks},
        )
        assert res_csv.status_code == 200
        assert "text/csv" in res_csv.headers["content-type"]
        assert 'filename="Summer_Jam.csv"' in res_csv.headers["content-disposition"]
        assert "Starlight Echo" in res_csv.text

        # 2. JSON (JSPF)
        res_json = await client.post(
            "/export/file",
            json={"format": "json", "playlist_name": "Summer Jam", "tracks": sample_tracks},
        )
        assert res_json.status_code == 200
        assert "application/json" in res_json.headers["content-type"]
        assert "Summer Jam" in res_json.text
        assert "playlist" in res_json.json()

        # 3. M3U
        res_m3u = await client.post(
            "/export/file",
            json={"format": "m3u", "playlist_name": "Summer Jam", "tracks": sample_tracks},
        )
        assert res_m3u.status_code == 200
        assert "audio/x-mpegurl" in res_m3u.headers["content-type"]
        assert "#EXTM3U" in res_m3u.text

        # 4. TXT
        res_txt = await client.post(
            "/export/file",
            json={"format": "txt", "playlist_name": "Summer Jam", "tracks": sample_tracks},
        )
        assert res_txt.status_code == 200
        assert "text/plain" in res_txt.headers["content-type"]
        assert "1. Aurora - Starlight Echo" in res_txt.text


@pytest.mark.asyncio
async def test_spotify_auth_url_generation():
    """Verify GET /export/spotify/auth-url returns valid PKCE parameters."""
    with patch("app.config.Settings.PLATFORM", create=True) as mock_plat:
        mock_plat.spotify_client_id = "test_sp_cid"
        mock_plat.client_id = "test_sp_cid"
        mock_plat.spotify_redirect_uri = "http://127.0.0.1:8000/export/spotify/callback"

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.get("/export/spotify/auth-url")
            assert res.status_code == 200
            data = res.json()
            assert "auth_url" in data
            assert "session_id" in data
            assert "state" in data
            assert "accounts.spotify.com" in data["auth_url"]
            assert data["state"] in STATE_TO_SESSION


@pytest.mark.asyncio
async def test_spotify_callback_and_session():
    """Verify Spotify OAuth callback exchanges code and updates session status."""
    session_id = "test_session_123"
    state = "test_state_xyz"
    SPOTIFY_SESSIONS[session_id] = {
        "code_verifier": "test_verifier_abc",
        "state": state,
        "created_at": 1000.0,
    }
    STATE_TO_SESSION[state] = session_id

    mock_auth = AsyncMock(
        return_value={
            "access_token": "mock_token_abc",
            "refresh_token": "mock_refresh_def",
            "expires_in": 3600,
        }
    )
    mock_user = AsyncMock(
        return_value={
            "id": "spotify_user_01",
            "display_name": "Alice Tester",
            "external_urls": {"spotify": "https://open.spotify.com/user/spotify_user_01"},
        }
    )

    with (
        patch("app.routers.export.SpotifyAdapter.authenticate", mock_auth),
        patch("app.routers.export.SpotifyAdapter.get_current_user", mock_user),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Invalid state returns 400
            res_bad = await client.get("/export/spotify/callback?code=mock_code&state=wrong_state")
            assert res_bad.status_code == 400

            # 2. Valid state successfully connects
            res_good = await client.get(f"/export/spotify/callback?code=mock_code&state={state}")
            assert res_good.status_code == 200
            assert "Connected to Spotify" in res_good.text

            # 3. Check status
            client.cookies.set("melovia_session_id", session_id)
            status_res = await client.get("/export/spotify/status")
            assert status_res.status_code == 200
            status_data = status_res.json()
            assert status_data["connected"] is True
            assert status_data["display_name"] == "Alice Tester"
            assert status_data["user_id"] == "spotify_user_01"


@pytest.mark.asyncio
async def test_export_playlist_flow():
    """Verify POST /export/playlist requires auth and creates playlist with matched tracks."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Unauthenticated export returns 401
        res_unauth = await client.post(
            "/export/playlist",
            json={
                "platform": "spotify",
                "playlist_name": "My Discovery",
                "tracks": [{"id": "t1", "title": "Song", "artist": "Artist"}],
            },
        )
        assert res_unauth.status_code == 401

        # 2. Authenticate session
        session_id = "test_sess_export"
        SPOTIFY_SESSIONS[session_id] = {
            "access_token": "valid_token_xyz",
            "user_id": "alice_user",
            "expires_at": 9999999999,
        }
        client.cookies.set("melovia_session_id", session_id)

        sample_tracks = [
            {"id": "t1", "title": "Solaris Echo", "artist": "Aurora", "isrc": "US123"},
            {"id": "t2", "title": "Unknown Mystery Sound", "artist": "Nobody", "isrc": None},
        ]

        # Mock search to match track 1 and fail track 2
        async def mock_search(query="", artist=None, isrc=None, access_token=None):
            if isrc == "US123" or "Solaris" in query:
                return [
                    {
                        "id": "sp_match_1",
                        "uri": "spotify:track:sp_match_1",
                        "title": "Solaris Echo",
                        "artist": "Aurora",
                        "isrc": "US123",
                    }
                ]
            return []

        mock_create = AsyncMock(
            return_value={
                "id": "sp_playlist_001",
                "name": "My Discovery",
                "external_urls": {"spotify": "https://open.spotify.com/playlist/sp_playlist_001"},
            }
        )

        patch_search = patch(
            "app.routers.export.SpotifyAdapter.search_track", side_effect=mock_search
        )
        patch_create = patch("app.routers.export.SpotifyAdapter.create_playlist", mock_create)
        with patch_search, patch_create:
            res_export = await client.post(
                "/export/playlist",
                json={
                    "platform": "spotify",
                    "playlist_name": "My Discovery",
                    "tracks": sample_tracks,
                },
            )
            assert res_export.status_code == 200
            job_data = res_export.json()
            assert job_data["status"] == "completed"
            assert job_data["playlist_id"] == "sp_playlist_001"
            assert job_data["matched_count"] == 1
            assert job_data["unmatched_count"] == 1
            assert len(job_data["tracks"]) == 2

            job_id = job_data["job_id"]

            # 3. GET /export/jobs/{job_id}
            res_job = await client.get(f"/export/jobs/{job_id}")
            assert res_job.status_code == 200
            assert res_job.json()["job_id"] == job_id

            # 4. Download unmatched tracks
            res_unmatched = await client.get(f"/export/jobs/{job_id}/unmatched")
            assert res_unmatched.status_code == 200
            assert "text/csv" in res_unmatched.headers["content-type"]
            assert "Unknown Mystery Sound" in res_unmatched.text
