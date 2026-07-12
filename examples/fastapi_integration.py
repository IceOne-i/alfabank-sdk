# ruff: noqa: RUF002
"""Пример интеграции с FastAPI: клиент на время запроса (паттерн fin-doctor).

Ключи хранятся per-tenant (в БД), поэтому клиент создаётся на каждый запрос;
пул соединений живёт внутри httpx и переиспользуется процессом недолго —
для низких RPS это осознанный компромисс в пользу простоты.
"""

from __future__ import annotations

from datetime import date

from fastapi import FastAPI, HTTPException

from alfabank import AlfaBankAPIError, AlfaBankClient

app = FastAPI()


def get_api_key_for_tenant(tenant_id: int) -> str:
    raise NotImplementedError("достаньте ключ из вашего хранилища per-tenant")


@app.get("/tenants/{tenant_id}/accounts/{account_number}/statement")
async def statement(tenant_id: int, account_number: str, statement_date: date) -> dict:
    api_key = get_api_key_for_tenant(tenant_id)
    try:
        async with AlfaBankClient(api_key=api_key) as client:
            transactions = [
                tx.model_dump(mode="json")
                async for tx in client.statements.iter_transactions(
                    account_number, statement_date
                )
            ]
    except AlfaBankAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"transactions": transactions}
