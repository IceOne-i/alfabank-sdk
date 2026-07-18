"""Internal helpers: async rate limiting and statement pagination parsing."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from urllib.parse import parse_qs


def page_from_href(href: str) -> int | None:
    """Extract the ``page`` number from a statement ``_links`` href.

    The OpenAPI spec shows hrefs like ``?accountNumber=...&page=3`` while the
    bank's real mock sends them without the leading ``?`` — accept both.
    """
    query = href[1:] if href.startswith("?") else href
    values = parse_qs(query).get("page")
    if not values:
        return None
    try:
        return int(values[0])
    except ValueError:
        return None


class AsyncRateLimiter:
    """Sliding-window rate limiter: at most ``rate`` acquisitions per ``per`` seconds."""

    def __init__(self, rate: int, per: float = 1.0) -> None:
        if rate <= 0:
            raise ValueError("rate must be a positive integer")
        self._rate = rate
        self._per = per
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                while self._timestamps and now - self._timestamps[0] >= self._per:
                    self._timestamps.popleft()
                if len(self._timestamps) < self._rate:
                    self._timestamps.append(now)
                    return
                delay = self._per - (now - self._timestamps[0])
            await asyncio.sleep(max(delay, 0.001))
