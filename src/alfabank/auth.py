"""Authorization providers for the Alfa API.

The bank accepts two schemes in the same ``Authorization`` header:
``Bearer <access_token>`` (OAuth2 / AlfaID) and ``ApiKey <key>`` (developer
portal). A provider is any zero-argument sync or async callable returning the
full header value; it is re-resolved before every request, which lets
callers rotate tokens without recreating the client.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable

from alfabank.exceptions import AlfaBankConfigurationError

TokenProvider = Callable[[], "str | Awaitable[str]"]


def _require_non_empty_str(value: str, name: str) -> str:
    if not value or not isinstance(value, str):
        raise AlfaBankConfigurationError(f"{name} must be a non-empty string")
    return value


class ApiKeyAuth:
    """Static ``Authorization: ApiKey <key>`` provider."""

    __slots__ = ("_api_key",)

    def __init__(self, api_key: str) -> None:
        self._api_key = _require_non_empty_str(api_key, "api_key")

    def __call__(self) -> str:
        return f"ApiKey {self._api_key}"


class BearerAuth:
    """Static ``Authorization: Bearer <token>`` provider."""

    __slots__ = ("_access_token",)

    def __init__(self, access_token: str) -> None:
        self._access_token = _require_non_empty_str(access_token, "access_token")

    def __call__(self) -> str:
        return f"Bearer {self._access_token}"


async def resolve_authorization(provider: TokenProvider) -> str:
    """Call the provider (awaiting if needed) and validate the header value."""
    value = provider()
    if inspect.isawaitable(value):
        value = await value
    if not isinstance(value, str) or not value:
        raise AlfaBankConfigurationError(
            "token_provider must return a non-empty Authorization header string"
        )
    return value
