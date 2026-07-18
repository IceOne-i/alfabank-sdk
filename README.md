# alfabank-sdk

Асинхронный Python SDK для **Alfa API** Альфа-Банка (интеграция host-to-host):
выписки по счетам, сводка оборотов, информация об организации и её счетах.

- Python >= 3.10, полностью async (httpx), строгая типизация (pydantic v2, `py.typed`)
- Деньги — `Decimal`, никаких float
- Ретраи с учётом идемпотентности, опциональный rate limiter
- Две схемы аутентификации банка: `ApiKey` и `Bearer` + шов `token_provider` под OAuth

## ⚠️ Disclaimer

> **Этот проект — НЕОФИЦИАЛЬНЫЙ SDK.**
>
> Он создан и поддерживается сообществом. Этот SDK **не является официальным**, **не имеет отношения** к АО «Альфа-Банк» ([https://alfabank.ru](https://alfabank.ru)), не одобрен и не спонсирован им. Все упомянутые торговые марки и названия принадлежат их законным владельцам.
>
> Используете на свой страх и риск. Авторы и контрибьюторы не несут ответственности за любые последствия использования этой библиотеки.
>
> ---
>
> **This project is an UNOFFICIAL SDK.**
>
> It is community-maintained and is **NOT affiliated with**, endorsed by, sponsored by, or in any way officially connected with Alfa-Bank (АО «Альфа-Банк», [https://alfabank.ru](https://alfabank.ru)). All trademarks and product names mentioned belong to their respective owners.
>
> Use at your own risk. The authors and contributors are not liable for any consequences arising from the use of this library.

## Установка

```bash
pip install alfabank-sdk
```

## Быстрый старт

```python
import asyncio
from datetime import date

from alfabank import AlfaBankClient


async def main() -> None:
    async with AlfaBankClient(api_key="ВАШ_КЛЮЧ") as client:
        # Профиль организации и счета с балансами
        info = await client.customer.info()
        for account in info.accounts:
            print(account.number, account.amount_balance)

        # Выписка за дату (автопагинация)
        async for tx in client.statements.iter_transactions(
            "40702810102300000001", date(2026, 7, 1)
        ):
            print(tx.direction, tx.amount.amount if tx.amount else None, tx.payment_purpose)

        # Сводка оборотов
        summary = await client.statements.summary("40702810102300000001", date(2026, 7, 1))
        print(summary.closing_balance)


asyncio.run(main())
```

## Аутентификация

Ровно один из трёх способов:

```python
AlfaBankClient(api_key="...")            # Authorization: ApiKey <key>
AlfaBankClient(access_token="...")       # Authorization: Bearer <token>
AlfaBankClient(token_provider=provider)  # (a)sync callable -> значение заголовка
```

OAuth-хелпер (**experimental** — контракт /oidc/token не проверен на живой песочнице):

```python
from alfabank.oauth import OAuthTokenProvider

provider = OAuthTokenProvider(
    client_id="...", client_secret="...", refresh_token="...",
)
client = AlfaBankClient(token_provider=provider)
```

## Песочница и настройка окружения

```python
from alfabank import SANDBOX_BASE_URL, AlfaBankClient

client = AlfaBankClient(api_key="...", base_url=SANDBOX_BASE_URL)
```

`base_url` и `api_prefix` настраиваются: шлюзовые пути могут отличаться
в зависимости от договора с банком. mTLS — через параметры `cert`/`verify`
(PEM) или инъекцию своего `httpx.AsyncClient` в `http_client=`.

## Обработка ошибок

```python
from alfabank import AlfaBankAPIError, AlfaBankRateLimitError

try:
    page = await client.statements.transactions("40702810102300000001", "2026-07-01")
except AlfaBankRateLimitError as exc:
    print("Лимит запросов, повторить через:", exc.retry_after)
except AlfaBankAPIError as exc:
    print(exc.status_code, exc.error_code, exc.request_id, exc.response_body)
```

## Эндпоинты

| Метод SDK | HTTP |
|---|---|
| `client.statements.transactions()` | `GET {prefix}/statement/transactions` |
| `client.statements.iter_transactions()` | автопагинация по `_links rel=next` |
| `client.statements.summary()` | `GET {prefix}/statement/summary` |
| `client.customer.info()` | `GET {prefix}/jp/v2/customer-info` |
| `client.request(method, path)` | произвольный запрос (escape hatch) |

Вендоренные OpenAPI-спеки банка и реалистичные моки: `specs/alfa-api/`.

## Лицензия

MIT
