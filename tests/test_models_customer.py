"""Customer-info models validated against the bank's own mock payload."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from alfabank.enums import CustomerCategory, CustomerStatus, SpecConditionCode
from alfabank.models.customer import BankRef, CustomerInfo


def test_customer_info_parses_bank_mock(load_mock: Callable[[str], Any]) -> None:
    info = CustomerInfo.model_validate(load_mock("customer-info/customer-info-v2.json"))

    assert info.organization_id == (
        "1ba92f29c6a39a60b5bf487a4c8c63631c10c6b3b98e0b7428668838c857b50b"
    )
    assert info.full_name == "Test Organization"
    assert info.inn == "0000000000"
    assert info.kpps == ["000000000"]
    assert info.status == CustomerStatus.ACTIVE
    assert info.category == CustomerCategory.OTHER
    assert info.registration_date == datetime(2020, 1, 1, tzinfo=timezone.utc)
    assert info.organization_form is not None
    assert info.organization_form.code == "00000"


def test_customer_addresses(load_mock: Callable[[str], Any]) -> None:
    info = CustomerInfo.model_validate(load_mock("customer-info/customer-info-v2.json"))
    address = info.addresses[0]
    assert address.type == "LEGAL_FULL"
    assert address.zip == "000000"
    assert address.country == "000"
    assert address.full_address == "Test Address"
    assert address.settlement_type == "city"


def test_customer_accounts(load_mock: Callable[[str], Any]) -> None:
    info = CustomerInfo.model_validate(load_mock("customer-info/customer-info-v2.json"))
    account = info.accounts[0]
    assert account.number == "00000000000000000000"
    assert account.type == "PAYMENT"
    assert account.open_date == date(2020, 1, 1)
    assert isinstance(account.amount_balance, Decimal)
    assert account.amount_balance == Decimal("1000.00")
    assert account.amount_holds == Decimal("0.00")
    assert account.amount_overdraft_limit is None  # absent in mock
    assert account.blocked_sums == []  # absent in mock -> default
    assert isinstance(account.bank, BankRef)  # empty {} object in mock
    assert account.bank.bic is None
    assert len(account.spec_conditions) == 10
    first = account.spec_conditions[0]
    assert first.code == SpecConditionCode.AI11
    assert first.value is False
    assert first.description == "Нельзя кредитовать"


def test_unknown_top_level_field_ignored(load_mock: Callable[[str], Any]) -> None:
    payload = load_mock("customer-info/customer-info-v2.json")
    assert "unknownField" in payload  # the bank mock deliberately includes it
    CustomerInfo.model_validate(payload)  # must not raise


def test_customer_enum_fields_parse_as_enums(load_mock: Callable[[str], Any]) -> None:
    info = CustomerInfo.model_validate(load_mock("customer-info/customer-info-v2.json"))
    assert type(info.status) is CustomerStatus
    spec_condition = info.accounts[0].spec_conditions[0]
    assert type(spec_condition.code) is SpecConditionCode
    assert spec_condition.code is SpecConditionCode.AI11
    assert isinstance(SpecConditionCode.AI11.description, str)
    assert SpecConditionCode.AI11.description != ""


def test_customer_unknown_status_degrades_to_str() -> None:
    info = CustomerInfo.model_validate({"status": "FROZEN"})
    assert info.status == "FROZEN"
    assert type(info.status) is str
