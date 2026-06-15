from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass
from typing import Callable, Mapping


DEFAULT_GROUP_LIMITS: dict[str, int] = {
    "AUTH": 5,
    "ACCOUNT": 1,
    "ASSET": 5,
    "STOCK": 5,
    "MARKET_INFO": 3,
    "MARKET_DATA": 10,
    "MARKET_DATA_CHART": 5,
    "ORDER": 6,
    "ORDER_HISTORY": 5,
    "ORDER_INFO": 6,
}


@dataclass
class _Bucket:
    limit: float
    tokens: float
    updated_at: float


class TossRateLimitManager:
    """Client-side token bucket for Toss Invest rate-limit groups."""

    def __init__(
        self,
        *,
        default_limits: Mapping[str, int] = DEFAULT_GROUP_LIMITS,
        min_request_interval: float = 1.0,
        sleep_func: Callable[[float], None] = time.sleep,
        monotonic_func: Callable[[], float] = time.monotonic,
        jitter_func: Callable[[float, float], float] = random.uniform,
    ):
        self._default_limits = dict(default_limits)
        self._min_request_interval = max(0.0, min_request_interval)
        self._sleep = sleep_func
        self._monotonic = monotonic_func
        self._jitter = jitter_func
        self._buckets: dict[str, _Bucket] = {}
        self._next_request_at = 0.0
        self._lock = threading.RLock()

    def wait(self, group: str) -> None:
        while True:
            with self._lock:
                bucket = self._bucket_for(group)
                self._refill(bucket)
                if bucket.tokens >= 1.0:
                    bucket.tokens -= 1.0
                    now = self._monotonic()
                    request_at = max(now, self._next_request_at)
                    self._next_request_at = request_at + self._min_request_interval
                    wait_seconds = max(0.0, request_at - now)
                    break
                wait_seconds = max(0.0, (1.0 - bucket.tokens) / bucket.limit)
            if wait_seconds > 0.0:
                self._sleep(wait_seconds)
        if wait_seconds > 0.0:
            self._sleep(wait_seconds)

    def update_from_headers(self, group: str, headers: Mapping[str, object]) -> None:
        with self._lock:
            bucket = self._bucket_for(group)
            limit = _positive_float(headers.get("X-RateLimit-Limit"))
            remaining = _non_negative_float(headers.get("X-RateLimit-Remaining"))
            reset = _non_negative_float(headers.get("X-RateLimit-Reset"))

            if limit is not None:
                bucket.limit = limit
                bucket.tokens = min(bucket.tokens, limit)
            if remaining is not None:
                bucket.tokens = min(remaining, bucket.limit)
                bucket.updated_at = self._monotonic()
            if reset is not None and remaining == 0:
                bucket.updated_at = self._monotonic() + reset - (1.0 / bucket.limit)

    def retry_delay(self, headers: Mapping[str, object], attempt: int) -> float:
        retry_after = _non_negative_float(headers.get("Retry-After"))
        if retry_after is not None:
            return retry_after

        reset = _non_negative_float(headers.get("X-RateLimit-Reset"))
        if reset is not None:
            return reset

        backoff = min(2.0**attempt, 30.0)
        return backoff + self._jitter(0.0, min(0.25 * backoff, 1.0))

    def sleep(self, seconds: float) -> None:
        self._sleep(max(0.0, seconds))

    def _bucket_for(self, group: str) -> _Bucket:
        normalized = group.upper()
        bucket = self._buckets.get(normalized)
        if bucket is not None:
            return bucket

        limit = float(self._default_limits.get(normalized, 1))
        bucket = _Bucket(limit=limit, tokens=limit, updated_at=self._monotonic())
        self._buckets[normalized] = bucket
        return bucket

    def _refill(self, bucket: _Bucket) -> None:
        now = self._monotonic()
        elapsed = max(0.0, now - bucket.updated_at)
        bucket.tokens = min(bucket.limit, bucket.tokens + elapsed * bucket.limit)
        bucket.updated_at = now


def _positive_float(value: object) -> float | None:
    parsed = _non_negative_float(value)
    if parsed is None or parsed <= 0:
        return None
    return parsed


def _non_negative_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


DEFAULT_RATE_LIMIT_MANAGER = TossRateLimitManager()
