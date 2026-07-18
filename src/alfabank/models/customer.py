# ruff: noqa: RUF002
"""Models for GET /jp/v2/customer-info."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import Field

from alfabank.enums import BlockType, CustomerCategory, CustomerStatus, SpecConditionCode
from alfabank.models.common import _AlfaBase, coerce_to_enum


class OrganizationForm(_AlfaBase):
    """Организационно-правовая форма."""

    full_name: str | None = None
    short_name: str | None = None
    type: str | None = None
    code: str | None = None


class Address(_AlfaBase):
    """Адрес организации."""

    type: str | None = None
    area: str | None = None
    building: str | None = None
    city: str | None = None
    country: str | None = None
    flat: str | None = None
    full_address: str | None = None
    house: str | None = None
    region: str | None = None
    settlement: str | None = None
    settlement_type: str | None = None
    street: str | None = None
    zip: str | None = None
    fias_code: str | None = None


class SpecCondition(_AlfaBase):
    """Специальное условие (ограничение) по счёту."""

    code: Annotated[SpecConditionCode | str, coerce_to_enum(SpecConditionCode)] | None = None
    description: str | None = None
    value: bool | None = None


class AccountBlockInfo(_AlfaBase):
    """Блокировка суммы на счёте."""

    num: str | None = None
    begin_date: date | None = None
    cause: str | None = None
    initiator: str | None = None
    sum: Decimal | None = None
    block_type: Annotated[BlockType | str, coerce_to_enum(BlockType)] | None = None


class BankRef(_AlfaBase):
    """Реквизиты банка, в котором открыт счёт."""

    bic: str | None = None
    correspondent_account_number: str | None = None


class Account(_AlfaBase):
    """Счёт организации с балансами и ограничениями."""

    number: str | None = None
    type: str | None = None
    type_name: str | None = None
    open_date: date | None = None
    currency_code: str | None = None
    transit_account_number: str | None = None
    client_name: str | None = None
    amount_balance: Decimal | None = None
    amount_total: Decimal | None = None
    amount_holds: Decimal | None = None
    amount_overdraft_own_funds: Decimal | None = None
    amount_overdraft_limit: Decimal | None = None
    spec_conditions: list[SpecCondition] = Field(default_factory=list)
    blocked_sums: list[AccountBlockInfo] = Field(default_factory=list)
    bank: BankRef | None = None


class CustomerInfo(_AlfaBase):
    """Профиль организации (GET /jp/v2/customer-info)."""

    organization_id: str | None = None
    full_name: str | None = None
    short_name: str | None = None
    inn: str | None = None
    ogrn: str | None = None
    okpo: str | None = None
    okved: str | None = None
    type: str | None = None
    phone: str | None = None
    email: str | None = None
    kpps: list[str] = Field(default_factory=list)
    organization_form: OrganizationForm | None = None
    category: Annotated[CustomerCategory | str, coerce_to_enum(CustomerCategory)] | None = None
    status: Annotated[CustomerStatus | str, coerce_to_enum(CustomerStatus)] | None = None
    registration_date: datetime | None = None
    addresses: list[Address] = Field(default_factory=list)
    accounts: list[Account] = Field(default_factory=list)
