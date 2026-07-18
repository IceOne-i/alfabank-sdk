# ruff: noqa: RUF002
"""Models for GET /statement/transactions and GET /statement/summary."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime
from typing import Annotated

from pydantic import Field

from alfabank._utils import page_from_href
from alfabank.enums import Direction, OperationCode
from alfabank.models.common import Money, _AlfaBase, coerce_to_enum


class CartInfo(_AlfaBase):
    """Картотека (для operationCode 16). Все поля — строки как на проводе."""

    document_code: str | None = None
    document_content: str | None = None
    document_date: str | None = None
    document_number: str | None = None
    payment_number: str | None = None
    rest_amount: str | None = None


class DepartmentalInfo(_AlfaBase):
    """Налоговые / бюджетные реквизиты (поля 101-110 платёжного поручения)."""

    uip: str | None = None
    drawer_status101: str | None = None
    kbk: str | None = None
    oktmo: str | None = None
    reason_code106: str | None = None
    tax_period107: str | None = None
    doc_number108: str | None = None
    doc_date109: str | None = None  # DD.MM.YYYY — не ISO, оставляем строкой
    payment_kind110: str | None = None


class RurTransfer(_AlfaBase):
    """Реквизиты рублёвого перевода."""

    cart_info: CartInfo | None = None
    delivery_kind: str | None = None
    departmental_info: DepartmentalInfo | None = None
    payee_account: str | None = None
    payee_bank_bic: str | None = None
    payee_bank_corr_account: str | None = None
    payee_bank_name: str | None = None
    payee_inn: str | None = None
    payee_kpp: str | None = None
    payee_name: str | None = None
    payer_account: str | None = None
    payer_bank_bic: str | None = None
    payer_bank_corr_account: str | None = None
    payer_bank_name: str | None = None
    payer_inn: str | None = None
    payer_kpp: str | None = None
    payer_name: str | None = None
    paying_condition: str | None = None
    purpose_code: str | None = None
    receipt_date: date | None = None
    value_date: date | None = None


class SwiftTransfer(_AlfaBase):
    """Поля SWIFT MT103. Суммы/курсы с запятой-разделителем остаются строками."""

    bank_operation_code: str | None = None
    beneficiary_bank_account: str | None = None
    beneficiary_bank_name: str | None = None
    beneficiary_bank_option: str | None = None
    beneficiary_customer_account: str | None = None
    beneficiary_customer_name: str | None = None
    details_of_charges: str | None = None
    exchange_rate: str | None = None
    instructed_amount: str | None = None
    instruction_code: str | None = None
    intermediary_bank_account: str | None = None
    intermediary_bank_name: str | None = None
    intermediary_bank_option: str | None = None
    message_destinator: str | None = None
    message_identifier: str | None = None
    message_originator: str | None = None
    message_receive_time: str | None = None
    message_send_time: str | None = None
    message_type: str | None = None
    ordering_customer_account: str | None = None
    ordering_customer_name: str | None = None
    ordering_customer_option: str | None = None
    ordering_institution_account: str | None = None
    ordering_institution_name: str | None = None
    ordering_institution_option: str | None = None
    receiver_charges: str | None = None
    receiver_correspondent_account: str | None = None
    receiver_correspondent_name: str | None = None
    receiver_correspondent_option: str | None = None
    regulatory_reporting: str | None = None
    remittance_information: str | None = None
    sender_charges: str | None = None
    sender_correspondent_account: str | None = None
    sender_correspondent_name: str | None = None
    sender_correspondent_option: str | None = None
    sender_to_receiver_information: str | None = None
    transaction_reference_number: str | None = None
    transaction_related_reference: str | None = None
    transaction_type_code: str | None = None
    urgent: str | None = None
    value_date_currency_interbank_settled_amount: str | None = None


class CurTransfer(SwiftTransfer):
    """Валютный перевод: поля SWIFT + рублёвые реквизиты контрагентов."""

    payee_account: str | None = None
    payee_bank_bic: str | None = None
    payee_bank_corr_account: str | None = None
    payee_bank_name: str | None = None
    payee_inn: str | None = None
    payee_kpp: str | None = None
    payee_name: str | None = None
    payer_account: str | None = None
    payer_bank_bic: str | None = None
    payer_bank_corr_account: str | None = None
    payer_bank_name: str | None = None
    payer_inn: str | None = None
    payer_kpp: str | None = None
    payer_name: str | None = None


class Transaction(_AlfaBase):
    """Одна операция из выписки."""

    uuid: str | None = None
    transaction_id: str | None = None
    number: str | None = None
    direction: Annotated[Direction | str, coerce_to_enum(Direction)] | None = None
    amount: Money | None = None
    amount_rub: Money | None = None
    operation_code: Annotated[OperationCode | str, coerce_to_enum(OperationCode)] | None = None
    document_date: date | None = None
    operation_date: datetime | None = None
    payment_purpose: str | None = None
    priority: str | None = None
    corresponding_account: str | None = None
    filial: str | None = None
    revaln: str | None = None
    debtor_code: str | None = None
    extended_debtor_code: str | None = None
    rur_transfer: RurTransfer | None = None
    swift_transfer: SwiftTransfer | None = None
    cur_transfer: CurTransfer | None = None


class StatementLink(_AlfaBase):
    """Элемент _links: относительная ссылка пагинации."""

    href: str
    rel: str  # "next" | "prev"


class StatementPage(_AlfaBase):
    """Страница выписки: операции + ссылки пагинации."""

    links: list[StatementLink] = Field(default_factory=list, alias="_links")
    transactions: list[Transaction] = Field(default_factory=list)

    @property
    def _next_link(self) -> StatementLink | None:
        for link in self.links:
            if link.rel == "next":
                return link
        return None

    @property
    def has_next(self) -> bool:
        return self._next_link is not None

    @property
    def next_page(self) -> int | None:
        link = self._next_link
        return page_from_href(link.href) if link else None

    def __iter__(self) -> Iterator[Transaction]:  # type: ignore[override]
        return iter(self.transactions)

    def __len__(self) -> int:
        return len(self.transactions)


class StatementSummary(_AlfaBase):
    """Сводка оборотов по счёту за день (GET /statement/summary)."""

    composed_date_time: date | None = None
    last_movement_date: date | None = None
    opening_rate: str | None = None
    opening_balance: Money | None = None
    opening_balance_rub: Money | None = None
    closing_balance: Money | None = None
    closing_balance_rub: Money | None = None
    debit_turnover: Money | None = None
    debit_turnover_rub: Money | None = None
    credit_turnover: Money | None = None
    credit_turnover_rub: Money | None = None
    debit_transactions_number: int | None = None
    credit_transactions_number: int | None = None
