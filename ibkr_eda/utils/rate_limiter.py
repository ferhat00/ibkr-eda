"""Simple token-bucket rate limiter for IBKR API (10 req/sec)."""

import threading
import time


class RateLimiter:
    """Thread-safe rate limiter using minimum interval between requests."""

    def __init__(self, max_per_second: int = 10):
        self._interval = 1.0 / max_per_second
        self._lock = threading.Lock()
        self._last_call = 0.0

    def wait(self) -> None:
        """Block until enough time has elapsed since the last call."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self._interval:
                time.sleep(self._interval - elapsed)
            self._last_call = time.monotonic()
