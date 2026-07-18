"""Tests for the experimental OAuth helper (respx-mocked /oidc/token)."""

from __future__ import annotations

from urllib.parse import parse_qs

import httpx
import pytest
import respx

from alfabank.client import AlfaBankClient
from alfabank.exceptions import AlfaBankAPIError
from alfabank.oauth import (
    PRODUCTION_TOKEN_URL,
    SANDBOX_TOKEN_URL,
    OAuthTokenProvider,
    TokenPair,
    exchange_authorization_code,
    refresh_access_token,
)

TOKEN_RESPONSE = {
    "access_token": "t1",
    "token_type": "Bearer",
    "expires_in": 3600,
    "refresh_token": "rt2",
    "scope": "statements",
}


def test_token_url_constants() -> None:
    assert PRODUCTION_TOKEN_URL == "https://baas.alfabank.ru/oidc/token"
    assert SANDBOX_TOKEN_URL == "https://sandbox.alfabank.ru/oidc/token"


@respx.mock
async def test_exchange_authorization_code_posts_form() -> None:
    route = respx.post(PRODUCTION_TOKEN_URL).mock(
        return_value=httpx.Response(200, json=TOKEN_RESPONSE)
    )
    pair = await exchange_authorization_code(
        client_id="cid",
        client_secret="secret",
        code="auth-code",
        redirect_uri="https://example.com/cb",
    )
    assert isinstance(pair, TokenPair)
    assert pair.access_token == "t1"
    assert pair.refresh_token == "rt2"
    form = parse_qs(route.calls.last.request.content.decode())
    assert form["grant_type"] == ["authorization_code"]
    assert form["code"] == ["auth-code"]
    assert form["redirect_uri"] == ["https://example.com/cb"]
    assert form["client_id"] == ["cid"]
    assert form["client_secret"] == ["secret"]


@respx.mock
async def test_refresh_access_token_posts_form() -> None:
    route = respx.post(SANDBOX_TOKEN_URL).mock(
        return_value=httpx.Response(200, json=TOKEN_RESPONSE)
    )
    pair = await refresh_access_token(
        client_id="cid",
        client_secret="secret",
        refresh_token="rt1",
        token_url=SANDBOX_TOKEN_URL,
    )
    assert pair.access_token == "t1"
    form = parse_qs(route.calls.last.request.content.decode())
    assert form["grant_type"] == ["refresh_token"]
    assert form["refresh_token"] == ["rt1"]


@respx.mock
async def test_token_endpoint_error_is_mapped() -> None:
    respx.post(PRODUCTION_TOKEN_URL).mock(
        return_value=httpx.Response(
            400, json={"error": "invalid_grant", "error_description": "code expired"}
        )
    )
    with pytest.raises(AlfaBankAPIError) as exc_info:
        await refresh_access_token(client_id="c", client_secret="s", refresh_token="rt")
    assert exc_info.value.error_code == "invalid_grant"


@respx.mock
async def test_provider_caches_until_expiry() -> None:
    route = respx.post(PRODUCTION_TOKEN_URL).mock(
        return_value=httpx.Response(200, json=TOKEN_RESPONSE)
    )
    provider = OAuthTokenProvider(
        client_id="cid", client_secret="secret", refresh_token="rt1"
    )
    assert await provider() == "Bearer t1"
    assert await provider() == "Bearer t1"
    assert route.call_count == 1  # second call served from cache


@respx.mock
async def test_provider_refreshes_expired_token_and_rotates_refresh_token() -> None:
    route = respx.post(PRODUCTION_TOKEN_URL).mock(
        side_effect=[
            httpx.Response(
                200,
                json={"access_token": "t1", "expires_in": 1, "refresh_token": "rt2"},
            ),
            httpx.Response(
                200,
                json={"access_token": "t2", "expires_in": 3600, "refresh_token": "rt3"},
            ),
        ]
    )
    # leeway larger than expires_in -> token is treated as expired immediately
    provider = OAuthTokenProvider(
        client_id="cid", client_secret="secret", refresh_token="rt1", leeway=10.0
    )
    assert await provider() == "Bearer t1"
    assert await provider() == "Bearer t2"
    assert route.call_count == 2
    # the second request must use the rotated refresh token from the first response
    second_form = parse_qs(route.calls[1].request.content.decode())
    assert second_form["refresh_token"] == ["rt2"]


async def test_provider_plugs_into_client(mock_api: respx.MockRouter) -> None:
    mock_api.post("/oidc/token").mock(return_value=httpx.Response(200, json=TOKEN_RESPONSE))
    api_route = mock_api.get("/api/jp/v2/customer-info").mock(
        return_value=httpx.Response(200, json={})
    )
    provider = OAuthTokenProvider(
        client_id="cid", client_secret="secret", refresh_token="rt1"
    )
    async with AlfaBankClient(token_provider=provider, max_retries=0) as client:
        await client.customer.info()
    assert api_route.calls.last.request.headers["Authorization"] == "Bearer t1"
