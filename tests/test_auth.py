"""Tests for authorization providers."""

from __future__ import annotations

import pytest

from alfabank.auth import ApiKeyAuth, BearerAuth, resolve_authorization
from alfabank.exceptions import AlfaBankConfigurationError


def test_api_key_auth_header_value() -> None:
    assert ApiKeyAuth("sample-api-key")() == "ApiKey sample-api-key"


def test_bearer_auth_header_value() -> None:
    assert BearerAuth("eyJtoken")() == "Bearer eyJtoken"


@pytest.mark.parametrize("bad", ["", None, 123])
def test_api_key_auth_rejects_bad_values(bad: object) -> None:
    with pytest.raises(AlfaBankConfigurationError):
        ApiKeyAuth(bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", ["", None, 123])
def test_bearer_auth_rejects_bad_values(bad: object) -> None:
    with pytest.raises(AlfaBankConfigurationError):
        BearerAuth(bad)  # type: ignore[arg-type]


async def test_resolve_sync_provider() -> None:
    assert await resolve_authorization(lambda: "ApiKey k") == "ApiKey k"
    assert await resolve_authorization(ApiKeyAuth("k")) == "ApiKey k"


async def test_resolve_async_provider() -> None:
    async def provider() -> str:
        return "Bearer t"

    assert await resolve_authorization(provider) == "Bearer t"


async def test_resolve_rejects_empty_or_non_string() -> None:
    with pytest.raises(AlfaBankConfigurationError):
        await resolve_authorization(lambda: "")
    with pytest.raises(AlfaBankConfigurationError):
        await resolve_authorization(lambda: 42)  # type: ignore[arg-type,return-value]
