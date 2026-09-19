"""Cleaning, normalization, noise filtering, and deduplication logic for Melovia catalog."""

from dataclasses import dataclass, field
import math
import re
import unicodedata
from typing import Any
import uuid

# Compiled patterns for detecting unwanted variants in titles
LIVE_PATTERN = re.compile(
    r"(\b(live\s+at|live\s+from|in\s+concert|recorded\s+live|live\s+version|live\s+in|live\s+session)\b|\(\s*live[^)]*\)|\[\s*live[^\]]*\]|\s+-\s+live\b|\s+live\s*$)",
    re.IGNORECASE,
)

REMIX_PATTERN = re.compile(
    r"(\b(remix|remixed|club\s+mix|extended\s+mix|dub\s+mix|dance\s+mix|vip\s+mix|dj\s+edit)\b|\([^)]*remix[^)]*\)|\[[^\]]*remix[^\]]*\])",
    re.IGNORECASE,
)
KARAOKE_PATTERN = re.compile(
    r"(\b(karaoke|backing\s+track|tribute\s+to|in\s+the\s+style\s+of)\b|\(\s*karaoke[^)]*\)|\[\s*karaoke[^\]]*\])",
    re.IGNORECASE,
)
INSTRUMENTAL_VARIANT_PATTERN = re.compile(
    r"(\b(instrumental\s+version|piano\s+version|acoustic\s+version|karaoke\s+version)\b|\(\s*instrumental\s+version[^)]*\)|\[\s*instrumental\s+version[^\]]*\])",
    re.IGNORECASE,
)
VIDEO_PATTERN = re.compile(
    r"(\b(music\s+video|official\s+video|lyric\s+video|video\s+version|visualizer)\b|\(\s*video\s+version[^)]*\)|\[\s*video\s+version[^\]]*\])",
    re.IGNORECASE,
)


@dataclass
class RawRecording:
    """Raw recording entity parsed from dumps or external APIs."""

    mbid: str
    title: str
    artist_name: str
    artist_mbid: str | None = None
    year: int | None = None
    isrcs: list[str] = field(default_factory=list)
    tags: list[dict[str, Any]] = field(default_factory=list)
    listen_count: int = 0
    disambiguation: str | None = None
    secondary_types: list[str] = field(default_factory=list)
    scalars: dict[str, Any] | None = None


@dataclass
class CleanedRecording:
    """Final sanitized, deduplicated recording ready for staging table insertion."""

    id: str
    mbid: str | None
    title: str
    artist_name: str
    artist_mbid: str | None
    year: int | None
    isrcs: list[str]
    popularity_pct: float
    has_a: bool
    has_t: bool
    tags: list[dict[str, Any]]
    scalars: dict[str, Any] | None
    source: str = "real_staging"


