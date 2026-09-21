"""Unit tests for platform track matching cascade.

Covers ISRC exact match + fuzzy title/artist fallback.
"""

from typing import Any

import pytest

from app.platforms.base import PlatformAdapter
from app.platforms.matching import (
    MatchStatus,
    TrackMatcher,
    compute_string_similarity,
    normalize_artist,
    normalize_title,
)


class MockPlatformAdapter(PlatformAdapter):
    """Mock platform adapter for isolated unit testing."""

    def __init__(self):
        self.search_calls = 0
        self.mock_isrc_db = {}
        self.mock_search_db = []

    async def search_track(
        self,
        query: str,
        artist: str | None = None,
        isrc: str | None = None,
    ) -> list[dict[str, Any]]:
        self.search_calls += 1
        if isrc and isrc in self.mock_isrc_db:
            return [self.mock_isrc_db[isrc]]

        if query:
            results = []
            for item in self.mock_search_db:
                results.append(item)
            return results
        return []

    async def get_metadata(self, platform_id: str) -> dict[str, Any]:
        return {}

    async def authenticate(self, code: str) -> dict[str, Any]:
        return {}

    async def create_playlist(
        self, user_id: str, name: str, track_ids: list[str] | None = None
    ) -> dict[str, Any]:
        return {}

    async def add_tracks(self, playlist_id: str, track_ids: list[str]) -> bool:
        return True


def test_string_normalization():
    """Verify title and artist cleaning strips parentheticals, featured artists, and punctuation."""
    assert normalize_title("Song Title (feat. Artist B)") == "song title"
    assert normalize_title("Midnight Dreams [Remastered 2021]") == "midnight dreams"
    assert normalize_title("Hello, World! (ft. Drake & 21 Savage)") == "hello world"
    assert normalize_artist("The Chemical Brothers") == "the chemical brothers"
    assert normalize_artist("AC/DC") == "ac dc"


def test_string_similarity():
    """Verify difflib ratio metrics."""
    assert compute_string_similarity("hello world", "hello world") == 1.0
    assert compute_string_similarity("hello world", "hello worlz") > 0.9
    assert compute_string_similarity("ambient", "rock") < 0.3


@pytest.mark.asyncio
async def test_isrc_exact_matching():
    """Verify Strategy 1: When ISRC matches on platform, returns MATCHED with confidence 1.0."""
    adapter = MockPlatformAdapter()
    adapter.mock_isrc_db["USMLV2600001"] = {
        "id": "spotify-track-123",
        "uri": "spotify:track:spotify-track-123",
        "title": "Solaris Echoes",
        "artist": "Starlight Ensemble",
        "isrc": "USMLV2600001",
    }
    matcher = TrackMatcher(adapter)

    res = await matcher.match_track(
        catalog_track_id="cat-01",
        title="Solaris Echoes (Original Mix)",
        artist="Starlight Ensemble",
        isrc="USMLV2600001",
    )

    assert res.status == MatchStatus.MATCHED
    assert res.confidence == 1.0
    assert res.match_strategy == "isrc"
    assert res.platform_uri == "spotify:track:spotify-track-123"
    assert adapter.search_calls == 1


@pytest.mark.asyncio
async def test_fuzzy_matching_cascade():
    """Verify Strategy 2: Fuzzy fallback evaluates confidence thresholds."""
    adapter = MockPlatformAdapter()
    # Candidate with high title/artist similarity
    adapter.mock_search_db = [
        {
            "id": "sp-high",
            "uri": "spotify:track:sp-high",
            "title": "Cosmic Drift (Extended Mix)",
            "artist": "Nova Pulse",
        }
    ]
    matcher = TrackMatcher(adapter)

    # 1. High similarity match (score >= 0.82)
    res_high = await matcher.match_track(
        catalog_track_id="cat-high",
        title="Cosmic Drift",
        artist="Nova Pulse",
        isrc=None,
    )
    assert res_high.status == MatchStatus.MATCHED
    assert res_high.confidence >= 0.82
    assert res_high.match_strategy == "fuzzy"
    assert res_high.platform_track_id == "sp-high"

    # 2. Ambiguous match (0.65 <= score < 0.82)
    adapter.mock_search_db = [
        {
            "id": "sp-med",
            "uri": "spotify:track:sp-med",
            "title": "Cosmic Waves Live",
            "artist": "Nova Pulse Band",
        }
    ]
    res_ambig = await matcher.match_track(
        catalog_track_id="cat-ambig",
        title="Cosmic Drift",
        artist="Nova Pulse",
        isrc=None,
    )
    assert res_ambig.status == MatchStatus.AMBIGUOUS
    assert 0.65 <= res_ambig.confidence < 0.82

    # 3. Unmatched (score < 0.65)
    adapter.mock_search_db = [
        {
            "id": "sp-low",
            "uri": "spotify:track:sp-low",
            "title": "Totally Unrelated Symphony",
            "artist": "Classical Trio",
        }
    ]
    res_low = await matcher.match_track(
        catalog_track_id="cat-low",
        title="Cosmic Drift",
        artist="Nova Pulse",
        isrc=None,
    )
    assert res_low.status == MatchStatus.UNMATCHED
    assert res_low.confidence < 0.65
    assert res_low.platform_track_id is None


@pytest.mark.asyncio
async def test_matcher_caching():
    """Verify in-memory caching avoids repeated queries for identical tracks."""
    adapter = MockPlatformAdapter()
    adapter.mock_isrc_db["ISRC-TEST"] = {
        "id": "sp-cached",
        "uri": "spotify:track:sp-cached",
        "title": "Test",
        "artist": "Tester",
    }
    matcher = TrackMatcher(adapter)

    res1 = await matcher.match_track("cat-1", "Test", "Tester", isrc="ISRC-TEST")
    assert adapter.search_calls == 1

    # Second call for the same track ID and ISRC should hit cache
    res2 = await matcher.match_track("cat-1", "Test", "Tester", isrc="ISRC-TEST")
    assert adapter.search_calls == 1
    assert res1 == res2
