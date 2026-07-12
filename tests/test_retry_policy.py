"""Unit tests for RetryPolicy decisions and the Response wrapper."""

from __future__ import annotations

import httpx
import pytest

from alfabank._transport import Response, RetryPolicy


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS", "PUT", "DELETE"])
def test_idempotent_methods_retry_5xx(method: str) -> None:
    policy = RetryPolicy()
    assert policy.should_retry_status(method=method, status_code=500) is True
    assert policy.should_retry_status(method=method, status_code=503) is True


def test_post_does_not_retry_5xx_by_default() -> None:
    policy = RetryPolicy()
    assert policy.should_retry_status(method="POST", status_code=500) is False


@pytest.mark.parametrize("status", [408, 425, 429])
def test_pre_handler_statuses_retry_even_for_post(status: int) -> None:
    # These statuses mean the server never processed the request body.
    assert RetryPolicy().should_retry_status(method="POST", status_code=status) is True


def test_retry_non_idempotent_opts_into_5xx_retry_for_post() -> None:
    policy = RetryPolicy(retry_non_idempotent=True)
    assert policy.should_retry_status(method="POST", status_code=500) is True


def test_per_call_idempotent_override() -> None:
    policy = RetryPolicy()
    assert policy.should_retry_status(method="GET", status_code=500, idempotent=False) is False
    assert policy.should_retry_status(method="POST", status_code=500, idempotent=True) is True


def test_success_and_client_errors_never_retry() -> None:
    policy = RetryPolicy()
    assert policy.should_retry_status(method="GET", status_code=200) is False
    assert policy.should_retry_status(method="GET", status_code=404) is False


def test_connect_errors_retry_for_any_method() -> None:
    policy = RetryPolicy()
    exc = httpx.ConnectError("boom")
    assert policy.should_retry_exception(method="POST", exc=exc) is True
    assert policy.should_retry_exception(method="GET", exc=exc) is True


def test_read_errors_retry_only_for_idempotent() -> None:
    policy = RetryPolicy()
    exc = httpx.ReadTimeout("slow")
    assert policy.should_retry_exception(method="GET", exc=exc) is True
    assert policy.should_retry_exception(method="POST", exc=exc) is False


def test_backoff_delay_grows_and_caps() -> None:
    policy = RetryPolicy(backoff_factor=0.5, max_backoff=30.0)
    d0 = policy.backoff_delay(0)
    assert 0.375 <= d0 <= 0.625  # 0.5 * 2**0, jitter +-25%
    d_big = policy.backoff_delay(20)
    assert d_big <= 30.0 * 1.25


def test_backoff_delay_honors_retry_after() -> None:
    policy = RetryPolicy(backoff_factor=0.0)
    assert policy.backoff_delay(0, retry_after=10.0) >= 10.0


def test_zero_backoff_factor_gives_zero_delay() -> None:
    assert RetryPolicy(backoff_factor=0.0).backoff_delay(0) == 0.0


def test_response_wrapper() -> None:
    resp = Response(
        status_code=200,
        headers={"Content-Type": "application/json", "X-TraceId": "a57610880b621435"},
        content=b'{"a": 1}',
    )
    assert resp.status_code == 200
    assert resp.is_json is True
    assert resp.json_body == {"a": 1}
    assert resp.request_id == "a57610880b621435"
    assert resp.text == '{"a": 1}'


def test_response_non_json_body() -> None:
    resp = Response(status_code=503, headers={}, content=b"")
    assert resp.is_json is False
    assert resp.json_body is None
    assert resp.request_id is None
