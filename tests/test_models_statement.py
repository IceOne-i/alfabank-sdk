"""Statement models validated against the bank's own mock payloads."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from alfabank.enums import Direction, OperationCode
from alfabank.models.statement import StatementPage, StatementSummary, Transaction


def test_statement_page_parses_bank_mock(load_mock: Callable[[str], Any]) -> None:
    page = StatementPage.model_validate(load_mock("transactions/statement.json"))

    assert len(page) == 1
    assert list(page) == page.transactions
    # the mock only has rel=prev links -> no next page
    assert page.has_next is False
    assert page.next_page is None
    assert page.links[0].rel == "prev"

    tx = page.transactions[0]
    assert tx.direction == Direction.DEBIT
    assert tx.operation_code == OperationCode.PAYMENT_ORDER
    assert tx.uuid == "55daccdf-de87-3879-976c-8b8415c8caf9"
    assert tx.transaction_id == "1211206MOCO#DS0000017"
    assert tx.number == "1843"
    assert tx.payment_purpose == "НДС не облагается"
    assert tx.document_date == date(2021, 10, 7)
    assert tx.operation_date == datetime(2018, 12, 31, tzinfo=timezone.utc)
    assert isinstance(tx.amount.amount, Decimal)
    assert tx.amount.amount == Decimal("1.01")
    assert tx.amount.currency_name == "USD"
    assert tx.amount_rub is not None
    # numbers-as-strings coercion (bank sends JSON numbers here)
    assert tx.debtor_code == "0"
    assert tx.extended_debtor_code == "50012008"


def test_rur_transfer_block(load_mock: Callable[[str], Any]) -> None:
    tx = StatementPage.model_validate(load_mock("transactions/statement.json")).transactions[0]
    rur = tx.rur_transfer
    assert rur is not None
    assert rur.payer_inn == "7720000971"
    assert rur.payer_bank_bic == "012525593"
    assert rur.payee_name == "Наименование получателя"
    assert rur.delivery_kind == "электронно"
    assert rur.purpose_code == "1"
    assert rur.receipt_date == date(2018, 12, 31)
    assert rur.value_date == date(2018, 12, 31)
    assert rur.departmental_info is not None
    assert rur.departmental_info.kbk == "39210202010061000160"
    assert rur.departmental_info.oktmo == "11605000"
    assert rur.departmental_info.doc_date109 == "31.12.2018"  # DD.MM.YYYY stays a string
    assert rur.cart_info is not None
    assert rur.cart_info.document_date == "2019-10-19T06:33:47.923Z"  # cart fields stay strings


def test_swift_and_cur_transfer_blocks(load_mock: Callable[[str], Any]) -> None:
    tx = StatementPage.model_validate(load_mock("transactions/statement.json")).transactions[0]
    swift = tx.swift_transfer
    assert swift is not None
    assert swift.transaction_reference_number == "69528"  # JSON number -> str
    assert swift.exchange_rate == "67,74"  # comma decimals stay strings
    assert swift.instructed_amount == "USD70,00"
    assert swift.message_receive_time == "15-05-27 13:21"
    assert swift.bank_operation_code == "CRED"

    cur = tx.cur_transfer
    assert cur is not None
    assert cur.beneficiary_bank_account == "TESTTT21323"
    assert cur.payee_inn == "7720000971"  # CurTransfer = SwiftTransfer + RUB requisites
    assert cur.payer_bank_corr_account == "30101810200000000593"


def test_next_page_from_synthetic_links() -> None:
    page = StatementPage.model_validate(
        {
            "_links": [{"rel": "next", "href": "?accountNumber=1&page=2"}],
            "transactions": [],
        }
    )
    assert page.has_next is True
    assert page.next_page == 2
    assert len(page) == 0


def test_statement_page_defaults() -> None:
    page = StatementPage.model_validate({})
    assert page.transactions == []
    assert page.links == []
    assert page.has_next is False


def test_transaction_enum_fields_parse_as_enums(load_mock: Callable[[str], Any]) -> None:
    tx = StatementPage.model_validate(load_mock("transactions/statement.json")).transactions[0]
    assert type(tx.direction) is Direction
    assert type(tx.operation_code) is OperationCode
    assert isinstance(tx.operation_code.description, str)
    assert tx.operation_code.description != ""


def test_transaction_unknown_direction_degrades_to_str() -> None:
    tx = Transaction.model_validate({"direction": "SIDEWAYS"})
    assert tx.direction == "SIDEWAYS"
    assert type(tx.direction) is str


def test_summary_parses_bank_mock(load_mock: Callable[[str], Any]) -> None:
    summary = StatementSummary.model_validate(load_mock("transactions/statement-summary.json"))
    assert summary.opening_balance is not None
    assert summary.opening_balance.amount == Decimal("10000.55")
    assert summary.opening_balance.currency_name == "RUR"
    assert summary.closing_balance_rub is not None
    assert summary.closing_balance_rub.amount == Decimal("25000.3")
    assert summary.debit_turnover is not None
    assert summary.debit_turnover.amount == Decimal("10000")
    assert summary.debit_transactions_number == 10
    assert summary.credit_transactions_number == 10
    assert summary.opening_rate is None
    assert summary.composed_date_time == date(2018, 12, 31)
    assert summary.last_movement_date == date(2018, 12, 31)
