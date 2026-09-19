"""Platform Adapter Module.

All external music service interactions (Spotify, Apple Music, etc.) must implement
PlatformAdapter. No platform-specific types may leak into the recsys module.
"""

from typing import Any, Protocol


class PlatformAdapter(Protocol):
    """Protocol defining the required interface for all music platform integrations."""

    async def search_track(self, query: str) -> list[dict[str, Any]]:
        """Search tracks on the platform."""
        ...

    async def get_metadata(self, platform_id: str) -> dict[str, Any]:
        """Fetch metadata for a single track."""
        ...

    async def authenticate(self, code: str) -> dict[str, Any]:
        """Exchange authorization code for access credentials."""
        ...

    async def create_playlist(self, user_id: str, title: str) -> dict[str, Any]:
        """Create an empty playlist for the user."""
        ...

    async def add_tracks(self, playlist_id: str, track_ids: list[str]) -> bool:
        """Add track IDs to an existing playlist."""
        ...


__all__ = ["PlatformAdapter"]
