"""MusicBrainz metadata ingestion module."""

import json
from pathlib import Path
from typing import Any
import re

from pipelines.cleaner import RawRecording
from pipelines.rate_limiter import DiskCache, RateLimiter, fetch_with_rate_limit


def parse_musicbrainz_recording_dict(raw: dict[str, Any]) -> RawRecording:
    """Parse a MusicBrainz recording JSON object into a RawRecording entity."""
    mbid = str(raw.get("id") or raw.get("mbid", ""))
    title = str(raw.get("title", ""))

    # Artist credits
    artist_name = ""
    artist_mbid = None
    artist_credit = raw.get("artist-credit") or raw.get("artists")
    if artist_credit and isinstance(artist_credit, list):
        first_credit = artist_credit[0]
        if isinstance(first_credit, dict):
            artist_name = first_credit.get("name") or first_credit.get("artist", {}).get("name", "")
            artist_mbid = first_credit.get("artist", {}).get("id") or first_credit.get("id")
    if not artist_name:
        artist_name = str(raw.get("artist_name") or "Unknown Artist")

    # Earliest release year
    year: int | None = None
    first_release_date = raw.get("first-release-date") or raw.get("year") or raw.get("release_date")
    if first_release_date:
        match = re.search(r"\b(19\d\d|20\d\d)\b", str(first_release_date))
        if match:
            year = int(match.group(1))

    # ISRCs
    isrcs = []
    raw_isrcs = raw.get("isrcs") or raw.get("isrc_list", [])
    if isinstance(raw_isrcs, list):
        for item in raw_isrcs:
            if isinstance(item, str):
                isrcs.append(item)
            elif isinstance(item, dict) and "isrc" in item:
                isrcs.append(item["isrc"])

    # Disambiguation & Secondary Types
    disambiguation = raw.get("disambiguation")
    secondary_types = []
    releases = raw.get("releases", [])
    if isinstance(releases, list):
        for rel in releases:
            sec = rel.get("release-group", {}).get("secondary-types", [])
            if isinstance(sec, list):
                secondary_types.extend(sec)

    # Tags: recording-level (weight 1.0) + artist/release-group fallback (weight 0.5)
    tags: list[dict[str, Any]] = []
    seen_tag_names: set[str] = set()

    for t in raw.get("tags", []) + raw.get("genres", []):
        name = t.get("name") if isinstance(t, dict) else str(t)
        if name and name.lower() not in seen_tag_names:
            seen_tag_names.add(name.lower())
            tags.append({"name": name.lower(), "weight": 1.0, "source": "recording"})

    # Fallback artist tags if present
    for t in raw.get("artist_tags", []):
        name = t.get("name") if isinstance(t, dict) else str(t)
        if name and name.lower() not in seen_tag_names:
            seen_tag_names.add(name.lower())
            tags.append({"name": name.lower(), "weight": 0.5, "source": "artist_fallback"})

    return RawRecording(
        mbid=mbid,
        title=title,
        artist_name=artist_name,
        artist_mbid=artist_mbid,
        year=year,
        isrcs=isrcs,
        tags=tags,
        listen_count=int(raw.get("listen_count", 0)),
        disambiguation=disambiguation,
        secondary_types=secondary_types,
        scalars=raw.get("scalars"),
    )


def parse_musicbrainz_dump(file_path: Path) -> list[RawRecording]:
    """Parse MusicBrainz recording dump from JSON or JSONL file."""
    recordings: list[RawRecording] = []
    if not file_path.exists():
        return recordings

    with open(file_path, "r", encoding="utf-8") as f:
        first_line = f.readline().strip()
        f.seek(0)

        if first_line.startswith("["):
            data = json.load(f)
            for item in data:
                if isinstance(item, dict):
                    recordings.append(parse_musicbrainz_recording_dict(item))
        else:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                    recordings.append(parse_musicbrainz_recording_dict(item))
                except json.JSONDecodeError:
                    continue

    return recordings


def fetch_musicbrainz_recording(
    mbid: str,
    limiter: RateLimiter,
    cache: DiskCache | None = None,
) -> RawRecording | None:
    """Fetch recording metadata from MusicBrainz API with rate limiting and caching."""
    url = f"https://musicbrainz.org/ws/2/recording/{mbid}?inc=artists+releases+tags+genres+isrcs&fmt=json"
    data = fetch_with_rate_limit(url, limiter=limiter, cache=cache)
    if not data:
        return None
    return parse_musicbrainz_recording_dict(data)
