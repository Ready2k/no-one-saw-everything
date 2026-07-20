"""A minimal in-process rate limiter.

The session store is already single-process, in-memory, one-worker-only (see
session.py); a rate limiter with the same constraint is consistent with that,
not a new limitation. This exists to stop one detective (accidentally or on
purpose) hammering the LLM-backed and case-generation routes — both of which
either cost real provider money/latency or do meaningful CPU/disk work.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Callable


class RateLimiter:
    """Sliding-window limiter: at most `max_requests` per `window_seconds`, per key."""

    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        time_func: Callable[[], float] = time.monotonic,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._time_func = time_func
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self._time_func()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > self.window_seconds:
                q.popleft()
            if len(q) >= self.max_requests:
                return False
            q.append(now)
            return True

    def retry_after_seconds(self, key: str) -> float:
        with self._lock:
            q = self._hits.get(key)
            if not q:
                return 0.0
            return max(0.0, self.window_seconds - (self._time_func() - q[0]))

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
