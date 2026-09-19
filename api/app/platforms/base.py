"""Base Platform Adapter abstract base class for Melovia.

All platform integrations (Spotify, Apple Music, etc.) must implement PlatformAdapter.
Architecture Rules:
- Platform code lives only in api/app/platforms/* behind PlatformAdapter.
- No platform-specific types may leak into the recsys module.
- All external input is validated and treated as untrusted.
"""

from abc import ABC, abstractmethod
from typing import Any


class PlatformAdapter(ABC):
    """Abstract base class defining interface for music platform adapters."""

    @abstractmethod
    async def search_track(
        self,
        query: str,
        artist: str | None = None,
        isrc: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for tracks on the platform by query, artist, and/or ISRC."""
        raise NotImplementedError

    @abstractmethod
    async def get_metadata(self, platform_id: str) -> dict[str, Any]:
        """Fetch metadata for a single platform track."""
        raise NotImplementedError

    @abstractmethod
    async def authenticate(self, code: str) -> dict[str, Any]:
        """Exchange authorization code for access and refresh tokens."""
        raise NotImplementedError

    @abstractmethod
    async def create_playlist(
        self,
        user_id: str,
        name: str,
        track_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new playlist for the specified user, optionally populating tracks."""
        raise NotImplementedError

    @abstractmethod
    async def add_tracks(
        self,
        playlist_id: str,
        track_ids: list[str],
    ) -> bool:
        """Add track IDs to an existing playlist."""
        raise NotImplementedError
