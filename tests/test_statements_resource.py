"""StatementsResource tests over respx with the bank's own mocks."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest
import respx

from alfabank._transport import RetryPolicy, Transport
from alfabank.auth import ApiKeyAuth
from alfabank.enums import CurFormat
from alfabank.exceptions import AlfaBankValidationError
from alfabank.models.statement import StatementPage, StatementSummary
from alfabank.resources.statements import StatementsResource
from tests.conftest import TEST_BASE_URL

ACCOUNT = "40702810102300000001"


@pytest.fixture
async def statements() -> AsyncIterator[StatementsResource]:
    transport = Transport(
        token_provider=ApiKeyAuth("test-key"),
        base_url=TEST_BASE_URL,
        retry_policy=RetryPolicy(max_retries=0, backoff_factor=0.0),
    )
    try:
        yield StatementsResource(transport)
    finally:
        await transport.aclose()


async def test_transactions_parses_bank_mock(
    statements: StatementsResource,
    mock_api: respx.MockRouter,
    load_mock: Callable[[str], Any],
) -> None:
    route = mock_api.get("/api/statement/transactions").mock(
        return_value=httpx.Response(200, json=load_mock("transactions/statement.json"))
    )
    page = await statements.transactions(ACCOUNT, date(2023, 1, 30))
    assert isinstance(page, StatementPage)
    assert len(page) == 1
    request = route.calls.last.request
    assert request.url.params["accountNumber"] == ACCOUNT
    assert request.url.params["statementDate"] == "2023-01-30"
    assert request.url.params["page"] == "1"
    assert "curFormat" not in request.url.params


async def test_transactions_sends_cur_format_and_string_date(
    statements: StatementsResource,
    mock_api: respx.MockRouter,
) -> None:
    route = mock_api.get("/api/statement/transactions").mock(
        return_value=httpx.Response(200, json={"transactions": [], "_links": []})
    )
    await statements.transactions(
        ACCOUNT, "2023-01-30", page=2, cur_format=CurFormat.CUR_TRANSFER
    )
    request = route.calls.last.request
    assert request.url.params["curFormat"] == "curTransfer"
    assert request.url.params["page"] == "2"
    assert request.url.params["statementDate"] == "2023-01-30"


@pytest.mark.parametrize(
    ("account", "statement_date", "page"),
    [
        ("123", "2023-01-30", 1),  # not 20 digits
        ("4070281010230000000X", "2023-01-30", 1),  # non-digit
        (ACCOUNT, "30.01.2023", 1),  # wrong date format
        (ACCOUNT, "2023-01-30", 0),  # page < 1
    ],
)
async def test_client_side_validation(
    statements: StatementsResource,
    account: str,
    statement_date: str,
    page: int,
) -> None:
    with pytest.raises(AlfaBankValidationError):
        await statements.transactions(account, statement_date, page=page)


async def test_summary_parses_bank_mock(
    statements: StatementsResource,
    mock_api: respx.MockRouter,
    load_mock: Callable[[str], Any],
) -> None:
    mock_api.get("/api/statement/summary").mock(
        return_value=httpx.Response(
            200, json=load_mock("transactions/statement-summary.json")
        )
    )
    summary = await statements.summary(ACCOUNT, date(2023, 1, 30))
    assert isinstance(summary, StatementSummary)
    assert summary.opening_balance is not None
    assert summary.opening_balance.amount == Decimal("10000.55")


def _page_payload(tx_uuid: str, next_page: int | None) -> dict[str, Any]:
    links = (
        [{"rel": "next", "href": f"accountNumber={ACCOUNT}&statementDate=2023-01-30&page={next_page}"}]
        if next_page is not None
        else []
    )
    return {"_links": links, "transactions": [{"uuid": tx_uuid, "direction": "DEBIT"}]}


async def test_iter_transactions_walks_all_pages(
    statements: StatementsResource,
    mock_api: respx.MockRouter,
) -> None:
    route = mock_api.get("/api/statement/transactions").mock(
        side_effect=[
            httpx.Response(200, json=_page_payload("tx-1", next_page=2)),
            httpx.Response(200, json=_page_payload("tx-2", next_page=None)),
        ]
    )
    collected = [
        tx.uuid async for tx in statements.iter_transactions(ACCOUNT, date(2023, 1, 30))
    ]
    assert collected == ["tx-1", "tx-2"]
    assert route.call_count == 2
    assert route.calls[0].request.url.params["page"] == "1"
    assert route.calls[1].request.url.params["page"] == "2"


async def test_iter_transactions_guards_against_page_loop(
    statements: StatementsResource,
    mock_api: respx.MockRouter,
) -> None:
    # Malformed server response pointing "next" at the same page must not loop forever.
    mock_api.get("/api/statement/transactions").mock(
        return_value=httpx.Response(200, json=_page_payload("tx-1", next_page=1))
    )
    collected = [
        tx.uuid async for tx in statements.iter_transactions(ACCOUNT, date(2023, 1, 30))
    ]
    assert collected == ["tx-1"]
