"""Tests for str-based enums."""

from __future__ import annotations

from alfabank.enums import (
    BlockType,
    CurFormat,
    CustomerCategory,
    CustomerStatus,
    Direction,
    OperationCode,
    SpecConditionCode,
)


def test_direction_is_str() -> None:
    assert Direction.DEBIT == "DEBIT"
    assert Direction.CREDIT == "CREDIT"
    assert isinstance(Direction.DEBIT, str)


def test_cur_format_values() -> None:
    assert CurFormat.CUR_TRANSFER.value == "curTransfer"
    assert CurFormat.SWIFT_TRANSFER.value == "swiftTransfer"


def test_operation_code_lookup_and_description() -> None:
    assert OperationCode("01") is OperationCode.PAYMENT_ORDER
    assert OperationCode("17") is OperationCode.BANK_ORDER
    for member in OperationCode:
        assert member.description  # non-empty Russian text


def test_customer_enums() -> None:
    assert CustomerStatus("ACTIVE") is CustomerStatus.ACTIVE
    assert CustomerCategory("OTHER") is CustomerCategory.OTHER
    assert BlockType("OUTGOING_LIMITATION") is BlockType.OUTGOING_LIMITATION


def test_spec_condition_codes() -> None:
    assert SpecConditionCode("AI11") is SpecConditionCode.AI11
    assert len(list(SpecConditionCode)) == 10
    for member in SpecConditionCode:
        assert member.description
