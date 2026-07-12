"""Transport tests over respx-mocked httpx."""

from __future__ import annotations

import httpx
import pytest
import respx

from alfabank._transport import Response, RetryPolicy, Transport
from alfabank.auth import ApiKeyAuth
from alfabank.exceptions import (
    AlfaBankNotFoundError,
    AlfaBankServerError,
    AlfaBankTransportError,
)
from tests.conftest import TEST_BASE_URL


def make_transport(**overrides: object) -> Transport:
    kwargs: dict[str, object] = {
        "token_provider": ApiKeyAuth("test-key"),
        "base_url": TEST_BASE_URL,
        "api_prefix": "/api",
        "timeout": 5.0,
        "retry_policy": RetryPolicy(max_retries=0, backoff_factor=0.0),
        "rate_limiter": None,
        "user_agent": "test-agent",
    }
    kwargs.update(overrides)
    return Transport(**kwargs)  # type: ignore[arg-type]


async def test_request_sends_default_headers_and_prefix(mock_api: respx.MockRouter) -> None:
    route = mock_api.get("/api/statement/summary").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    transport = make_transport()
    try:
        resp = await transport.request(
            "GET",
            "/statement/summary",
            params={"accountNumber": "40702810000000000001", "page": None, "curFormat": ""},
        )
    finally:
        await transport.aclose()

    assert isinstance(resp, Response)
    assert resp.json_body == {"ok": True}
    request = route.calls.last.request
    assert request.headers["Authorization"] == "ApiKey test-key"
    assert request.headers["Accept"] == "application/json"
    assert request.headers["User-Agent"] == "test-agent"
    # None/empty params are dropped
    assert "page" not in str(request.url)
    assert "curFormat" not in str(request.url)
    assert request.url.params["accountNumber"] == "40702810000000000001"


async def test_error_maps_and_carries_traceid(mock_api: respx.MockRouter) -> None:
    mock_api.get("/api/missing").mock(
        return_value=httpx.Response(
            404,
            json={"error": "unknown_endpoint", "error_description": "Endpoint is not found"},
            headers={"x-traceid": "trace-42"},
        )
    )
    transport = make_transport()
    try:
        with pytest.raises(AlfaBankNotFoundError) as exc_info:
            await transport.request("GET", "/missing")
    finally:
        await transport.aclose()
    assert exc_info.value.request_id == "trace-42"
    assert exc_info.value.error_code == "unknown_endpoint"


async def test_get_retries_5xx_then_succeeds(mock_api: respx.MockRouter) -> None:
    route = mock_api.get("/api/flaky").mock(
        side_effect=[
            httpx.Response(500, json={"error": "internal_error"}),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    transport = make_transport(retry_policy=RetryPolicy(max_retries=2, backoff_factor=0.0))
    try:
        resp = await transport.request("GET", "/flaky")
    finally:
        await transport.aclose()
    assert resp.json_body == {"ok": True}
    assert route.call_count == 2


async def test_get_raises_after_retries_exhausted(mock_api: respx.MockRouter) -> None:
    route = mock_api.get("/api/broken").mock(return_value=httpx.Response(500))
    transport = make_transport(retry_policy=RetryPolicy(max_retries=1, backoff_factor=0.0))
    try:
        with pytest.raises(AlfaBankServerError):
            await transport.request("GET", "/broken")
    finally:
        await transport.aclose()
    assert route.call_count == 2  # initial + 1 retry


async def test_post_5xx_not_retried(mock_api: respx.MockRouter) -> None:
    route = mock_api.post("/api/pay").mock(return_value=httpx.Response(500))
    transport = make_transport(retry_policy=RetryPolicy(max_retries=3, backoff_factor=0.0))
    try:
        with pytest.raises(AlfaBankServerError):
            await transport.request("POST", "/pay", json_body={"x": 1})
    finally:
        await transport.aclose()
    assert route.call_count == 1


async def test_post_connect_error_is_retried(mock_api: respx.MockRouter) -> None:
    route = mock_api.post("/api/pay").mock(
        side_effect=[httpx.ConnectError("refused"), httpx.Response(200, json={"ok": True})]
    )
    transport = make_transport(retry_policy=RetryPolicy(max_retries=1, backoff_factor=0.0))
    try:
        resp = await transport.request("POST", "/pay", json_body={"x": 1})
    finally:
        await transport.aclose()
    assert resp.json_body == {"ok": True}
    assert route.call_count == 2


async def test_timeout_wrapped_in_transport_error(mock_api: respx.MockRouter) -> None:
    mock_api.get("/api/slow").mock(side_effect=httpx.ReadTimeout("timeout"))
    transport = make_transport()
    try:
        with pytest.raises(AlfaBankTransportError):
            await transport.request("GET", "/slow")
    finally:
        await transport.aclose()


async def test_injected_client_is_not_closed(mock_api: respx.MockRouter) -> None:
    mock_api.get("/api/ping").mock(return_value=httpx.Response(200, json={}))
    external = httpx.AsyncClient(base_url=TEST_BASE_URL)
    transport = make_transport(client=external)
    await transport.request("GET", "/ping")
    await transport.aclose()
    assert external.is_closed is False
    await external.aclose()
