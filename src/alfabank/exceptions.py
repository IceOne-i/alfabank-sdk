"""Exception hierarchy for alfabank-sdk and HTTP status -> exception mapping.

The Alfa API reports errors via HTTP status codes with a JSON body of the
shape ``{"error": "<code>", "error_description": "<text>"}``. 429 and 503
responses arrive without a body.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_MAX_BODY_CHARS = 250


def _short_repr(value: Any) -> str:
    text = repr(value)
    if len(text) > _MAX_BODY_CHARS:
        return text[:_MAX_BODY_CHARS] + "..."
    return text


class AlfaBankError(Exception):
    """Base class for all alfabank-sdk errors."""


class AlfaBankConfigurationError(AlfaBankError):
    """Invalid client configuration (bad constructor arguments, credentials)."""


class AlfaBankValidationError(AlfaBankError):
    """Client-side validation failed before any network I/O."""


class AlfaBankTransportError(AlfaBankError):
    """Network-level failure: timeout, DNS, connection problems."""


class AlfaBankAPIError(AlfaBankError):
    """Non-success HTTP response from the Alfa API."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
        response_body: Any = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.response_body = response_body
        self.request_id = request_id

    def __str__(self) -> str:
        parts = []
        if self.status_code is not None:
            parts.append(f"[HTTP {self.status_code}]")
        if self.error_code:
            parts.append(f"[{self.error_code}]")
        parts.append(self.message)
        return " ".join(parts)


class AlfaBankAuthenticationError(AlfaBankAPIError):
    """401: the access token / API key is missing, expired or invalid."""


class AlfaBankPermissionError(AlfaBankAPIError):
    """403: insufficient scope or no access to the requested account."""


class AlfaBankNotFoundError(AlfaBankAPIError):
    """404: endpoint or entity not found / not active."""


class AlfaBankConflictError(AlfaBankAPIError):
    """409: conflicting state (e.g. duplicate externalId on payments)."""


class AlfaBankRateLimitError(AlfaBankAPIError):
    """429: rate limit exceeded. ``retry_after`` holds the server hint, if any."""

    def __init__(
        self,
        message: str,
        *,
        retry_after: float | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class AlfaBankServerError(AlfaBankAPIError):
    """5xx: internal error on the bank side."""


_DEFAULT_MESSAGES: dict[int, str] = {
    401: "Authentication failed",
    403: "Insufficient privileges",
    404: "Not found",
    409: "Conflict",
    429: "Rate limit exceeded",
}


def _parse_retry_after(headers: Mapping[str, str] | None) -> float | None:
    if not headers:
        return None
    raw = None
    for key, value in headers.items():
        if key.lower() == "retry-after":
            raw = value
            break
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def raise_for_status(
    *,
    status_code: int,
    response_body: Any,
    request_id: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> None:
    """Raise the mapped :class:`AlfaBankAPIError` subclass for non-2xx/3xx statuses.

    Statuses in the 200-399 range are treated as success (mirrors the bank's
    own reference client).
    """
    if 200 <= status_code < 400:
        return

    error_code: str | None = None
    description: str | None = None
    if isinstance(response_body, Mapping):
        raw_code = response_body.get("error")
        raw_description = response_body.get("error_description")
        error_code = str(raw_code) if raw_code is not None else None
        description = str(raw_description) if raw_description is not None else None

    message = description or _DEFAULT_MESSAGES.get(
        status_code, f"Alfa API request failed with HTTP {status_code}"
    )
    if response_body is not None and description is None:
        message = f"{message}: {_short_repr(response_body)}"
    if len(message) > _MAX_BODY_CHARS:
        message = message[:_MAX_BODY_CHARS] + "..."

    kwargs: dict[str, Any] = {
        "status_code": status_code,
        "error_code": error_code,
        "response_body": response_body,
        "request_id": request_id,
    }
    if status_code == 401:
        raise AlfaBankAuthenticationError(message, **kwargs)
    if status_code == 403:
        raise AlfaBankPermissionError(message, **kwargs)
    if status_code == 404:
        raise AlfaBankNotFoundError(message, **kwargs)
    if status_code == 409:
        raise AlfaBankConflictError(message, **kwargs)
    if status_code == 429:
        raise AlfaBankRateLimitError(
            message, retry_after=_parse_retry_after(headers), **kwargs
        )
    if status_code >= 500:
        raise AlfaBankServerError(message, **kwargs)
    raise AlfaBankAPIError(message, **kwargs)
