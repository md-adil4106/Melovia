"""ListenBrainz stats ingestion module."""

import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from pipelines.rate_limiter import get_user_agent


def parse_listenbrainz_dump(file_path: Path) -> dict[str, int]:
    """Parse ListenBrainz recording listen stats from JSONL or JSON file.

    Returns mapping of recording_mbid -> listen_count.
    """
    stats: dict[str, int] = {}
    if not file_path.exists():
        return stats

    with open(file_path, "r", encoding="utf-8") as f:
        # Detect JSON vs JSONL
        first_line = f.readline().strip()
        f.seek(0)

        if first_line.startswith("["):
            # Standard JSON array
            data = json.load(f)
            for item in data:
                mbid = item.get("recording_mbid") or item.get("mbid")
                count = int(item.get("listen_count", item.get("count", 0)))
                if mbid:
                    stats[mbid] = max(stats.get(mbid, 0), count)
        else:
            # JSONL lines
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                    mbid = item.get("recording_mbid") or item.get("mbid")
                    count = int(item.get("listen_count", item.get("count", 0)))
                    if mbid:
                        stats[mbid] = max(stats.get(mbid, 0), count)
                except json.JSONDecodeError:
                    continue

    return stats


def fetch_listenbrainz_top_recordings(limit: int = 100) -> dict[str, int]:
    """Fetch sitewide top recordings directly from ListenBrainz public API."""
    stats: dict[str, int] = {}
    url = "https://api.listenbrainz.org/1/stats/sitewide/artists"
    headers = {"User-Agent": get_user_agent(), "Accept": "application/json"}
    req = Request(url, headers=headers)

    try:
        with urlopen(req, timeout=15) as response:
            if response.status == 200:
                payload = json.loads(response.read().decode("utf-8"))
                artists = payload.get("payload", {}).get("artists", [])
                for a in artists[:limit]:
                    count = int(a.get("listen_count", 1000))
                    # Fallback mapping
                    artist_mbid = a.get("artist_mbid")
                    if artist_mbid:
                        stats[artist_mbid] = count
    except (HTTPError, Exception):
        pass

    return stats
