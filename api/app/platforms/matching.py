"""Platform track matching service: ISRC exact match with fuzzy title+artist fallback.

Architecture Rules:
- Platform code lives in api/app/platforms/*.
- Deterministic text normalization and difflib similarity scoring.
- Caches results to avoid redundant external platform queries.
- Acceptance threshold: >=0.82 matched, [0.65, 0.82) ambiguous, <0.65 unmatched.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.platforms.base import PlatformAdapter


class MatchStatus(StrEnum):
    MATCHED = "matched"
    AMBIGUOUS = "ambiguous"
    UNMATCHED = "unmatched"


@dataclass
class TrackMatchResult:
    catalog_track_id: str
    catalog_title: str
    catalog_artist: str
    catalog_isrc: str | None
    status: MatchStatus
    confidence: float
    platform_track_id: str | None = None
    platform_uri: str | None = None
    platform_title: str | None = None
    platform_artist: str | None = None
    match_strategy: str = "none"  # "isrc", "fuzzy", "none"


def normalize_title(title: str) -> str:
    """Normalize track title for robust fuzzy matching."""
    s = title.lower()
    # Strip feat. / ft. expressions
    s = re.sub(r"\(feat\..*?\)|\[feat\..*?\]|\(ft\..*?\)|\[ft\..*?\]", "", s)
    # Strip remastered / remaster expressions
    s = re.sub(r"\(remastered.*?\)|\[remastered.*?\]|\(remaster.*?\)|\[remaster.*?\]", "", s)
    # Strip mix / version / edit parentheticals
    mix_pat = r"(extended|radio|club|original|acoustic)?\s*(mix|edit|version|instrumental|dub).*?"
    s = re.sub(rf"\({mix_pat}\)", "", s)
    s = re.sub(rf"\[{mix_pat}\]", "", s)
    # Strip standard punctuation
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def normalize_artist(artist: str) -> str:
    """Normalize artist name for robust fuzzy matching."""
    s = artist.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def compute_string_similarity(a: str, b: str) -> float:
    """Compute normalized SequenceMatcher ratio between two strings."""
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


class TrackMatcher:
    """Service to match catalog tracks against an external streaming platform."""

    def __init__(self, adapter: PlatformAdapter) -> None:
        self.adapter = adapter
        self._cache: dict[str, TrackMatchResult] = {}

    def clear_cache(self) -> None:
        """Clear the match cache."""
        self._cache.clear()

    async def match_track(
        self,
        catalog_track_id: str,
        title: str,
        artist: str,
        isrc: str | None = None,
    ) -> TrackMatchResult:
        """Match a single catalog track against the platform.

        Strategy 1: Exact ISRC query
        Strategy 2: Fuzzy title + artist match
        """
        cache_key = f"{catalog_track_id}:{isrc or ''}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 1. Try ISRC lookup if available
        if isrc and isrc.strip():
            clean_isrc = isrc.strip().upper()
            try:
                results = await self.adapter.search_track(query="", artist=artist, isrc=clean_isrc)
                if results:
                    best = results[0]
                    result = TrackMatchResult(
                        catalog_track_id=catalog_track_id,
                        catalog_title=title,
                        catalog_artist=artist,
                        catalog_isrc=clean_isrc,
                        status=MatchStatus.MATCHED,
                        confidence=1.0,
                        platform_track_id=best.get("id"),
                        platform_uri=best.get("uri"),
                        platform_title=best.get("title"),
                        platform_artist=best.get("artist"),
                        match_strategy="isrc",
                    )
                    self._cache[cache_key] = result
                    return result
            except Exception:
                # Fall through to fuzzy search if ISRC query fails
                pass

        # 2. Fuzzy title + artist search
        norm_title = normalize_title(title)
        norm_artist = normalize_artist(artist)

        try:
            results = await self.adapter.search_track(query=title, artist=artist, isrc=None)
        except Exception:
            results = []

        if not results:
            result = TrackMatchResult(
                catalog_track_id=catalog_track_id,
                catalog_title=title,
                catalog_artist=artist,
                catalog_isrc=isrc,
                status=MatchStatus.UNMATCHED,
                confidence=0.0,
                match_strategy="none",
            )
            self._cache[cache_key] = result
            return result

        best_cand: dict[str, Any] | None = None
        best_score = -1.0

        for cand in results:
            cand_title = normalize_title(cand.get("title", ""))
            cand_artist = normalize_artist(cand.get("artist", ""))

            title_sim = compute_string_similarity(norm_title, cand_title)
            artist_sim = compute_string_similarity(norm_artist, cand_artist)

            # Weight title slightly higher than artist (60/40)
            score = 0.6 * title_sim + 0.4 * artist_sim

            if score > best_score:
                best_score = score
                best_cand = cand

        if best_cand and best_score >= 0.82:
            status = MatchStatus.MATCHED
        elif best_cand and best_score >= 0.65:
            status = MatchStatus.AMBIGUOUS
        else:
            status = MatchStatus.UNMATCHED

        is_matched = status != MatchStatus.UNMATCHED
        result = TrackMatchResult(
            catalog_track_id=catalog_track_id,
            catalog_title=title,
            catalog_artist=artist,
            catalog_isrc=isrc,
            status=status,
            confidence=round(max(0.0, best_score), 3) if best_cand else 0.0,
            platform_track_id=best_cand.get("id") if (best_cand and is_matched) else None,
            platform_uri=best_cand.get("uri") if (best_cand and is_matched) else None,
            platform_title=best_cand.get("title") if (best_cand and is_matched) else None,
            platform_artist=best_cand.get("artist") if (best_cand and is_matched) else None,
            match_strategy="fuzzy" if is_matched else "none",
        )
        self._cache[cache_key] = result
        return result

    async def match_batch(
        self,
        tracks: list[dict[str, Any]],
    ) -> list[TrackMatchResult]:
        """Match a batch of tracks sequentially or in parallel."""
        results: list[TrackMatchResult] = []
        for t in tracks:
            tid = t.get("track_id") or t.get("id", "")
            title = t.get("title", "")
            artist = t.get("artist") or t.get("artist_name", "")
            isrc = t.get("isrc")
            if not isrc and isinstance(t.get("isrcs"), list) and t["isrcs"]:
                isrc = t["isrcs"][0]

            res = await self.match_track(
                catalog_track_id=tid,
                title=title,
                artist=artist,
                isrc=isrc,
            )
            results.append(res)
        return results
