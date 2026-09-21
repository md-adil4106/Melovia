"""Live Public Music Search Service using the iTunes Search API.

Provides free, public, real-time access to commercial and independent music releases
up to today's date with zero authentication keys required.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Genre-to-heuristic scalars mapping for dynamic tracks
GENRE_SCALARS: dict[str, dict[str, float]] = {
    "hip-hop/rap": {
        "bpm": 130.0,
        "energy": 0.75,
        "valence": 0.55,
        "danceability": 0.80,
        "acousticness": 0.15,
    },
    "rap": {
        "bpm": 130.0,
        "energy": 0.75,
        "valence": 0.55,
        "danceability": 0.80,
        "acousticness": 0.15,
    },
    "hip-hop": {
        "bpm": 130.0,
        "energy": 0.75,
        "valence": 0.55,
        "danceability": 0.80,
        "acousticness": 0.15,
    },
    "pop": {
        "bpm": 120.0,
        "energy": 0.70,
        "valence": 0.65,
        "danceability": 0.75,
        "acousticness": 0.20,
    },
    "r&b/soul": {
        "bpm": 105.0,
        "energy": 0.55,
        "valence": 0.55,
        "danceability": 0.65,
        "acousticness": 0.35,
    },
    "rock": {
        "bpm": 125.0,
        "energy": 0.80,
        "valence": 0.50,
        "danceability": 0.55,
        "acousticness": 0.15,
    },
    "alternative": {
        "bpm": 120.0,
        "energy": 0.70,
        "valence": 0.45,
        "danceability": 0.60,
        "acousticness": 0.25,
    },
    "electronic": {
        "bpm": 128.0,
        "energy": 0.85,
        "valence": 0.60,
        "danceability": 0.80,
        "acousticness": 0.10,
    },
    "dance": {
        "bpm": 128.0,
        "energy": 0.85,
        "valence": 0.65,
        "danceability": 0.85,
        "acousticness": 0.08,
    },
    "indie": {
        "bpm": 115.0,
        "energy": 0.60,
        "valence": 0.45,
        "danceability": 0.55,
        "acousticness": 0.40,
    },
    "ambient": {
        "bpm": 70.0,
        "energy": 0.20,
        "valence": 0.35,
        "danceability": 0.25,
        "acousticness": 0.80,
    },
    "classical": {
        "bpm": 80.0,
        "energy": 0.30,
        "valence": 0.30,
        "danceability": 0.20,
        "acousticness": 0.90,
    },
    "jazz": {
        "bpm": 110.0,
        "energy": 0.50,
        "valence": 0.55,
        "danceability": 0.60,
        "acousticness": 0.65,
    },
    "country": {
        "bpm": 115.0,
        "energy": 0.65,
        "valence": 0.60,
        "danceability": 0.60,
        "acousticness": 0.45,
    },
    "latin": {
        "bpm": 115.0,
        "energy": 0.80,
        "valence": 0.75,
        "danceability": 0.85,
        "acousticness": 0.25,
    },
}


class LiveSearchService:
    """Asynchronous client for querying public music releases."""

    SEARCH_URL = "https://itunes.apple.com/search"
    LOOKUP_URL = "https://itunes.apple.com/lookup"

    def __init__(self, cache_ttl_seconds: int = 600) -> None:
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._query_cache: dict[str, tuple[datetime, list[dict[str, Any]]]] = {}
        self._track_cache: dict[str, tuple[datetime, dict[str, Any]]] = {}

    def _clean_cache(self) -> None:
        now = datetime.now()
        if len(self._query_cache) > 200:
            self._query_cache = {
                k: v for k, v in self._query_cache.items() if now - v[0] < self.cache_ttl
            }
        if len(self._track_cache) > 500:
            self._track_cache = {
                k: v for k, v in self._track_cache.items() if now - v[0] < self.cache_ttl
            }

    @staticmethod
    def _normalize_itunes_track(item: dict[str, Any]) -> dict[str, Any] | None:
        track_id = item.get("trackId")
        title = item.get("trackName")
        artist = item.get("artistName")
        if not track_id or not title or not artist:
            return None

        # Determine release year
        year: int | None = None
        release_date = item.get("releaseDate")
        if release_date and isinstance(release_date, str) and len(release_date) >= 4:
            try:
                year = int(release_date[:4])
            except ValueError:
                year = None

        primary_genre = (item.get("primaryGenreName") or "Music").strip()
        genre_key = primary_genre.lower().replace(" ", "-")

        # Tags extraction
        tags = [primary_genre.lower()]
        if "/" in primary_genre:
            for part in primary_genre.split("/"):
                tags.append(part.strip().lower())
        if "hip-hop" in genre_key or "rap" in genre_key:
            tags.extend(["hip-hop", "rap", "urban"])
        elif "rock" in genre_key:
            tags.extend(["rock", "guitar"])
        elif "pop" in genre_key:
            tags.extend(["pop", "vocal"])

        # Determine audio scalars proxy
        scalars_preset = GENRE_SCALARS.get(genre_key, GENRE_SCALARS.get("pop", {}))
        scalars = {
            "bpm": scalars_preset.get("bpm", 120.0),
            "tempo_bpm": scalars_preset.get("bpm", 120.0),
            "energy": scalars_preset.get("energy", 0.60),
            "valence": scalars_preset.get("valence", 0.50),
            "danceability": scalars_preset.get("danceability", 0.65),
            "acousticness": scalars_preset.get("acousticness", 0.25),
            "instrumentalness": 0.05,
            "loudness_db": -8.0,
        }

        canonical_id = f"ext:itunes:{track_id}"
        artist_seed_str = f"itunes.artist.{item.get('artistId', artist)}"
        artist_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, artist_seed_str))

        return {
            "id": canonical_id,
            "track_idx": -1,
            "mbid": None,
            "title": str(title),
            "artist_id": artist_id,
            "artist_name": str(artist),
            "album_name": item.get("collectionName"),
            "year": year,
            "isrcs": [],
            "popularity_pct": 75.0,  # Live tracks have strong baseline familiarity
            "has_a": False,  # Missing precomputed acoustic audio features (compliant invariant)
            "has_t": True,  # Has semantic genre & descriptive tags
            "region_id": None,
            "scalars": scalars,
            "tags": sorted(set(tags)),
            "artwork_url": item.get("artworkUrl100") or item.get("artworkUrl60"),
            "preview_url": item.get("previewUrl"),
            "source": "itunes_live",
        }

    async def search_tracks(self, query: str, limit: int = 15) -> list[dict[str, Any]]:
        """Search public tracks by query string."""
        q_clean = query.strip()
        if len(q_clean) < 2:
            return []

        cache_key = f"{q_clean.lower()}:{limit}"
        now = datetime.now()

        # Check cache
        if cache_key in self._query_cache:
            ts, cached_res = self._query_cache[cache_key]
            if now - ts < self.cache_ttl:
                return cached_res

        self._clean_cache()

        params: dict[str, str | int] = {
            "term": q_clean,
            "entity": "song",
            "limit": limit,
            "media": "music",
        }

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(self.SEARCH_URL, params=params)
                if response.status_code != 200:
                    logger.warning(
                        "iTunes search returned status %d for query %s",
                        response.status_code,
                        q_clean,
                    )
                    return []

                data = response.json()
                raw_results = data.get("results", [])

                normalized: list[dict[str, Any]] = []
                for item in raw_results:
                    parsed = self._normalize_itunes_track(item)
                    if parsed:
                        normalized.append(parsed)
                        self._track_cache[parsed["id"]] = (now, parsed)

                self._query_cache[cache_key] = (now, normalized)
                return normalized

        except Exception as exc:
            logger.warning("Failed to query iTunes search API: %s", exc)
            return []

    async def get_track_by_id(self, ext_id: str) -> dict[str, Any] | None:
        """Lookup external track by canonical ext:itunes:{trackId}."""
        now = datetime.now()
        if ext_id in self._track_cache:
            ts, track = self._track_cache[ext_id]
            if now - ts < self.cache_ttl:
                return track

        if not ext_id.startswith("ext:itunes:"):
            return None

        track_id = ext_id.split("ext:itunes:")[-1]
        lookup_params: dict[str, str] = {"id": str(track_id)}
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(self.LOOKUP_URL, params=lookup_params)
                if response.status_code != 200:
                    return None

                data = response.json()
                results = data.get("results", [])
                if not results:
                    return None

                parsed = self._normalize_itunes_track(results[0])
                if parsed:
                    self._track_cache[ext_id] = (now, parsed)
                    return parsed
        except Exception as exc:
            logger.warning("Failed to lookup track %s: %s", ext_id, exc)

        return None


# Global singleton service
live_search_service = LiveSearchService()
