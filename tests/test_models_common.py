"""Tests for the shared model base and Money."""

from __future__ import annotations

from decimal import Decimal

from alfabank.models.common import Money, _AlfaBase


class _Sample(_AlfaBase):
    some_field: str | None = None
    other_value: int | None = None


def test_camel_case_alias_accepted() -> None:
    obj = _Sample.model_validate({"someField": "x", "otherValue": 5})
    assert obj.some_field == "x"
    assert obj.other_value == 5


def test_populate_by_snake_name() -> None:
    assert _Sample(some_field="y").some_field == "y"


def test_unknown_fields_ignored() -> None:
    obj = _Sample.model_validate({"someField": "x", "unknownField": "ignored"})
    assert obj.some_field == "x"


def test_numbers_coerced_to_str() -> None:
    # The bank sends debtorCode/transactionReferenceNumber as JSON numbers.
    assert _Sample.model_validate({"someField": 69528}).some_field == "69528"


def test_money_uses_decimal() -> None:
    money = Money.model_validate({"amount": 1.01, "currencyName": "USD"})
    assert isinstance(money.amount, Decimal)
    assert money.amount == Decimal("1.01")
    assert money.currency_name == "USD"
