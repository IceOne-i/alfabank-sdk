# ruff: noqa: RUF002
"""Statements resource: transactions, pagination iterator, turnover summary."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from datetime import date

from alfabank.enums import CurFormat
from alfabank.exceptions import AlfaBankValidationError
from alfabank.models.statement import StatementPage, StatementSummary, Transaction
from alfabank.resources._base import Resource

_ACCOUNT_RE = re.compile(r"^\d{20}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_account_number(account_number: str) -> str:
    if not isinstance(account_number, str) or not _ACCOUNT_RE.match(account_number):
        raise AlfaBankValidationError(
            "account_number must be a 20-digit account number string, "
            f"got {account_number!r}"
        )
    return account_number


def _normalize_date(value: date | str, name: str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and _DATE_RE.match(value):
        return value
    raise AlfaBankValidationError(f"{name} must be a datetime.date or 'YYYY-MM-DD' string")


class StatementsResource(Resource):
    """Выписка и сводка оборотов по счёту."""

    # ---- GET /statement/transactions ----
    async def transactions(
        self,
        account_number: str,
        statement_date: date | str,
        *,
        page: int = 1,
        cur_format: CurFormat | str | None = None,
    ) -> StatementPage:
        """Одна страница выписки за дату (до 1000 операций на страницу)."""
        _validate_account_number(account_number)
        if not isinstance(page, int) or page < 1:
            raise AlfaBankValidationError("page must be a positive integer")
        params: dict[str, str | None] = {
            "accountNumber": account_number,
            "statementDate": _normalize_date(statement_date, "statement_date"),
            "page": str(page),
            "curFormat": (
                cur_format.value if isinstance(cur_format, CurFormat) else cur_format
            ),
        }
        response = await self._transport.request(
            "GET", "/statement/transactions", params=params
        )
        return StatementPage.model_validate(response.json_body)

    async def iter_transactions(
        self,
        account_number: str,
        statement_date: date | str,
        *,
        cur_format: CurFormat | str | None = None,
        start_page: int = 1,
    ) -> AsyncIterator[Transaction]:
        """Все операции за дату: автоматически обходит страницы по _links rel=next."""
        page_number = start_page
        while True:
            page = await self.transactions(
                account_number, statement_date, page=page_number, cur_format=cur_format
            )
            for transaction in page.transactions:
                yield transaction
            next_page = page.next_page
            if next_page is None or next_page <= page_number:
                return
            page_number = next_page

    # ---- GET /statement/summary ----
    async def summary(
        self, account_number: str, statement_date: date | str
    ) -> StatementSummary:
        """Сводка оборотов и остатков по счёту за дату."""
        _validate_account_number(account_number)
        params = {
            "accountNumber": account_number,
            "statementDate": _normalize_date(statement_date, "statement_date"),
        }
        response = await self._transport.request("GET", "/statement/summary", params=params)
        return StatementSummary.model_validate(response.json_body)
