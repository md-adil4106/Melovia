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
    "bollywood": {
        "bpm": 95.0,
        "energy": 0.55,
        "valence": 0.60,
        "danceability": 0.60,
        "acousticness": 0.45,
    },
    "indian-pop": {
        "bpm": 100.0,
        "energy": 0.60,
        "valence": 0.65,
        "danceability": 0.65,
        "acousticness": 0.40,
    },
    "indian": {
        "bpm": 95.0,
        "energy": 0.55,
        "valence": 0.60,
        "danceability": 0.60,
        "acousticness": 0.50,
    },
    "k-pop": {
        "bpm": 125.0,
        "energy": 0.85,
        "valence": 0.70,
        "danceability": 0.85,
        "acousticness": 0.12,
    },
}


def classify_genre_and_culture(primary_genre: str, tags: list[str] | None = None) -> str:
    """Classify genre and cultural market into a coherent domain."""
    text = (primary_genre or "").lower().replace("-", " ")
    if tags:
        text += " " + " ".join(str(t).lower().replace("-", " ") for t in tags)

    # 1. Bollywood / Desi / Indian
    if any(
        term in text
        for term in (
            "bollywood",
            "indian pop",
            "indian",
            "filmi",
            "sufi",
            "ghazal",
            "punjabi",
            "hindi",
            "tamil",
            "telugu",
            "malayalam",
            "bengali",
            "desi",
            "bhangra",
            "qawwali",
        )
    ):
        return "bollywood_desi"

    # 2. K-Pop
    if "k pop" in text or "kpop" in text or "korean" in text:
        return "kpop"

    # 3. Latin
    if any(
        term in text
        for term in ("latin", "reggaeton", "urbano", "salsa", "bachata", "cumbia", "corridos")
    ):
        return "latin"

    # 4. Hip-Hop / Rap
    if any(term in text for term in ("hip hop", "rap", "trap", "drill", "cloud rap")):
        return "hiphop"

    # 5. R&B / Soul
    if any(term in text for term in ("r&b", "soul", "neo soul", "funk")):
        return "rnb"

    # 6. Rock / Alternative
    if any(
        term in text for term in ("rock", "metal", "punk", "alternative", "grunge", "indie rock")
    ):
        return "rock"

    # 7. Western Pop
    if any(
        term in text for term in ("pop", "dance", "synth pop", "disco", "electro pop", "teen pop")
    ):
        return "western_pop"

    # 8. Electronic / Dance
    if any(
        term in text
        for term in ("electronic", "edm", "house", "techno", "trance", "dnb", "dubstep")
    ):
        return "electronic"

    return "general"


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

        artist_str = str(artist)
        title_str = str(title)
        artist_lower = artist_str.lower()
        title_lower = title_str.lower()
        if any(
            bad in artist_lower or bad in title_lower
            for bad in ("karaoke", "tribute", "backing track", "royalty free")
        ):
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

        # Tags extraction (using recognized vocabulary terms)
        tags = [primary_genre.lower()]
        if "/" in primary_genre:
            for part in primary_genre.split("/"):
                tags.append(part.strip().lower())
        culture = classify_genre_and_culture(primary_genre, tags)
        if culture == "bollywood_desi":
            tags.extend(["bollywood", "indian-pop", "acoustic", "melodic", "soul"])
            genre_key = "bollywood"
        elif culture == "hiphop":
            tags.extend(["hip-hop", "trap", "cloud-rap", "bass"])
            genre_key = "hip-hop"
        elif culture == "kpop":
            tags.extend(["k-pop", "dance", "electronic", "groove"])
            genre_key = "k-pop"
        elif culture == "latin":
            tags.extend(["latin", "dance", "groove"])
            genre_key = "latin"
        elif culture == "western_pop":
            tags.extend(["pop", "dance", "electronic", "groove"])
            genre_key = "pop"
        elif culture == "rock":
            tags.extend(["rock", "guitar", "raw", "alternative"])
            genre_key = "rock"
        elif culture == "rnb":
            tags.extend(["soul", "neo-soul", "groove", "smooth"])
            genre_key = "r&b/soul"

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
            "culture": culture,
            "artwork_url": item.get("artworkUrl100") or item.get("artworkUrl60"),
            "preview_url": item.get("previewUrl"),
            "source": "itunes_live",
        }

    async def search_tracks(
        self,
        query: str,
        limit: int = 15,
        country: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search public tracks by query string with storefront routing."""
        q_clean = query.strip()
        if len(q_clean) < 2:
            return []

        # Determine target storefront country
        target_country = country
        if not target_country:
            q_lower = q_clean.lower()
            if any(
                term in q_lower
                for term in (
                    "khat", "sajde", "guzarish", "arijit", "pritam", "rahman", "javed ali",
                    "faheem", "atif", "mohit chauhan", "navjot", "bollywood", "hindi",
                    "punjabi", "sonu nigam", "shreya ghoshal", "anuv jain", "prateek kuhad",
                    "jasleen royal", "kk", "armaan malik", "darshan raval", "jubin nautiyal",
                    "diljit", "sidhu", "ap dhillon", "badshah", "honey singh", "desi", "sufi"
                )
            ):
                target_country = "IN"
            elif any(
                term in q_lower
                for term in ("bts", "blackpink", "newjeans", "stray kids", "twice")
            ):
                target_country = "KR"
            elif any(
                term in q_lower
                for term in ("bad bunny", "peso pluma", "karol g", "reggaeton")
            ):
                target_country = "MX"
            else:
                target_country = "US"

        cache_key = f"{q_clean.lower()}:{limit}:{target_country}"
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
            "country": target_country,
        }

        try:
            async with httpx.AsyncClient(timeout=3.5) as client:
                response = await client.get(self.SEARCH_URL, params=params)
                if response.status_code == 200:
                    data = response.json()
                    raw_results = data.get("results", [])
                else:
                    raw_results = []

                # Fallback probe if 0 results on regional storefront
                if not raw_results:
                    alt_country = "IN" if target_country != "IN" else "US"
                    params["country"] = alt_country
                    alt_resp = await client.get(self.SEARCH_URL, params=params)
                    if alt_resp.status_code == 200:
                        raw_results = alt_resp.json().get("results", [])

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
            async with httpx.AsyncClient(timeout=3.5) as client:
                for country in ("IN", "US"):
                    lookup_params["country"] = country
                    response = await client.get(self.LOOKUP_URL, params=lookup_params)
                    if response.status_code == 200:
                        data = response.json()
                        results = data.get("results", [])
                        if results:
                            parsed = self._normalize_itunes_track(results[0])
                            if parsed:
                                self._track_cache[ext_id] = (now, parsed)
                                return parsed
        except Exception as exc:
            logger.warning("Failed to lookup track %s: %s", ext_id, exc)
            return None
        return None

    async def fetch_candidates_for_seeds(
        self,
        seed_tracks: list[dict[str, Any]],
        limit_per_query: int = 15,
    ) -> list[dict[str, Any]]:
        """Retrieve real-world candidate tracks matching seed artists and genre vibes."""
        candidates: list[dict[str, Any]] = []
        seen_ids = {str(s.get("id")) for s in seed_tracks}
        seen_keys = {
            (
                str(s.get("title", "")).lower().strip(),
                str(s.get("artist_name", "")).lower().strip(),
            )
            for s in seed_tracks
        }

        # 1. Gather distinct artists, genres, and cultures from seeds
        seed_artists: list[str] = []
        seed_cultures: set[str] = set()

        for s in seed_tracks:
            art = s.get("artist_name")
            if art and str(art) not in seed_artists:
                seed_artists.append(str(art))

            genre = str(s.get("genre") or s.get("primaryGenreName") or "")
            tags = list(s.get("tags") or [])
            culture = s.get("culture") or classify_genre_and_culture(genre, tags)
            seed_cultures.add(culture)

        # Determine primary market country based on seed cultures
        primary_country = "IN" if "bollywood_desi" in seed_cultures else "US"
        if "kpop" in seed_cultures:
            primary_country = "KR"
        elif "latin" in seed_cultures:
            primary_country = "MX"

        # 2. Formulate search queries based on seed artists
        search_queries = list(seed_artists)

        # 3. Add genre- and culture-specific peer discovery query terms
        if "bollywood_desi" in seed_cultures:
            search_queries.extend([
                "Arijit Singh romantic",
                "Pritam romantic hits",
                "Mohit Chauhan romantic",
                "Atif Aslam romantic",
                "Faheem Abdullah hits",
                "Anuv Jain hits",
                "bollywood romantic hits",
                "hindi romcom songs",
                "Jasleen Royal romantic",
                "KK romantic hits",
                "Javed Ali romantic hits",
                "Sonu Nigam romantic hits",
            ])
        elif "hiphop" in seed_cultures:
            search_queries.extend([
                "Travis Scott",
                "Metro Boomin",
                "Future",
                "21 Savage",
                "Gunna",
                "Lil Baby",
                "Playboi Carti",
                "Drake",
                "Kendrick Lamar",
            ])
        elif "rock" in seed_cultures:
            search_queries.extend([
                "Arctic Monkeys",
                "The Strokes",
                "Tame Impala",
                "Nirvana",
                "Radiohead",
            ])
        elif "western_pop" in seed_cultures:
            search_queries.extend([
                "The Weeknd",
                "Dua Lipa",
                "Billie Eilish",
                "Olivia Rodrigo",
                "Taylor Swift",
                "Post Malone",
                "Ariana Grande",
            ])
        elif "rnb" in seed_cultures:
            search_queries.extend([
                "SZA",
                "Frank Ocean",
                "Brent Faiyaz",
                "Daniel Caesar",
                "Giveon",
            ])
        elif "kpop" in seed_cultures:
            search_queries.extend([
                "BTS",
                "NewJeans",
                "BLACKPINK",
                "Stray Kids",
                "LE SSERAFIM",
                "TWICE",
            ])
        elif "latin" in seed_cultures:
            search_queries.extend([
                "Bad Bunny",
                "J Balvin",
                "Rauw Alejandro",
                "Karol G",
                "Feid",
                "Peso Pluma",
            ])

        # Deduplicate search queries while preserving order
        unique_queries: list[str] = []
        seen_q: set[str] = set()
        for q in search_queries:
            q_clean = q.strip().lower()
            if q_clean not in seen_q:
                seen_q.add(q_clean)
                unique_queries.append(q)

        # Query iTunes for top queries using the targeted country storefront
        for q in unique_queries[:10]:
            results = await self.search_tracks(q, limit=limit_per_query, country=primary_country)
            for r in results:
                # Culture boundary guard: if seeds are Bollywood, exclude Western pop/rap candidates
                r_culture = r.get("culture") or classify_genre_and_culture(
                    str(r.get("primaryGenreName") or ""), r.get("tags")
                )
                if "bollywood_desi" in seed_cultures and r_culture in ("western_pop", "hiphop"):
                    continue
                if "hiphop" in seed_cultures and r_culture in ("bollywood_desi", "kpop"):
                    continue

                rid = str(r.get("id"))
                r_key = (
                    str(r.get("title", "")).lower().strip(),
                    str(r.get("artist_name", "")).lower().strip(),
                )
                if rid not in seen_ids and r_key not in seen_keys:
                    seen_ids.add(rid)
                    seen_keys.add(r_key)
                    candidates.append(r)

        return candidates


# Global singleton service
live_search_service = LiveSearchService()
