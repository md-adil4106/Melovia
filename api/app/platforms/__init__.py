"""Platform Adapter Module for Melovia.

All external music service interactions (Spotify, Apple Music, etc.) must inherit from
PlatformAdapter in base.py. No platform-specific types may leak into the recsys module.
"""

from app.platforms.base import PlatformAdapter

__all__ = ["PlatformAdapter"]
