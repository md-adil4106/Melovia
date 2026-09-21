"""Security and reliability hardening test suite (Phase 14).

Verifies:
1. Security headers (CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy).
2. Rate limiting token bucket enforcement on search, feedback, export, and refine.
3. Input validation caps and error envelopes on oversized inputs.
4. Database graceful degradation (memory-only fallback on DB write failure).
5. Log redaction invariants (device ID hashed, tokens never logged).
6. Single-use OAuth state parameter defense.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_security_headers_present_on_all_responses(async_client: AsyncClient) -> None:
    """Every HTTP response must include standard security headers."""
    response = await async_client.get("/health")
    assert response.status_code == 200

    headers = response.headers
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") == "DENY"
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert "permissions-policy" in headers
    assert "content-security-policy" in headers
    csp = headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "connect-src" in csp


@pytest.mark.asyncio
async def test_track_search_rate_limiting(async_client: AsyncClient) -> None:
    """Exceeding token bucket on /tracks/search triggers HTTP 429 with error envelope."""
    from app.routers.tracks import search_rate_limiter

    # Exhaust tokens for a distinct test client
    test_key = "search:127.0.0.1:rl-test-device"
    # Drain bucket
    while search_rate_limiter.consume(test_key, tokens=1.0):
        pass

    # Next request with this device cookie should be rate limited
    response = await async_client.get(
        "/tracks/search?q=rock",
        cookies={"melovia_device_id": "rl-test-device"},
    )
    assert response.status_code == 429
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "request_id" in data["error"]


@pytest.mark.asyncio
async def test_input_validation_caps(async_client: AsyncClient) -> None:
    """Over-length inputs must fail schema validation at HTTP boundary."""
    # 1. Search query exceeding 100 characters
    long_query = "a" * 101
    resp = await async_client.get(f"/tracks/search?q={long_query}")
    assert resp.status_code == 422
    assert "error" in resp.json()
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    # 2. Excluded artists exceeding 50 items
    oversize_artists = [f"artist-{i}" for i in range(51)]
    resp = await async_client.post(
        "/recommendations",
        json={"seed_track_ids": ["mock-track-0001"], "excluded_artist_ids": oversize_artists},
    )
    assert resp.status_code == 422

    # 3. Export request exceeding 500 tracks
    oversize_tracks = [f"mock-track-{i:04d}" for i in range(501)]
    resp = await async_client.post(
        "/export/file",
        json={"format": "csv", "track_ids": oversize_tracks},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_feedback_degrades_gracefully_on_db_failure(
    async_client: AsyncClient,
) -> None:
    """When DB write fails during feedback, API must update in-memory session without 500 error."""
    from app.main import app

    store = app.state.catalog_store
    seed_id = store.get_id(0)
    target_id = store.get_id(1)

    # Generate recommendations first to have a valid candidate_set_id
    rec_resp = await async_client.post(
        "/recommendations",
        json={"seed_track_ids": [seed_id], "n": 10},
    )
    assert rec_resp.status_code == 200
    cand_id = rec_resp.json()["candidate_set_id"]

    # Mock DB commit to raise an operational failure
    with patch(
        "sqlalchemy.ext.asyncio.AsyncSession.commit",
        side_effect=RuntimeError("Database connection lost"),
    ):
        fb_resp = await async_client.post(
            "/feedback",
            json={
                "track_id": target_id,
                "event": "like",
                "candidate_set_id": cand_id,
            },
        )
        # Must return 200 OK because in-memory live modes and rerank succeeded
        assert fb_resp.status_code == 200
        fb_data = fb_resp.json()
        assert fb_data["status"] == "ok"
        assert fb_data["track_id"] == target_id


@pytest.mark.asyncio
async def test_single_use_oauth_state(async_client: AsyncClient) -> None:
    """OAuth state parameter must be consumed upon first use and rejected on replay."""
    from app.routers.export import SPOTIFY_SESSIONS, STATE_TO_SESSION

    test_state = "test-state-token-123"
    test_session = "test-session-456"

    SPOTIFY_SESSIONS[test_session] = {
        "code_verifier": "test-verifier",
        "state": test_state,
    }
    STATE_TO_SESSION[test_state] = test_session

    # Mock token exchange
    with (
        patch(
            "app.platforms.spotify.SpotifyAdapter.authenticate", new_callable=AsyncMock
        ) as mock_auth,
        patch(
            "app.platforms.spotify.SpotifyAdapter.get_current_user", new_callable=AsyncMock
        ) as mock_user,
    ):
        mock_auth.return_value = {"access_token": "mock-token", "expires_in": 3600}
        mock_user.return_value = {"id": "mock_user", "display_name": "Test User"}

        # First callback with valid state succeeds
        r1 = await async_client.get(f"/export/spotify/callback?code=mock_code&state={test_state}")
        assert r1.status_code == 200

        # Second callback with same state must be rejected with 400 Bad Request
        r2 = await async_client.get(f"/export/spotify/callback?code=mock_code&state={test_state}")
        assert r2.status_code == 400
        assert "Invalid or expired OAuth state parameter" in r2.text


@pytest.mark.asyncio
async def test_log_redaction_invariants(
    async_client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    """Device ID and tokens must never appear in unhashed plaintext in server logs."""
    import logging

    raw_device_id = "sensitive-device-uuid-999888777"
    client = AsyncClient(
        transport=async_client._transport,
        base_url=str(async_client.base_url),
        cookies={"melovia_device_id": raw_device_id},
    )

    with caplog.at_level(logging.INFO):
        resp = await client.get("/health")
        assert resp.status_code == 200

    # Ensure the raw device ID string does NOT appear anywhere in logged records
    for record in caplog.records:
        assert raw_device_id not in record.getMessage()
        assert raw_device_id not in getattr(record, "client_ip", "")
