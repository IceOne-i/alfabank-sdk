"""EXPERIMENTAL: OAuth2 helpers for AlfaID token acquisition and refresh.

The ``/oidc/token`` contract is documented indirectly (the endpoint URLs come
from official FAQ snippets) and has NOT been verified against a live sandbox.
Known lifetimes: authorization code ~120s, refresh_token ~180 days.

The rest of the SDK does not depend on this module: ``OAuthTokenProvider`` is
just one possible ``token_provider`` for :class:`alfabank.AlfaBankClient`.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict

from alfabank.exceptions import AlfaBankTransportError, raise_for_status

PRODUCTION_TOKEN_URL = "https://baas.alfabank.ru/oidc/token"
SANDBOX_TOKEN_URL = "https://sandbox.alfabank.ru/oidc/token"


class TokenPair(BaseModel):
    """Response of the OAuth token endpoint (snake_case per RFC 6749)."""

    model_config = ConfigDict(extra="ignore")

    access_token: str
    token_type: str | None = None
    expires_in: int | None = None
    refresh_token: str | None = None
    scope: str | None = None


async def _request_token(
    data: dict[str, str], *, token_url: str, http_client: httpx.AsyncClient | None = None
) -> TokenPair:
    owns_client = http_client is None
    client = http_client or httpx.AsyncClient()
    try:
        try:
            response = await client.post(
                token_url, data=data, headers={"Accept": "application/json"}
            )
        except httpx.HTTPError as exc:
            raise AlfaBankTransportError(f"POST {token_url} failed: {exc}") from exc
        body: Any
        try:
            body = response.json()
        except ValueError:
            body = response.text or None
        raise_for_status(
            status_code=response.status_code,
            response_body=body,
            request_id=response.headers.get("x-traceid"),
            headers=response.headers,
        )
        return TokenPair.model_validate(body)
    finally:
        if owns_client:
            await client.aclose()


async def exchange_authorization_code(
    *,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    token_url: str = PRODUCTION_TOKEN_URL,
    http_client: httpx.AsyncClient | None = None,
) -> TokenPair:
    """Exchange an authorization code (TTL ~120s) for access+refresh tokens."""
    return await _request_token(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        token_url=token_url,
        http_client=http_client,
    )


async def refresh_access_token(
    *,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    token_url: str = PRODUCTION_TOKEN_URL,
    http_client: httpx.AsyncClient | None = None,
) -> TokenPair:
    """Obtain a fresh access token using a refresh token (TTL ~180 days)."""
    return await _request_token(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        token_url=token_url,
        http_client=http_client,
    )


class OAuthTokenProvider:
    """Caching token provider: refreshes the access token when it expires.

    Plug into ``AlfaBankClient(token_provider=...)``. Refresh-token rotation
    is handled: if the endpoint returns a new refresh_token, it replaces the
    stored one for subsequent refreshes.
    """

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        token_url: str = PRODUCTION_TOKEN_URL,
        leeway: float = 60.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._token_url = token_url
        self._leeway = leeway
        self._http_client = http_client
        self._access_token: str | None = None
        self._expires_at: float | None = None
        self._lock = asyncio.Lock()

    def _is_expired(self) -> bool:
        if self._access_token is None:
            return True
        if self._expires_at is None:
            return False  # no expires_in reported -> assume long-lived
        return time.monotonic() >= self._expires_at

    async def __call__(self) -> str:
        async with self._lock:
            if self._is_expired():
                pair = await refresh_access_token(
                    client_id=self._client_id,
                    client_secret=self._client_secret,
                    refresh_token=self._refresh_token,
                    token_url=self._token_url,
                    http_client=self._http_client,
                )
                self._access_token = pair.access_token
                if pair.refresh_token:
                    self._refresh_token = pair.refresh_token
                self._expires_at = (
                    time.monotonic() + pair.expires_in - self._leeway
                    if pair.expires_in is not None
                    else None
                )
            assert self._access_token is not None
            return f"Bearer {self._access_token}"
