"""Tests for PlatformAdapter abstract base class."""

import pytest

from app.platforms import PlatformAdapter
from app.platforms.base import PlatformAdapter as BasePlatformAdapter


def test_platform_adapter_cannot_be_instantiated_directly() -> None:
    """PlatformAdapter is an ABC and cannot be instantiated without implementations."""
    with pytest.raises(TypeError):
        PlatformAdapter()  # type: ignore[abstract]


def test_incomplete_subclass_cannot_be_instantiated() -> None:
    """A subclass missing abstract methods cannot be instantiated."""

    class IncompleteAdapter(BasePlatformAdapter):
        async def search_track(
            self, query: str, artist: str | None = None, isrc: str | None = None
        ):
            return []

    with pytest.raises(TypeError):
        IncompleteAdapter()  # type: ignore[abstract]


@pytest.mark.asyncio
async def test_concrete_adapter_can_be_instantiated() -> None:
    """A concrete implementation of all abstract methods can be instantiated."""

    class DummyAdapter(BasePlatformAdapter):
        async def search_track(
            self, query: str, artist: str | None = None, isrc: str | None = None
        ):
            return [{"id": "trk_1", "title": query}]

        async def get_metadata(self, platform_id: str):
            return {"id": platform_id, "title": "Dummy"}

        async def authenticate(self, code: str):
            return {"access_token": "token_123"}

        async def create_playlist(
            self, user_id: str, name: str, track_ids: list[str] | None = None
        ):
            return {"id": "pl_1", "name": name, "tracks": track_ids or []}

        async def add_tracks(self, playlist_id: str, track_ids: list[str]):
            return True

    adapter = DummyAdapter()
    results = await adapter.search_track("Neon")
    assert len(results) == 1
    assert results[0]["title"] == "Neon"
