"""Unit tests for SpotifyAdapter using httpx.MockTransport (zero external network calls)."""

import json

import httpx
import pytest

from app.platforms.spotify import (
    SpotifyAdapter,
    generate_code_challenge,
    generate_code_verifier,
)


def test_pkce_generation():
    """Verify PKCE code verifier and S256 code challenge generation."""
    verifier = generate_code_verifier()
    assert len(verifier) >= 43
    assert len(verifier) <= 128
    # Ensure URL-safe characters only
    assert all(c.isalnum() or c in "-._~" for c in verifier)

    challenge = generate_code_challenge(verifier)
    assert len(challenge) > 20
    assert not challenge.endswith("=")  # Base64url without padding


def test_authorization_url_builder():
    """Verify Spotify authorization URL contains required OAuth PKCE query parameters."""
    adapter = SpotifyAdapter(
        client_id="test_client_id_123",
        redirect_uri="http://127.0.0.1:8000/export/spotify/callback",
    )
    url = adapter.get_authorization_url(state="test_state_xyz", code_challenge="test_challenge_abc")

    assert url.startswith("https://accounts.spotify.com/authorize?")
    assert "client_id=test_client_id_123" in url
    assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A8000%2Fexport%2Fspotify%2Fcallback" in url
    assert "response_type=code" in url
    assert "code_challenge=test_challenge_abc" in url
    assert "code_challenge_method=S256" in url
    assert "state=test_state_xyz" in url
    assert "playlist-modify-private" in url


@pytest.mark.asyncio
async def test_spotify_adapter_mock_requests():
    """Test token exchange, playlist creation, and track batching with mock transport."""
    added_batches: list[list[str]] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)

        # 1. Token exchange
        if "accounts.spotify.com/api/token" in url:
            return httpx.Response(
                200,
                json={
                    "access_token": "mock_access_token_123",
                    "refresh_token": "mock_refresh_token_456",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
            )

        # 2. Create playlist
        if "/playlists" in url and request.method == "POST" and not url.endswith("/tracks"):
            body = json.loads(request.content)
            return httpx.Response(
                201,
                json={
                    "id": "mock_playlist_id_789",
                    "name": body["name"],
                    "external_urls": {
                        "spotify": "https://open.spotify.com/playlist/mock_playlist_id_789"
                    },
                },
            )

        if "api.spotify.com/v1/me" in url:
            return httpx.Response(
                200,
                json={
                    "id": "mock_user_id",
                    "display_name": "Melovia Explorer",
                    "external_urls": {"spotify": "https://open.spotify.com/user/mock_user_id"},
                },
            )

        # 3. Add tracks to playlist
        if "playlists/mock_playlist_id_789/tracks" in url and request.method == "POST":
            body = json.loads(request.content)
            added_batches.append(body.get("uris", []))
            return httpx.Response(201, json={"snapshot_id": "mock_snap_1"})

        # 4. Search
        if "api.spotify.com/v1/search" in url:
            return httpx.Response(
                200,
                json={
                    "tracks": {
                        "items": [
                            {
                                "id": "sp_t1",
                                "uri": "spotify:track:sp_t1",
                                "name": "Solaris Echoes",
                                "artists": [{"name": "Starlight Ensemble"}],
                                "external_ids": {"isrc": "USMLV2600001"},
                                "duration_ms": 210000,
                            }
                        ]
                    }
                },
            )

        return httpx.Response(404, json={"error": "not found"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    adapter = SpotifyAdapter(
        client_id="mock_cid",
        client_secret="mock_sec",
        redirect_uri="http://127.0.0.1:8000/export/spotify/callback",
        http_client=client,
    )

    # 1. Authenticate with PKCE
    tokens = await adapter.authenticate("mock_auth_code", "mock_code_verifier")
    assert tokens["access_token"] == "mock_access_token_123"

    # 2. Get profile
    profile = await adapter.get_current_user("mock_access_token_123")
    assert profile["id"] == "mock_user_id"
    assert profile["display_name"] == "Melovia Explorer"

    # 3. Search track
    search_res = await adapter.search_track(query="Solaris", access_token="mock_access_token_123")
    assert len(search_res) == 1
    assert search_res[0]["id"] == "sp_t1"
    assert search_res[0]["uri"] == "spotify:track:sp_t1"

    # 4. Create playlist and verify 100-track chunking
    # Pass 150 tracks to test batch chunking
    sample_track_uris = [f"spotify:track:test_{i}" for i in range(150)]
    pl = await adapter.create_playlist(
        user_id="mock_user_id",
        name="150 Track Adventure",
        track_ids=sample_track_uris,
        access_token="mock_access_token_123",
    )
    assert pl["id"] == "mock_playlist_id_789"
    # Verify add_tracks was called in chunks of <= 100
    assert len(added_batches) == 2
    assert len(added_batches[0]) == 100
    assert len(added_batches[1]) == 50

    await client.aclose()
