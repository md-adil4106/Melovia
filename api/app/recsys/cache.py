"""In-process thread-safe TTL candidate pool cache for Melovia.

Stores full CandidatePool and Modes for 30 minutes to enable sub-100ms
interactive steering and re-ranking without repeating candidate generation.
"""

import threading
import time
from dataclasses import dataclass

from app.recsys.candidates import CandidatePool
from app.recsys.config import RecsysConfig
from app.recsys.scoring import ScoredList


@dataclass
class CachedCandidateSet:
    candidate_set_id: str
    pool: CandidatePool
    scored_list: ScoredList
    config: RecsysConfig
    created_at: float
    latest_reranked: ScoredList | None = None
    discovery: float = 0.35


class CandidateCache:
    """Thread-safe TTL in-memory cache for candidate sets."""

    def __init__(self, default_ttl_seconds: int = 1800) -> None:
        self._default_ttl = default_ttl_seconds
        self._cache: dict[str, CachedCandidateSet] = {}
        self._lock = threading.Lock()

    def set(
        self,
        candidate_set_id: str,
        pool: CandidatePool,
        scored_list: ScoredList,
        config: RecsysConfig,
        latest_reranked: ScoredList | None = None,
        discovery: float = 0.35,
    ) -> None:
        """Store candidate pool and scored list in cache with current timestamp."""
        now = time.time()
        with self._lock:
            self._evict_expired(now)
            self._cache[candidate_set_id] = CachedCandidateSet(
                candidate_set_id=candidate_set_id,
                pool=pool,
                scored_list=scored_list,
                config=config,
                created_at=now,
                latest_reranked=latest_reranked,
                discovery=discovery,
            )

    def update_reranked(
        self,
        candidate_set_id: str,
        latest_reranked: ScoredList,
        discovery: float,
    ) -> None:
        """Update cached set with latest reranked result and discovery level."""
        with self._lock:
            entry = self._cache.get(candidate_set_id)
            if entry:
                entry.latest_reranked = latest_reranked
                entry.discovery = discovery

    def get(self, candidate_set_id: str) -> CachedCandidateSet | None:
        """Retrieve cached candidate set if present and not expired."""
        now = time.time()
        with self._lock:
            entry = self._cache.get(candidate_set_id)
            if entry is None:
                return None
            if now - entry.created_at > entry.config.ttl_seconds:
                del self._cache[candidate_set_id]
                return None
            return entry

    def _evict_expired(self, current_time: float) -> None:
        """Internal helper to remove expired entries."""
        expired_keys = [
            k
            for k, entry in self._cache.items()
            if current_time - entry.created_at > entry.config.ttl_seconds
        ]
        for k in expired_keys:
            del self._cache[k]

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._cache)


# Global singleton cache instance for the API process
global_candidate_cache = CandidateCache()
