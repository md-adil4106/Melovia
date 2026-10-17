"""Platform adapter registry for Melovia.

Architecture Rules:
- Lives in api/app/platforms/registry.py.
- Centralizes discovery and instantiation of supported platform adapters.
- Zero platform imports in recsys module.
"""

from __future__ import annotations

from typing import Any

from app.platforms.base import PlatformAdapter
from app.platforms.spotify import SpotifyAdapter


def list_supported_platforms() -> list[dict[str, Any]]:
    """Return catalog of available streaming and file export targets."""
    return [
        {
            "id": "file",
            "name": "Offline File Export",
            "formats": ["csv", "json", "m3u", "txt"],
            "requires_auth": False,
            "status": "ready",
            "description": (
                "Always available offline export to CSV, JSPF JSON, M3U playlist, or plain text."
            ),
        },
        {
            "id": "spotify",
            "name": "Spotify",
            "formats": ["playlist", "uri_clipboard", "universal"],
            "requires_auth": True,
            "auth_flow": "oauth_pkce",
            "status": "ready",
            "description": (
                "Export playlist directly to Spotify via OAuth PKCE, "
                "copy URIs, or transfer instantly."
            ),
        },
        {
            "id": "apple_music",
            "name": "Apple Music",
            "formats": ["m3u8", "web_links", "universal"],
            "requires_auth": False,
            "status": "ready",
            "description": (
                "Export native UTF-8 .m3u8 playlist file (imports into macOS Music / iTunes) "
                "or open track matches in Apple Music Web."
            ),
        },
        {
            "id": "ytmusic",
            "name": "YouTube Music",
            "formats": ["queue", "tracklist", "universal"],
            "requires_auth": False,
            "status": "ready",
            "description": (
                "Launch tracks in YouTube Music search/queue, copy tracklist, "
                "or transfer instantly."
            ),
        },
    ]


def get_adapter(platform_id: str) -> PlatformAdapter:
    """Instantiate and return the appropriate PlatformAdapter."""
    pid = platform_id.lower().strip()
    if pid == "spotify":
        return SpotifyAdapter()
    elif pid == "apple_music":
        raise NotImplementedError(
            "Apple Music adapter requires an Apple Developer membership. Use 'spotify' or 'file'."
        )
    else:
        raise ValueError(f"Unknown platform adapter: {platform_id}")
