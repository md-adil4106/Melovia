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
            "name": "Spotify Dev Mode",
            "formats": ["playlist"],
            "requires_auth": True,
            "auth_flow": "oauth_pkce",
            "status": "ready",
            "description": "Export playlist directly to your Spotify account using OAuth PKCE.",
        },
        {
            "id": "apple_music",
            "name": "Apple Music",
            "formats": ["playlist"],
            "requires_auth": True,
            "auth_flow": "musickit",
            "status": "planned",
            "description": (
                "Requires an active Apple Developer Program membership ($99/yr) "
                "and MusicKit Developer Key."
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
