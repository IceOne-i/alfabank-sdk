"""AlfaBankClient: the public facade of alfabank-sdk.

Example:
    async with AlfaBankClient(api_key="...") as client:
        async for tx in client.statements.iter_transactions(
            "40702810102300000001", date(2026, 7, 1)
        ):
            print(tx.payment_purpose, tx.amount)
"""

from __future__ import annotations

from types import TracebackType
from typing import Any

import httpx

from alfabank._transport import RetryPolicy, Transport
from alfabank._utils import AsyncRateLimiter
from alfabank.auth import ApiKeyAuth, BearerAuth, TokenProvider
from alfabank.exceptions import AlfaBankConfigurationError
from alfabank.resources.customer import CustomerResource
from alfabank.resources.statements import StatementsResource

try:
    from alfabank._version import __version__ as _sdk_version
except ImportError:  # pragma: no cover - version file is generated at build time
    _sdk_version = "0.0.0+unknown"

PRODUCTION_BASE_URL = "https://baas.alfabank.ru"
SANDBOX_BASE_URL = "https://sandbox.alfabank.ru"
DEFAULT_TIMEOUT = 30.0
DEFAULT_USER_AGENT = f"alfabank-sdk/{_sdk_version}"


class AlfaBankClient:
    """Async client for the Alfa-Bank Alfa API (h2h).

    Exactly one of ``api_key``, ``access_token`` or ``token_provider`` is
    required. ``base_url``/``api_prefix`` default to production values that
    are configurable because the bank's gateway paths differ per contract
    (see the design spec's assumptions section).
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        access_token: str | None = None,
        token_provider: TokenProvider | None = None,
        base_url: str = PRODUCTION_BASE_URL,
        api_prefix: str = "/api",
        timeout: float | httpx.Timeout = DEFAULT_TIMEOUT,
        max_retries: int = 3,
        retry_non_idempotent: bool = False,
        rate_limit: int | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
        cert: Any = None,
        verify: Any = True,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        provided = [v for v in (api_key, access_token, token_provider) if v is not None]
        if len(provided) != 1:
            raise AlfaBankConfigurationError(
                "Provide exactly one of api_key, access_token or token_provider"
            )
        if not base_url or not isinstance(base_url, str):
            raise AlfaBankConfigurationError("base_url must be a non-empty string")

        provider: TokenProvider
        if api_key is not None:
            provider = ApiKeyAuth(api_key)
        elif access_token is not None:
            provider = BearerAuth(access_token)
        else:
            assert token_provider is not None
            provider = token_provider

        self._closed = False
        self._transport = Transport(
            token_provider=provider,
            base_url=base_url,
            api_prefix=api_prefix,
            timeout=timeout,
            retry_policy=RetryPolicy(
                max_retries=max_retries, retry_non_idempotent=retry_non_idempotent
            ),
            rate_limiter=AsyncRateLimiter(rate_limit) if rate_limit else None,
            user_agent=user_agent,
            cert=cert,
            verify=verify,
            client=http_client,
        )
        self.statements = StatementsResource(self._transport)
        self.customer = CustomerResource(self._transport)

    async def request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Escape hatch: raw request to any endpoint, returns decoded JSON."""
        response = await self._transport.request(method, path, **kwargs)
        return response.json_body

    async def aclose(self) -> None:
        if not self._closed:
            self._closed = True
            await self._transport.aclose()

    async def __aenter__(self) -> AlfaBankClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()
