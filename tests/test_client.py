"""AlfaBankClient facade tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest
import respx

from alfabank.client import (
    PRODUCTION_BASE_URL,
    SANDBOX_BASE_URL,
    AlfaBankClient,
)
from alfabank.exceptions import AlfaBankConfigurationError
from alfabank.models.customer import CustomerInfo


def test_url_constants() -> None:
    assert PRODUCTION_BASE_URL == "https://baas.alfabank.ru"
    assert SANDBOX_BASE_URL == "https://sandbox.alfabank.ru"


def test_requires_exactly_one_auth_method() -> None:
    with pytest.raises(AlfaBankConfigurationError):
        AlfaBankClient()
    with pytest.raises(AlfaBankConfigurationError):
        AlfaBankClient(api_key="k", access_token="t")
    with pytest.raises(AlfaBankConfigurationError):
        AlfaBankClient(api_key="k", token_provider=lambda: "Bearer x")


def test_rejects_empty_credentials() -> None:
    with pytest.raises(AlfaBankConfigurationError):
        AlfaBankClient(api_key="")
    with pytest.raises(AlfaBankConfigurationError):
        AlfaBankClient(access_token="")


async def test_api_key_auth_end_to_end(
    mock_api: respx.MockRouter, load_mock: Callable[[str], Any]
) -> None:
    route = mock_api.get("/api/jp/v2/customer-info").mock(
        return_value=httpx.Response(
            200, json=load_mock("customer-info/customer-info-v2.json")
        )
    )
    async with AlfaBankClient(api_key="sample-api-key", rate_limit=None, max_retries=0) as client:
        info = await client.customer.info()
    assert isinstance(info, CustomerInfo)
    assert route.calls.last.request.headers["Authorization"] == "ApiKey sample-api-key"


async def test_access_token_auth_end_to_end(mock_api: respx.MockRouter) -> None:
    route = mock_api.get("/api/jp/v2/customer-info").mock(
        return_value=httpx.Response(200, json={})
    )
    async with AlfaBankClient(access_token="eyJtoken", max_retries=0) as client:
        await client.customer.info()
    assert route.calls.last.request.headers["Authorization"] == "Bearer eyJtoken"


async def test_async_token_provider_used(mock_api: respx.MockRouter) -> None:
    route = mock_api.get("/api/jp/v2/customer-info").mock(
        return_value=httpx.Response(200, json={})
    )

    async def provider() -> str:
        return "Bearer from-provider"

    async with AlfaBankClient(token_provider=provider, max_retries=0) as client:
        await client.customer.info()
    assert route.calls.last.request.headers["Authorization"] == "Bearer from-provider"


async def test_api_prefix_override(mock_api: respx.MockRouter) -> None:
    route = mock_api.get("/api/jp/v1/statement/summary").mock(
        return_value=httpx.Response(200, json={})
    )
    async with AlfaBankClient(api_key="k", api_prefix="/api/jp/v1", max_retries=0) as client:
        await client.statements.summary("40702810102300000001", "2023-01-30")
    assert route.call_count == 1


async def test_raw_request_escape_hatch(mock_api: respx.MockRouter) -> None:
    mock_api.get("/api/some/unwrapped").mock(
        return_value=httpx.Response(200, json={"raw": True})
    )
    async with AlfaBankClient(api_key="k", max_retries=0) as client:
        body = await client.request("GET", "/some/unwrapped")
    assert body == {"raw": True}


async def test_aclose_is_idempotent() -> None:
    client = AlfaBankClient(api_key="k")
    await client.aclose()
    await client.aclose()  # second close must not raise


async def test_injected_http_client_not_closed(mock_api: respx.MockRouter) -> None:
    mock_api.get("/api/jp/v2/customer-info").mock(return_value=httpx.Response(200, json={}))
    external = httpx.AsyncClient(base_url=PRODUCTION_BASE_URL)
    async with AlfaBankClient(api_key="k", http_client=external, max_retries=0) as client:
        await client.customer.info()
    assert external.is_closed is False
    await external.aclose()