def normalize_text(text: str) -> str:
    """Normalize unicode characters, collapse whitespace, and trim."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    cleaned = "".join(c for c in normalized if not unicodedata.combining(c))
    return " ".join(cleaned.split()).strip()


def canonical_match_key(title: str, artist: str) -> tuple[str, str]:
    """Generate normalized, stripped tuple key for fuzzy title and artist matching."""
    norm_title = re.sub(r"[^\w\s]", "", normalize_text(title).lower())
    norm_artist = re.sub(r"[^\w\s]", "", normalize_text(artist).lower())
    return " ".join(norm_title.split()), " ".join(norm_artist.split())


def is_noise_variant(
    title: str,
    disambiguation: str | None = None,
    secondary_types: list[str] | None = None,
) -> bool:
    """Identify live, remix, karaoke, video, or alternate version recordings."""
    # 1. MusicBrainz secondary types flags
    if secondary_types:
        lowered_types = {st.lower() for st in secondary_types}
        forbidden_types = {"live", "remix", "karaoke", "spokenword", "interview"}
        if lowered_types.intersection(forbidden_types):
            return True

    # 2. MusicBrainz disambiguation comment
    if disambiguation:
        dis_lower = disambiguation.lower()
        if any(
            kw in dis_lower
            for kw in [
                "live",
                "remix",
                "karaoke",
                "instrumental version",
                "acoustic version",
                "video",
                "backing track",
                "tribute",
            ]
        ):
            return True

    # 3. Title regex heuristics
    clean_title = normalize_text(title)
    if LIVE_PATTERN.search(clean_title):
        return True
    if REMIX_PATTERN.search(clean_title):
        return True
    if KARAOKE_PATTERN.search(clean_title):
        return True
    if INSTRUMENTAL_VARIANT_PATTERN.search(clean_title):
        return True
    if VIDEO_PATTERN.search(clean_title):
        return True

    return False


def _merge_recordings(winner: RawRecording, loser: RawRecording) -> RawRecording:
    """Merge duplicate recordings, prioritizing earliest release year and richest tags."""
    # Earliest valid year
    if loser.year and (not winner.year or (1900 <= loser.year < winner.year)):
        winner.year = loser.year

    # Maximize listen count
    winner.listen_count = max(winner.listen_count, loser.listen_count)

    # Union of unique ISRCs
    combined_isrcs = list(dict.fromkeys(winner.isrcs + loser.isrcs))
    winner.isrcs = combined_isrcs

    # Merge tags
    tag_map: dict[str, dict[str, Any]] = {t["name"]: t for t in winner.tags}
    for t in loser.tags:
        if t["name"] not in tag_map:
            tag_map[t["name"]] = t
        else:
            # Boost weight slightly if present in multiple records
            tag_map[t["name"]]["weight"] = min(1.0, tag_map[t["name"]].get("weight", 1.0) + 0.1)
    winner.tags = list(tag_map.values())

    # Merge scalars if missing
    if not winner.scalars and loser.scalars:
        winner.scalars = loser.scalars

    return winner


def deduplicate_recordings(recordings: list[RawRecording]) -> list[RawRecording]:
    """Execute multi-pass deduplication by MBID, ISRC, and canonical (title, artist)."""
    # Filter noise first
    valid_recs = [
        r
        for r in recordings
        if not is_noise_variant(r.title, r.disambiguation, r.secondary_types)
    ]

    # Pass 1: Dedupe by MBID
    by_mbid: dict[str, RawRecording] = {}
    for r in valid_recs:
        if r.mbid:
            if r.mbid in by_mbid:
                by_mbid[r.mbid] = _merge_recordings(by_mbid[r.mbid], r)
            else:
                by_mbid[r.mbid] = r
        else:
            # Placeholder key for empty MBID
            by_mbid[str(uuid.uuid4())] = r

    recs_after_mbid = list(by_mbid.values())

    # Pass 2: Dedupe by ISRC
    by_isrc: dict[str, RawRecording] = {}
    remaining_after_isrc: list[RawRecording] = []
    for r in recs_after_mbid:
        primary_isrc = r.isrcs[0] if r.isrcs else None
        if primary_isrc:
            if primary_isrc in by_isrc:
                by_isrc[primary_isrc] = _merge_recordings(by_isrc[primary_isrc], r)
            else:
                by_isrc[primary_isrc] = r
        else:
            remaining_after_isrc.append(r)

    recs_after_isrc = list(by_isrc.values()) + remaining_after_isrc

    # Pass 3: Dedupe by canonical (title, primary_artist)
    by_title_artist: dict[tuple[str, str], RawRecording] = {}
    for r in recs_after_isrc:
        key = canonical_match_key(r.title, r.artist_name)
        if key in by_title_artist:
            by_title_artist[key] = _merge_recordings(by_title_artist[key], r)
        else:
            by_title_artist[key] = r

    return list(by_title_artist.values())


def compute_popularity_percentiles(recordings: list[RawRecording]) -> dict[str, float]:
    """Compute log-percentile popularity score in [1.0, 99.5] from listen counts."""
    if not recordings:
        return {}

    # Calculate log-transformed score: log(1 + listen_count)
    scores = [(r.mbid, math.log1p(max(0, r.listen_count))) for r in recordings]
    # Sort by score ascending
    scores.sort(key=lambda item: item[1])

    n = len(scores)
    if n == 1:
        return {scores[0][0]: 50.0}

    percentiles: dict[str, float] = {}
    for rank, (mbid, _) in enumerate(scores):
        # Scale rank linearly between 1.0 and 99.5
        pct = 1.0 + (rank / (n - 1)) * 98.5
        percentiles[mbid] = round(pct, 2)

    return percentiles
