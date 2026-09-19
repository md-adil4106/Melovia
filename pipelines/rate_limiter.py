"""Rate limiting and on-disk caching for external music metadata queries.

Enforces:
- 1 request/second rate limiting for MusicBrainz API.
- Mandatory User-Agent header from env or default.
- File-based on-disk caching to prevent redundant requests.
"""

import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_USER_AGENT = "Melovia/0.1.0 ( https://github.com/md-adil4106/Melovia )"


class RateLimiter:
    """Thread-safe rate limiter ensuring a minimum interval between calls."""

    def __init__(self, requests_per_second: float = 1.0) -> None:
        self.interval = 1.0 / max(0.01, requests_per_second)
        self._last_call: float = 0.0

    def wait(self) -> float:
        """Wait if needed until the minimum interval has elapsed. Returns elapsed wait time."""
        now = time.monotonic()
        elapsed = now - self._last_call
        wait_time = max(0.0, self.interval - elapsed)
        if wait_time > 0:
            time.sleep(wait_time)
        self._last_call = time.monotonic()
        return wait_time


class DiskCache:
    """Simple on-disk JSON cache using hashed URL filenames."""

    def __init__(self, cache_dir: Path | str) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _hash_key(self, key: str) -> str:
        return hashlib.sha256(key.encode("utf-8")).hexdigest() + ".json"

    def get(self, key: str) -> dict[str, Any] | None:
        path = self.cache_dir / self._hash_key(key)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)  # type: ignore[no-any-return]
        except Exception:
            return None

    def set(self, key: str, data: dict[str, Any]) -> None:
        path = self.cache_dir / self._hash_key(key)
        try:
            temp_path = path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            temp_path.replace(path)
        except Exception:
            pass


def get_user_agent() -> str:
    """Retrieve User-Agent header from environment or default."""
    return os.environ.get("MUSICBRAINZ_USER_AGENT", DEFAULT_USER_AGENT)


def fetch_with_rate_limit(
    url: str,
    limiter: RateLimiter,
    cache: DiskCache | None = None,
    timeout: float = 10.0,
) -> dict[str, Any] | None:
    """Fetch JSON with disk cache check and rate limiter enforcement."""
    if cache:
        cached = cache.get(url)
        if cached is not None:
            return cached

    limiter.wait()

    headers = {
        "User-Agent": get_user_agent(),
        "Accept": "application/json",
    }
    req = Request(url, headers=headers)

    try:
        with urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                raw_bytes = response.read()
                data: dict[str, Any] = json.loads(raw_bytes.decode("utf-8"))
                if cache:
                    cache.set(url, data)
                return data
    except HTTPError as e:
        if e.code == 404:
            return None
        raise
    except URLError:
        return None

    return None
