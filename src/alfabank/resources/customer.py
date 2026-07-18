# ruff: noqa: RUF002
"""Customer resource: organization profile with accounts and balances."""

from __future__ import annotations

from alfabank.models.customer import CustomerInfo
from alfabank.resources._base import Resource


class CustomerResource(Resource):
    """Информация об организации."""

    # ---- GET /jp/v2/customer-info ----
    async def info(self) -> CustomerInfo:
        """Профиль организации: реквизиты, адреса, счета с балансами."""
        response = await self._transport.request("GET", "/jp/v2/customer-info")
        return CustomerInfo.model_validate(response.json_body)
