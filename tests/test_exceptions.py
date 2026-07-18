"""Tests for the exception hierarchy and HTTP status mapping."""

from __future__ import annotations

import pytest

from alfabank.exceptions import (
    AlfaBankAPIError,
    AlfaBankAuthenticationError,
    AlfaBankConfigurationError,
    AlfaBankConflictError,
    AlfaBankError,
    AlfaBankNotFoundError,
    AlfaBankPermissionError,
    AlfaBankRateLimitError,
    AlfaBankServerError,
    AlfaBankTransportError,
    AlfaBankValidationError,
    raise_for_status,
)


def test_hierarchy() -> None:
    for exc_type in (
        AlfaBankConfigurationError,
        AlfaBankAPIError,
        AlfaBankValidationError,
        AlfaBankTransportError,
    ):
        assert issubclass(exc_type, AlfaBankError)
    for exc_type in (
        AlfaBankAuthenticationError,
        AlfaBankPermissionError,
        AlfaBankNotFoundError,
        AlfaBankConflictError,
        AlfaBankRateLimitError,
        AlfaBankServerError,
    ):
        assert issubclass(exc_type, AlfaBankAPIError)


def test_api_error_str_contains_status_and_code() -> None:
    exc = AlfaBankAPIError(
        "Something failed",
        status_code=400,
        error_code="invalid_request",
        response_body={"error": "invalid_request"},
        request_id="a57610880b621435",
    )
    text = str(exc)
    assert "[HTTP 400]" in text
    assert "invalid_request" in text
    assert exc.status_code == 400
    assert exc.error_code == "invalid_request"
    assert exc.request_id == "a57610880b621435"


@pytest.mark.parametrize("status", [200, 204, 302, 399])
def test_raise_for_status_success_is_noop(status: int) -> None:
    raise_for_status(status_code=status, response_body=None)


@pytest.mark.parametrize(
    ("status", "error_code", "expected_type"),
    [
        (401, "invalid_token", AlfaBankAuthenticationError),
        (403, "insufficient_scope", AlfaBankPermissionError),
        (404, "unknown_endpoint", AlfaBankNotFoundError),
        (409, "conflict", AlfaBankConflictError),
        (500, "internal_error", AlfaBankServerError),
        (503, None, AlfaBankServerError),
    ],
)
def test_raise_for_status_maps_statuses(
    status: int, error_code: str | None, expected_type: type[AlfaBankAPIError]
) -> None:
    body = (
        {"error": error_code, "error_description": "details here"}
        if error_code is not None
        else None
    )
    with pytest.raises(expected_type) as exc_info:
        raise_for_status(status_code=status, response_body=body, request_id="trace-1")
    exc = exc_info.value
    assert exc.status_code == status
    assert exc.error_code == error_code
    assert exc.request_id == "trace-1"
    assert exc.response_body == body


def test_unmapped_4xx_is_plain_api_error() -> None:
    with pytest.raises(AlfaBankAPIError) as exc_info:
        raise_for_status(
            status_code=400,
            response_body={"error": "invalid_request", "error_description": "bad"},
        )
    assert type(exc_info.value) is AlfaBankAPIError
    assert exc_info.value.error_code == "invalid_request"


def test_rate_limit_extracts_retry_after_and_survives_empty_body() -> None:
    with pytest.raises(AlfaBankRateLimitError) as exc_info:
        raise_for_status(
            status_code=429,
            response_body=None,
            headers={"retry-after": "7"},
        )
    exc = exc_info.value
    assert exc.retry_after == 7.0
    assert exc.status_code == 429
    assert str(exc)  # message synthesized despite empty body


def test_rate_limit_invalid_retry_after_is_none() -> None:
    with pytest.raises(AlfaBankRateLimitError) as exc_info:
        raise_for_status(status_code=429, response_body=None, headers={"Retry-After": "nope"})
    assert exc_info.value.retry_after is None


def test_long_body_truncated_in_message() -> None:
    with pytest.raises(AlfaBankAPIError) as exc_info:
        raise_for_status(status_code=400, response_body={"error_description": "x" * 1000})
    assert len(str(exc_info.value)) < 500
