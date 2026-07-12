"""Private transport layer: retry policy, response wrapper, httpx plumbing.

Retries are idempotency-aware: GET/HEAD/OPTIONS/PUT/DELETE retry on any
transient failure, while POST/PATCH retry only when the server provably never
processed the request (connect-phase network errors or pre-handler statuses
408/425/429). This prevents duplicate side effects for future payment
endpoints while keeping v1's GET-only surface fully retried.
"""

from __future__ import annotations

import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

_IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "PUT", "DELETE"})
_PRE_HANDLER_STATUSES = frozenset({408, 425, 429})


@dataclass(frozen=True)
class RetryPolicy:
    """Decides whether a failed request may be retried and with what delay."""

    max_retries: int = 3
    retry_non_idempotent: bool = False
    backoff_factor: float = 0.5
    max_backoff: float = 30.0

    def _effective_idempotent(self, method: str, idempotent: bool | None) -> bool:
        if idempotent is not None:
            return idempotent
        return method.upper() in _IDEMPOTENT_METHODS

    def should_retry_status(
        self, *, method: str, status_code: int, idempotent: bool | None = None
    ) -> bool:
        if status_code in _PRE_HANDLER_STATUSES:
            return True
        if status_code < 500:
            return False
        return self._effective_idempotent(method, idempotent) or self.retry_non_idempotent

    def should_retry_exception(
        self, *, method: str, exc: Exception, idempotent: bool | None = None
    ) -> bool:
        if isinstance(exc, httpx.ConnectError | httpx.ConnectTimeout):
            return True  # connect never happened -> safe for any method
        if isinstance(exc, httpx.TimeoutException | httpx.TransportError):
            return self._effective_idempotent(method, idempotent) or self.retry_non_idempotent
        return False

    def backoff_delay(self, attempt: int, *, retry_after: float | None = None) -> float:
        base = min(self.backoff_factor * (2**attempt), self.max_backoff)
        delay = base + base * random.uniform(-0.25, 0.25)  # jitter; not cryptographic
        if retry_after is not None:
            delay = max(delay, retry_after)
        return float(max(delay, 0.0))


class Response:
    """Minimal response wrapper so httpx types never leak past the transport."""

    __slots__ = ("_content", "headers", "status_code")

    def __init__(self, status_code: int, headers: Mapping[str, str], content: bytes) -> None:
        self.status_code = status_code
        self.headers: dict[str, str] = {k.lower(): v for k, v in headers.items()}
        self._content = content

    @property
    def text(self) -> str:
        return self._content.decode("utf-8", errors="replace")

    @property
    def is_json(self) -> bool:
        return "json" in self.headers.get("content-type", "")

    @property
    def json_body(self) -> Any:
        if not self._content:
            return None
        try:
            return json.loads(self._content)
        except ValueError:
            return None

    @property
    def request_id(self) -> str | None:
        return self.headers.get("x-traceid")
