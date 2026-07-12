"""Str-based enums for Alfa API wire values.

Values are the exact strings the API sends. Model fields are typed as
``EnumType | str`` so unknown future values degrade to plain strings instead
of breaking parsing.
"""

from __future__ import annotations

from enum import Enum


class Direction(str, Enum):
    """Направление операции по счёту."""

    DEBIT = "DEBIT"  # списание
    CREDIT = "CREDIT"  # поступление


class CurFormat(str, Enum):
    """Формат блока валютного перевода в выписке (query-параметр curFormat)."""

    CUR_TRANSFER = "curTransfer"
    SWIFT_TRANSFER = "swiftTransfer"


class OperationCode(str, Enum):
    """Код вида расчётной операции (поле operationCode выписки)."""

    PAYMENT_ORDER = "01"
    PAYMENT_REQUEST = "02"
    CASH_DEBIT_ORDER = "03"
    CASH_CREDIT_ORDER = "04"
    COLLECTION_ORDER = "06"
    LETTER_OF_CREDIT = "08"
    MEMORIAL_ORDER = "09"
    PAYMENT_ORDER_16 = "16"
    BANK_ORDER = "17"

    @property
    def description(self) -> str:
        return _OPERATION_CODE_DESCRIPTIONS[self]


_OPERATION_CODE_DESCRIPTIONS: dict[OperationCode, str] = {
    OperationCode.PAYMENT_ORDER: "Платёжное поручение / перевод в иностранной валюте",
    OperationCode.PAYMENT_REQUEST: "Платёжное требование",
    OperationCode.CASH_DEBIT_ORDER: "Расходный кассовый ордер / денежный чек",
    OperationCode.CASH_CREDIT_ORDER: "Приходный кассовый ордер / взнос наличными",
    OperationCode.COLLECTION_ORDER: "Инкассовое поручение",
    OperationCode.LETTER_OF_CREDIT: "Аккредитив",
    OperationCode.MEMORIAL_ORDER: "Мемориальный ордер",
    OperationCode.PAYMENT_ORDER_16: "Платёжный ордер",
    OperationCode.BANK_ORDER: "Банковский ордер",
}


class CustomerStatus(str, Enum):
    """Статус организации (customer-info)."""

    ACTIVE = "ACTIVE"
    LIQUIDATING = "LIQUIDATING"
    LIQUIDATED = "LIQUIDATED"
    BANKRUPT = "BANKRUPT"


class CustomerCategory(str, Enum):
    """Категория организации (customer-info)."""

    BANK = "BANK"
    FINANCIAL = "FINANCIAL"
    OTHER = "OTHER"


class BlockType(str, Enum):
    """Тип блокировки суммы на счёте."""

    OUTGOING_LIMITATION = "OUTGOING_LIMITATION"
    PARTIAL_BALANCE_BLOCK = "PARTIAL_BALANCE_BLOCK"


class SpecConditionCode(str, Enum):
    """Коды специальных условий (ограничений) по счёту."""

    AI11 = "AI11"
    AI12 = "AI12"
    AI14 = "AI14"
    AI17 = "AI17"
    AI20 = "AI20"
    AI30 = "AI30"
    AI47 = "AI47"
    AI82 = "AI82"
    AI83 = "AI83"
    AI87 = "AI87"

    @property
    def description(self) -> str:
        return _SPEC_CONDITION_DESCRIPTIONS[self]


_SPEC_CONDITION_DESCRIPTIONS: dict[SpecConditionCode, str] = {
    SpecConditionCode.AI11: "Нельзя кредитовать",
    SpecConditionCode.AI12: "Нельзя дебетовать",
    SpecConditionCode.AI14: "Клиент закрыт",
    SpecConditionCode.AI17: "Счёт заблокирован",
    SpecConditionCode.AI20: "Неактивный счёт",
    SpecConditionCode.AI30: "Счёт закрыт",
    SpecConditionCode.AI47: "Внутренний счёт",
    SpecConditionCode.AI82: "Дебетование ограничено",
    SpecConditionCode.AI83: "Электронная картотека",
    SpecConditionCode.AI87: "Бумажная разновалютная картотека",
}
