from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock
from time import monotonic

from fastapi import Request


@dataclass(frozen=True)
class RateLimitRule:
    requests: int
    window_seconds: int


class InMemoryRateLimiter:
    """Best-effort per-instance limiter for public serverless endpoints.

    Vercel can run multiple instances, so this is a local safety net rather than
    a billing-grade global quota. The deliberately low upstream tool-call caps
    provide a second bound inside each accepted request.
    """

    def __init__(self) -> None:
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = Lock()

    @staticmethod
    def client_key(request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        return forwarded or (request.client.host if request.client else "unknown")

    def check(self, bucket: str, client: str, rule: RateLimitRule) -> int | None:
        now = monotonic()
        cutoff = now - rule.window_seconds
        key = (bucket, client)
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= rule.requests:
                return max(1, int(rule.window_seconds - (now - events[0])))
            events.append(now)
        return None

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


RATE_LIMITER = InMemoryRateLimiter()

PUBLIC_API_RULES = {
    "/api/chat": RateLimitRule(requests=12, window_seconds=3_600),
    "/api/portfolio/generate": RateLimitRule(requests=20, window_seconds=3_600),
    "/api/portfolio/analyze": RateLimitRule(requests=30, window_seconds=3_600),
    "/api/company/analyze": RateLimitRule(requests=40, window_seconds=3_600),
    "/api/portfolio/quotes": RateLimitRule(requests=60, window_seconds=3_600),
}


def rule_for_path(path: str) -> tuple[str, RateLimitRule] | None:
    exact = PUBLIC_API_RULES.get(path)
    if exact:
        return path, exact
    if path.startswith("/api/company/"):
        return "/api/company/*", RateLimitRule(requests=80, window_seconds=3_600)
    if path.startswith("/api/market/"):
        return "/api/market/*", RateLimitRule(requests=120, window_seconds=3_600)
    return None
