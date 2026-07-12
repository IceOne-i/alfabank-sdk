"""CustomerResource tests over respx with the bank's own mock."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest
import respx

from alfabank._transport import RetryPolicy, Transport
from alfabank.auth import ApiKeyAuth
from alfabank.models.customer import CustomerInfo
from alfabank.resources.customer import CustomerResource
from tests.conftest import TEST_BASE_URL


@pytest.fixture
async def customer() -> AsyncIterator[CustomerResource]:
    transport = Transport(
        token_provider=ApiKeyAuth("test-key"),
        base_url=TEST_BASE_URL,
        retry_policy=RetryPolicy(max_retries=0, backoff_factor=0.0),
    )
    try:
        yield CustomerResource(transport)
    finally:
        await transport.aclose()


async def test_info_hits_versioned_path_and_parses(
    customer: CustomerResource,
    mock_api: respx.MockRouter,
    load_mock: Callable[[str], Any],
) -> None:
    route = mock_api.get("/api/jp/v2/customer-info").mock(
        return_value=httpx.Response(
            200, json=load_mock("customer-info/customer-info-v2.json")
        )
    )
    info = await customer.info()
    assert isinstance(info, CustomerInfo)
    assert info.inn == "0000000000"
    assert len(info.accounts) == 1
    assert route.call_count == 1
    assert route.calls.last.request.url.path == "/api/jp/v2/customer-info"
