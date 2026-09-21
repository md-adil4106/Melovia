"""Spotify Dev Mode Platform Adapter.

Implements Spotify OAuth 2.0 Authorization Code Flow with PKCE,
search, playlist creation, and batch track insertion.

Architecture Rules:
- Lives in api/app/platforms/spotify.py behind PlatformAdapter.
- Zero platform code or types leak into recsys.
- External inputs validated and treated as untrusted.
- Never logs tokens or writes them to disk.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import urllib.parse
from typing import Any, cast

import httpx

from app.config import get_settings
from app.platforms.base import PlatformAdapter

logger = logging.getLogger(__name__)

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"
DEFAULT_SCOPES = "playlist-modify-public playlist-modify-private user-read-private"


def generate_code_verifier() -> str:
    """Generate a high-entropy PKCE code verifier (RFC 7636)."""
    return secrets.token_urlsafe(64)[:128]


def generate_code_challenge(verifier: str) -> str:
    """Compute S256 code challenge from verifier."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


class SpotifyAdapter(PlatformAdapter):
    """Spotify platform adapter supporting OAuth PKCE, catalog search, and playlist export."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = get_settings()
        plat = settings.PLATFORM
        self.client_id = client_id or plat.spotify_client_id or plat.client_id
        self.client_secret = client_secret or plat.spotify_client_secret or plat.client_secret
        self.redirect_uri = redirect_uri or plat.spotify_redirect_uri or plat.redirect_uri
        self._custom_client = http_client
        self._client_credentials_token: str | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._custom_client:
            return self._custom_client
        return httpx.AsyncClient(timeout=10.0)

    def get_authorization_url(self, state: str, code_challenge: str) -> str:
        """Construct the Spotify OAuth authorization URL with PKCE."""
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "state": state,
            "scope": DEFAULT_SCOPES,
            "code_challenge_method": "S256",
            "code_challenge": code_challenge,
        }
        return f"{SPOTIFY_AUTH_URL}?{urllib.parse.urlencode(params)}"

    async def get_client_credentials_token(self) -> str:
        """Fetch or return an app-level token for catalog track search."""
        if self._client_credentials_token:
            return self._client_credentials_token

        if not self.client_id or not self.client_secret:
            return ""

        auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        client = await self._get_client()
        try:
            resp = await client.post(
                SPOTIFY_TOKEN_URL,
                data={"grant_type": "client_credentials"},
                headers={"Authorization": f"Basic {auth_header}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                token = str(data.get("access_token", ""))
                self._client_credentials_token = token
                return token
        finally:
            if not self._custom_client:
                await client.aclose()

        return ""

    async def authenticate(self, code: str, code_verifier: str = "") -> dict[str, Any]:
        """Exchange authorization code for access and refresh tokens via PKCE."""
        client = await self._get_client()
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
        }
        if code_verifier:
            data["code_verifier"] = code_verifier

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if self.client_secret:
            raw = f"{self.client_id}:{self.client_secret}".encode()
            auth_header = base64.b64encode(raw).decode()
            headers["Authorization"] = f"Basic {auth_header}"

        try:
            resp = await client.post(SPOTIFY_TOKEN_URL, data=data, headers=headers)
            if resp.status_code != 200:
                logger.error("Spotify token exchange failed with status %d", resp.status_code)
                return {
                    "error": f"Token exchange failed: {resp.status_code}",
                    "details": resp.text,
                }
            return cast(dict[str, Any], resp.json())
        finally:
            if not self._custom_client:
                await client.aclose()

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        """Refresh an expired access token."""
        client = await self._get_client()
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if self.client_secret:
            raw = f"{self.client_id}:{self.client_secret}".encode()
            auth_header = base64.b64encode(raw).decode()
            headers["Authorization"] = f"Basic {auth_header}"

        try:
            resp = await client.post(SPOTIFY_TOKEN_URL, data=data, headers=headers)
            if resp.status_code != 200:
                logger.error("Spotify token refresh failed with status %d", resp.status_code)
                return {"error": f"Token refresh failed: {resp.status_code}"}
            return cast(dict[str, Any], resp.json())
        finally:
            if not self._custom_client:
                await client.aclose()

    async def get_current_user(self, access_token: str) -> dict[str, Any]:
        """Fetch the current authenticated Spotify user profile."""
        client = await self._get_client()
        try:
            resp = await client.get(
                f"{SPOTIFY_API_BASE}/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code != 200:
                logger.error("Spotify /me failed with status %d", resp.status_code)
                return {}
            return cast(dict[str, Any], resp.json())
        finally:
            if not self._custom_client:
                await client.aclose()

    async def search_track(
        self,
        query: str,
        artist: str | None = None,
        isrc: str | None = None,
        access_token: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search Spotify for tracks matching ISRC or title+artist."""
        token = access_token or await self.get_client_credentials_token()
        if not token:
            return []

        if isrc and isrc.strip():
            q = f"isrc:{isrc.strip()}"
        elif query and artist:
            q = f"track:{query} artist:{artist}"
        elif query:
            q = query
        else:
            return []

        client = await self._get_client()
        try:
            resp = await client.get(
                f"{SPOTIFY_API_BASE}/search",
                params={"q": q, "type": "track", "limit": 10},
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            items = data.get("tracks", {}).get("items", [])
            results = []
            for item in items:
                artists = [a.get("name", "") for a in item.get("artists", [])]
                results.append(
                    {
                        "id": item.get("id"),
                        "uri": item.get("uri"),
                        "title": item.get("name"),
                        "artist": ", ".join(artists),
                        "isrc": item.get("external_ids", {}).get("isrc"),
                        "duration_ms": item.get("duration_ms"),
                    }
                )
            return results
        finally:
            if not self._custom_client:
                await client.aclose()

    async def get_metadata(
        self, platform_id: str, access_token: str | None = None
    ) -> dict[str, Any]:
        """Fetch metadata for a single platform track."""
        token = access_token or await self.get_client_credentials_token()
        if not token:
            return {}

        client = await self._get_client()
        try:
            resp = await client.get(
                f"{SPOTIFY_API_BASE}/tracks/{platform_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code != 200:
                return {}
            return cast(dict[str, Any], resp.json())
        finally:
            if not self._custom_client:
                await client.aclose()

    async def create_playlist(
        self,
        user_id: str,
        name: str,
        track_ids: list[str] | None = None,
        access_token: str = "",
        description: str = "Exported from Melovia Music Discovery",
    ) -> dict[str, Any]:
        """Create a new playlist for the user and optionally populate initial tracks."""
        if not access_token:
            raise ValueError("Spotify playlist creation requires an active user access_token.")

        client = await self._get_client()
        try:
            # POST /v1/me/playlists or /v1/users/{user_id}/playlists
            if not user_id or user_id == "me":
                endpoint = f"{SPOTIFY_API_BASE}/me/playlists"
            else:
                endpoint = f"{SPOTIFY_API_BASE}/users/{user_id}/playlists"

            resp = await client.post(
                endpoint,
                json={
                    "name": name,
                    "description": description,
                    "public": False,
                },
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code not in (200, 201):
                logger.error(
                    "Failed to create Spotify playlist: status %d %s",
                    resp.status_code,
                    resp.text,
                )
                return {
                    "error": f"Playlist creation failed: {resp.status_code}",
                    "details": resp.text,
                }

            playlist_data = cast(dict[str, Any], resp.json())
            playlist_id = playlist_data.get("id")

            if playlist_id and track_ids:
                await self.add_tracks(playlist_id, track_ids, access_token=access_token)

            return playlist_data
        finally:
            if not self._custom_client:
                await client.aclose()

    async def add_tracks(
        self,
        playlist_id: str,
        track_ids: list[str],
        access_token: str = "",
    ) -> bool:
        """Add track URIs to an existing playlist in batches of up to 100."""
        if not access_token or not track_ids:
            return False

        # Ensure all IDs are in uri format
        uris = [
            t if t.startswith("spotify:track:") else f"spotify:track:{t}" for t in track_ids if t
        ]

        client = await self._get_client()
        try:
            # Batch in chunks of 100 (Spotify API limit)
            chunk_size = 100
            for i in range(0, len(uris), chunk_size):
                chunk = uris[i : i + chunk_size]
                resp = await client.post(
                    f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks",
                    json={"uris": chunk},
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if resp.status_code not in (200, 201):
                    logger.error(
                        "Failed to add tracks chunk to Spotify playlist: status %d",
                        resp.status_code,
                    )
                    return False
            return True
        finally:
            if not self._custom_client:
                await client.aclose()
