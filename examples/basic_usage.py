"""Пример: выписка и балансы счетов через alfabank-sdk."""

from __future__ import annotations

import asyncio
import os
from datetime import date, timedelta

from alfabank import AlfaBankClient


async def main() -> None:
    async with AlfaBankClient(api_key=os.environ["ALFABANK_API_KEY"]) as client:
        info = await client.customer.info()
        print(f"Организация: {info.short_name} (ИНН {info.inn})")
        for account in info.accounts:
            print(f"  Счёт {account.number}: {account.amount_balance}")

        if info.accounts and info.accounts[0].number:
            yesterday = date.today() - timedelta(days=1)
            async for tx in client.statements.iter_transactions(
                info.accounts[0].number, yesterday
            ):
                amount = tx.amount.amount if tx.amount else "?"
                print(f"  {tx.direction} {amount} {tx.payment_purpose}")


if __name__ == "__main__":
    asyncio.run(main())
