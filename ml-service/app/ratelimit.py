"""Tiny in-memory fixed-window rate limiter. No external dependency — the
ml-service is single-instance for the pilot. Swap for Redis if it ever scales out."""
from __future__ import annotations

import threading
import time


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max = max_requests
        self.window = window_seconds
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        now = time.time()
        cutoff = now - self.window
        with self._lock:
            hits = [t for t in self._hits.get(key, []) if t > cutoff]
            if len(hits) >= self.max:
                retry_after = int(self.window - (now - hits[0])) + 1
                self._hits[key] = hits
                return False, max(retry_after, 1)
            hits.append(now)
            self._hits[key] = hits
            return True, 0
