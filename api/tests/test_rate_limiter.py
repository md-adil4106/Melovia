"""Unit tests for rate limiter and disk caching."""

import time
from pathlib import Path

from pipelines.rate_limiter import DiskCache, RateLimiter


def test_rate_limiter_enforces_interval() -> None:
    """RateLimiter must delay rapid successive calls to respect requests_per_second."""
    limiter = RateLimiter(requests_per_second=10.0)  # 0.10s interval

    t0 = time.monotonic()
    limiter.wait()  # First call immediate
    wait1 = limiter.wait()  # Second call should wait ~0.10s
    t1 = time.monotonic()

    elapsed = t1 - t0
    assert elapsed >= 0.08, f"Expected elapsed >= 0.08s, got {elapsed:.3f}s"
    assert wait1 > 0.0


def test_disk_cache_operations(tmp_path: Path) -> None:
    """DiskCache must store, retrieve, and handle cache misses properly."""
    cache = DiskCache(tmp_path / "test_cache")

    # Miss
    assert cache.get("https://example.com/api/item1") is None

    # Set and hit
    payload = {"id": 123, "name": "Melovia Track"}
    cache.set("https://example.com/api/item1", payload)

    cached = cache.get("https://example.com/api/item1")
    assert cached == payload

    # Different key miss
    assert cache.get("https://example.com/api/item2") is None
