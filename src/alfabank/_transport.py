"""Private transport layer: retry policy, response wrapper, httpx plumbing.

Retries are idempotency-aware: GET/HEAD/OPTIONS/PUT/DELETE retry on any
transient failure, while POST/PATCH retry only when the server provably never
processed the request (connect-phase network errors or pre-handler statuses
408/425/429). This prevents duplicate side effects for future payment
endpoints while keeping v1's GET-only surface fully retried.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from alfabank._utils import AsyncRateLimiter
from alfabank.auth import TokenProvider, resolve_authorization
from alfabank.exceptions import AlfaBankTransportError, raise_for_status

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


_LOGGER = logging.getLogger("alfabank")


def _clean_params(params: Mapping[str, Any] | None) -> dict[str, str] | None:
    """Drop None/empty values (mirrors the bank's reference client) and stringify."""
    if not params:
        return None
    cleaned = {k: str(v) for k, v in params.items() if v is not None and v != ""}
    return cleaned or None


class Transport:
    """Owns the httpx client and all cross-cutting request concerns."""

    def __init__(
        self,
        *,
        token_provider: TokenProvider,
        base_url: str,
        api_prefix: str = "/api",
        timeout: float | httpx.Timeout = 30.0,
        retry_policy: RetryPolicy | None = None,
        rate_limiter: AsyncRateLimiter | None = None,
        user_agent: str = "alfabank-sdk",
        cert: Any = None,
        verify: Any = True,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._token_provider = token_provider
        self._api_prefix = "/" + api_prefix.strip("/") if api_prefix.strip("/") else ""
        self._retry_policy = retry_policy or RetryPolicy()
        self._rate_limiter = rate_limiter
        self._user_agent = user_agent
        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            self._client = httpx.AsyncClient(
                base_url=base_url.rstrip("/"), timeout=timeout, cert=cert, verify=verify
            )
            self._owns_client = True

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any = None,
        headers: Mapping[str, str] | None = None,
        idempotent: bool | None = None,
    ) -> Response:
        """Perform a request, retrying transient failures per the retry policy.

        Raises the mapped :class:`AlfaBankAPIError` subclass on HTTP errors and
        :class:`AlfaBankTransportError` on network failures.
        """
        url = self._api_prefix + (path if path.startswith("/") else "/" + path)
        clean = _clean_params(params)
        policy = self._retry_policy
        attempt = 0
        while True:
            if self._rate_limiter is not None:
                await self._rate_limiter.acquire()
            request_headers = {
                "Authorization": await resolve_authorization(self._token_provider),
                "Accept": "application/json",
                "User-Agent": self._user_agent,
            }
            if headers:
                request_headers.update(headers)
            try:
                raw = await self._client.request(
                    method, url, params=clean, json=json_body, headers=request_headers
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt < policy.max_retries and policy.should_retry_exception(
                    method=method, exc=exc, idempotent=idempotent
                ):
                    delay = policy.backoff_delay(attempt)
                    _LOGGER.debug(
                        "Retrying %s %s after %s (attempt %d, sleep %.2fs)",
                        method, url, type(exc).__name__, attempt + 1, delay,
                    )
                    await asyncio.sleep(delay)
                    attempt += 1
                    continue
                raise AlfaBankTransportError(f"{method} {url} failed: {exc}") from exc

            response = Response(
                status_code=raw.status_code, headers=raw.headers, content=raw.content
            )
            if 200 <= response.status_code < 400:
                return response

            if attempt < policy.max_retries and policy.should_retry_status(
                method=method, status_code=response.status_code, idempotent=idempotent
            ):
                retry_after_raw = response.headers.get("retry-after")
                try:
                    retry_after = float(retry_after_raw) if retry_after_raw else None
                except ValueError:
                    retry_after = None
                delay = policy.backoff_delay(attempt, retry_after=retry_after)
                _LOGGER.debug(
                    "Retrying %s %s after HTTP %d (attempt %d, sleep %.2fs)",
                    method, url, response.status_code, attempt + 1, delay,
                )
                await asyncio.sleep(delay)
                attempt += 1
                continue

            raise_for_status(
                status_code=response.status_code,
                response_body=response.json_body if response.is_json else (response.text or None),
                request_id=response.request_id,
                headers=response.headers,
            )
            raise AssertionError("unreachable")  # raise_for_status always raises here

    async def aclose(self) -> None:
        if self._owns_client and not self._client.is_closed:
            await self._client.aclose()
