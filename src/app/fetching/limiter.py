from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable


@dataclass(slots=True)
class _TokenBucket:
    tokens: float
    last_refill: float


class RateLimiter:
    def __init__(self, sleep_func: Callable[[float], None] | None = None) -> None:
        self._sleep = sleep_func or time.sleep
        self._buckets: dict[str, _TokenBucket] = {}

    def acquire(self, key: str, qps: float, burst: int, max_concurrency: int) -> int:
        del max_concurrency  # The current scheduler is sequential; concurrency is reserved for future use.
        if qps <= 0:
            return 0

        now = time.monotonic()
        state = self._buckets.get(key)
        if state is None:
            state = _TokenBucket(tokens=float(max(1, burst)), last_refill=now)
            self._buckets[key] = state

        tokens = min(float(burst), state.tokens + (now - state.last_refill) * qps)
        waited_ms = 0
        if tokens < 1.0:
            wait_seconds = (1.0 - tokens) / qps
            self._sleep(wait_seconds)
            waited_ms = int(round(wait_seconds * 1000))
            now = time.monotonic()
            tokens = min(float(burst), tokens + wait_seconds * qps)

        state.tokens = max(0.0, tokens - 1.0)
        state.last_refill = now
        return waited_ms
