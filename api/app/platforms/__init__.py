"""Platform Adapter Module for Melovia.

All external music service interactions (Spotify, Apple Music, etc.) must inherit from
PlatformAdapter in base.py. No platform-specific types may leak into the recsys module.
"""

from app.platforms.base import PlatformAdapter
from app.platforms.files import FileExportAdapter
from app.platforms.matching import MatchStatus, TrackMatcher, TrackMatchResult
from app.platforms.registry import get_adapter, list_supported_platforms
from app.platforms.spotify import SpotifyAdapter

__all__ = [
    "PlatformAdapter",
    "FileExportAdapter",
    "SpotifyAdapter",
    "TrackMatcher",
    "TrackMatchResult",
    "MatchStatus",
    "get_adapter",
    "list_supported_platforms",
]
