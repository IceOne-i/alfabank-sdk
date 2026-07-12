# alfabank-sdk — дизайн Python SDK для Альфа-Банк Alfa API (h2h)

Дата: 2026-07-12. Статус: утверждён пользователем (секции 1–3), ожидает финального ревью спеки.

## 1. Контекст и цели

Асинхронный Python SDK для корпоративного REST API Альфа-Банка («Alfa API», интеграция host-to-host).
Основной потребитель — сервис **fin-doctor** (FastAPI, полностью async, Python 3.11, httpx, pydantic 2.x),
которому нужен автоимпорт банковских выписок в журнал операций и сверка балансов счетов.
Структурный образец — **podpislon-sdk** (fin-doctor уже потребляет его с PyPI и полагается на его
конвенции: `async with Client(...)`, иерархия исключений с `status_code`/`request_id`/`response_body`,
идемпотентные ретраи).

Источник истины по API: OpenAPI-спеки и WireMock-моки из квази-официального Java/Kotlin SDK банка
(github.com/alfacomdevelopment/alfa-api-sdk, v0.7.1) — завендорены в `specs/alfa-api/`.
Портал developers.alfabank.ru защищён от ботов и программно недоступен.

### Цели v1
- Выписка по счёту (JSON) с автопагинацией: `GET {prefix}/statement/transactions`
- Сводка оборотов за день: `GET {prefix}/statement/summary`
- Профиль организации + счета с балансами: `GET {prefix}/jp/v2/customer-info`
- Обе схемы аутентификации банка (`ApiKey`, `Bearer`) + шов `token_provider` под OAuth
- Экспериментальный OAuth-хелпер (`alfabank.oauth`)
- Публикация на PyPI как `alfabank-sdk`, импорт `alfabank`

### Не-цели v1 (дорожная карта)
- v1.1: выписки в форматах 1С-XML (`/jp/v2/accounts/{acc}/transactions/1C`) и SWIFT MT940
- v2: платёжные поручения + открепленная CMS-подпись (RSA/ГОСТ КЭП) — спеки платежей в открытом
  доступе нет; код ошибки `conflict` («payment order with same externalId exists») доказывает,
  что эндпоинт существует
- Цифровой рубль (спека завендорена, реализация не планируется)
- Вебхуков у Alfa API нет — модуль webhooks не создаётся; синхронизация у потребителя — polling

## 2. Архитектура

Трёхслойная схема podpislon-sdk, src-layout:

```
src/alfabank/
├── __init__.py        # публичные реэкспорты, __all__, __version__
├── _version.py        # генерируется hatch-vcs (в .gitignore)
├── client.py          # AlfaBankClient — фасад; PRODUCTION_BASE_URL, SANDBOX_BASE_URL
├── auth.py            # ApiKeyAuth, BearerAuth, TokenProvider (Protocol), resolve-логика
├── oauth.py           # experimental: exchange_authorization_code, refresh_access_token,
│                      #   OAuthTokenProvider (кэш + авто-refresh)
├── _transport.py      # httpx.AsyncClient-обёртка: RetryPolicy, AsyncRateLimiter, Response
├── _utils.py          # AsyncRateLimiter, парсинг _links, хелперы дат
├── exceptions.py      # иерархия + raise_for_status()
├── enums.py           # str-based енумы
├── models/
│   ├── __init__.py
│   ├── common.py      # _AlfaBase, Money
│   ├── statement.py   # Transaction, RurTransfer, SwiftTransfer, CurTransfer, CartInfo,
│   │                  #   DepartmentalInfo, StatementPage, StatementSummary
│   └── customer.py    # CustomerInfo, Address, Account, SpecCondition, AccountBlockInfo, BankRef
├── resources/
│   ├── __init__.py
│   ├── _base.py       # Resource: держит transport
│   ├── statements.py  # StatementsResource
│   └── customer.py    # CustomerResource
└── py.typed
```

Плюс: `tests/`, `examples/{basic_usage,fastapi_integration}`, `specs/alfa-api/` (вендоренные
спеки и моки банка), `.github/workflows/{tests,publish}.yml`, `CHANGELOG.md`, `README.md`.

### Клиент

```python
client = AlfaBankClient(
    api_key="...",                # → "Authorization: ApiKey <key>"
    # ИЛИ access_token="..."     # → "Authorization: Bearer <token>"
    # ИЛИ token_provider=fn      # (a)sync callable → полное значение заголовка Authorization;
    #                            #   вызывается перед каждым запросом
    base_url=PRODUCTION_BASE_URL, # "https://baas.alfabank.ru" (см. «Допущения»)
    api_prefix="/api",            # контекстный путь; в песочнице/проде может отличаться
    timeout=30.0,                 # float | httpx.Timeout
    max_retries=3,
    retry_non_idempotent=False,
    rate_limit=None,              # RPS; лимиты банка не документированы — по умолчанию выкл.
    user_agent=DEFAULT_USER_AGENT,
    cert=None,                    # mTLS: путь к PEM или (cert, key) — прокидывается в httpx
    verify=True,                  # SSL-контекст/CA bundle — прокидывается в httpx
    http_client=None,             # инъекция готового httpx.AsyncClient (SDK его не закрывает)
)
```

- Ровно один из `api_key` / `access_token` / `token_provider` обязателен, иначе
  `AlfaBankConfigurationError`.
- Жизненный цикл: `async with` / идемпотентный `aclose()`; правило «не закрывай чужой http_client»
  (`_owns_client`).
- Ресурсы создаются в `__init__` и доступны как атрибуты: `client.statements`, `client.customer`.
- Escape hatch: `await client.request(method, path, **kwargs)` → сырой JSON.
- `sandbox`-константа: `SANDBOX_BASE_URL = "https://sandbox.alfabank.ru"`.

### Transport (`_transport.py`)

Переносится из podpislon-sdk с адаптацией:
- Заголовки по умолчанию: `Authorization` (из auth-провайдера, разрешается на каждый запрос),
  `Accept: application/json`, `User-Agent`.
- `RetryPolicy` с учётом идемпотентности: GET/HEAD/OPTIONS/PUT/DELETE ретраятся при сетевых сбоях,
  5xx и 429; POST/PATCH — только при connect-phase ошибках и статусах {408, 425, 429}.
  Экспоненциальный backoff + джиттер ±25%, потолок 30 с, уважение `Retry-After`.
  В v1 все эндпоинты GET, но политика нужна под будущие платежи.
- `AsyncRateLimiter` (sliding window) — опционален, по умолчанию выключен.
- Собственный `Response`-враппер (`__slots__`): status_code, headers, text, json_body,
  `request_id` — из заголовка **`x-traceid`** (не x-request-id!).
- Сетевые ошибки → `AlfaBankTransportError`; HTTP-ошибки → `exceptions.raise_for_status(...)`.
- Логгер `alfabank` (debug-уровень для ретраев).

### Аутентификация (`auth.py`)

- `TokenProvider = Callable[[], str | Awaitable[str]]` — возвращает полное значение заголовка
  `Authorization` (например `"Bearer eyJ..."`).
- `ApiKeyAuth(key)` → `"ApiKey {key}"`; `BearerAuth(token)` → `"Bearer {token}"` — статические
  реализации; конструкторные шорткаты `api_key=` / `access_token=` оборачивают их.
- Transport разрешает провайдер на каждый запрос (await при необходимости) — это позволяет
  внешнему коду (или `oauth.OAuthTokenProvider`) подменять/обновлять токен без пересоздания клиента.
  Важно для fin-doctor: клиент создаётся per-request из per-business credentials.

### OAuth-хелпер (`oauth.py`) — EXPERIMENTAL

- `async exchange_authorization_code(client_id, client_secret, code, redirect_uri, *, token_url)` и
  `async refresh_access_token(client_id, client_secret, refresh_token, *, token_url)` →
  `TokenPair(access_token, refresh_token, expires_in, ...)`.
- `OAuthTokenProvider(client_id, client_secret, refresh_token, *, token_url, leeway=60)` —
  кэширует access_token, рефрешит при истечении (под `asyncio.Lock`); подставляется в
  `token_provider=`.
- token_url по умолчанию `{base}/oidc/token` (прод `https://baas.alfabank.ru/oidc/token`,
  песочница `https://sandbox.alfabank.ru/oidc/token`). Помечен experimental: контракт известен из
  косвенных источников, на живой песочнице не проверен. Известные TTL: authorization code 120 с,
  refresh_token 180 дней.

## 3. Ресурсы и эндпоинты (ground truth из спек банка)

### `client.statements` (StatementsResource)

**`transactions(account_number, statement_date, *, page=1, cur_format=None)` → `StatementPage`**
`GET {api_prefix}/statement/transactions`
Query: `accountNumber` (обяз., 20 цифр), `statementDate` (обяз., `YYYY-MM-DD`), `page` (int),
`curFormat` (`curTransfer` | `swiftTransfer`; для рублёвых счетов игнорируется — приходит
`rurTransfer`). До 1000 объектов на страницу, размер страницы не настраивается.
Клиентская валидация: непустой account_number (цифры), корректная дата — иначе
`AlfaBankValidationError` до сетевого вызова.

**`iter_transactions(account_number, statement_date, *, cur_format=None, start_page=1)` →
`AsyncIterator[Transaction]`** — крутит `transactions()` по `_links rel=next` до конца.

**`summary(account_number, statement_date)` → `StatementSummary`**
`GET {api_prefix}/statement/summary`, те же обязательные параметры.

### `client.customer` (CustomerResource)

**`info()` → `CustomerInfo`** — `GET {api_prefix}/jp/v2/customer-info`, без параметров.
Содержит `accounts: list[Account]` с балансами — этого достаточно для сверки балансов в
fin-doctor без отдельного accounts-эндпоинта (его спеки у нас нет).

### Пагинация выписки

Ответ содержит `_links: [{href, rel: "next"|"prev"}]`, без общего количества. В спеке `href`
начинается с `?`, в реальном моке банка — без него. Парсим лениво: `urllib.parse.parse_qs`
после отбрасывания необязательного `?`, достаём `page`. `StatementPage`: `transactions`,
`links`, `has_next`, `next_page`, `__iter__`, `__len__`. Поле `links` требует явного
`Field(alias="_links")` — общий `alias_generator=to_camel` подчёркивание не породит.

## 4. Модели (pydantic v2)

Базовый класс — протокол банка camelCase, реальные ответы «грязные»
(моки банка нарочно содержат `unknownField` и числа вместо строк):

```python
class _AlfaBase(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
        coerce_numbers_to_str=True,
    )
```

- **`Money { amount: Decimal, currency_name: str }`** — Decimal, не float. В JSON банка суммы —
  числа; парсим строго через Decimal (pydantic делает это без потери точности).
- **`Transaction`**: `uuid`, `transaction_id`, `number`, `direction` (DEBIT/CREDIT),
  `amount: Money`, `amount_rub: Money | None`, `operation_code` (01/02/03/04/06/08/09/16/17),
  `document_date: date`, `operation_date: datetime`, `payment_purpose`, `priority`,
  `corresponding_account`, `filial`, `revaln`, `debtor_code`, `extended_debtor_code`
  (приходят числами → str), `rur_transfer` / `swift_transfer` / `cur_transfer` (взаимоисключающие
  по типу счёта).
- **`RurTransfer`**: реквизиты контрагентов `payee_*`/`payer_*` (name, inn, kpp, account,
  bank_bic, bank_corr_account, bank_name), `purpose_code`, `delivery_kind`, `receipt_date`,
  `value_date`, `cart_info` (картотека, поле 16), `departmental_info` (налоговые поля:
  uip/101/104 КБК/105 ОКТМО/106/107/108/109/110; `doc_date109` в формате `DD.MM.YYYY` —
  оставляем строкой).
- **`SwiftTransfer`** — поля MT103 (все строки, запятая как десятичный разделитель в
  `exchange_rate`/`instructed_amount` — оставляем строками); **`CurTransfer`** = SwiftTransfer +
  рублёвые реквизиты.
- **`StatementSummary`**: `opening_balance(_rub)`, `closing_balance(_rub)`,
  `debit_turnover(_rub)`, `credit_turnover(_rub)` — все `Money`; `debit_transactions_number`,
  `credit_transactions_number`, `composed_date_time`, `last_movement_date`, `opening_rate`.
- **`CustomerInfo`**: `organization_id`, `full_name`, `short_name`, `inn`, `ogrn`, `okpo`,
  `okved`, `kpps: list[str]`, `organization_form`, `type`, `category`, `status`,
  `registration_date`, `addresses`, `accounts: list[Account]`.
- **`Account`**: `number`, `type`, `type_name`, `open_date`, `currency_code`,
  `amount_balance/amount_total/amount_holds/amount_overdraft_own_funds/amount_overdraft_limit`
  (Decimal), `spec_conditions` (коды блокировок AI11–AI87), `blocked_sums`, `bank`,
  `client_name`, `transit_account_number`.
- Даты: `YYYY-MM-DD` → `date`; ISO instant (`...T00:00:00Z`) → `datetime`; нестандартные форматы
  (`DD.MM.YYYY`, SWIFT `YY-MM-DD HH:MM`) — строками.
- Сериализация запросов не нужна (v1 — только GET с query-параметрами).

### Енумы (`enums.py`, str-based)

`Direction` (DEBIT/CREDIT), `OperationCode` (01…17 + `description` на русском),
`CurFormat` (curTransfer/swiftTransfer), `CustomerStatus` (ACTIVE/LIQUIDATING/LIQUIDATED/BANKRUPT),
`CustomerCategory` (BANK/FINANCIAL/OTHER), `SpecConditionCode` (AI11…AI87 + description),
`BlockType`. Неизвестные значения не роняют парсинг: поля с енумами объявляются как
`EnumType | str` (с before-валидатором, пытающимся привести к енуму) — форвард-совместимость.

## 5. Ошибки

```
AlfaBankError(Exception)
├── AlfaBankConfigurationError
├── AlfaBankAPIError                 # attrs: status_code, error_code, response_body, request_id
│   ├── AlfaBankAuthenticationError  # 401 (invalid_token)
│   ├── AlfaBankPermissionError      # 403 (insufficient_scope | insufficient_privileges | access_denied)
│   ├── AlfaBankNotFoundError        # 404 (unknown_endpoint)
│   ├── AlfaBankConflictError        # 409 (conflict — задел под платежи)
│   ├── AlfaBankRateLimitError       # 429 (тело пустое) + retry_after
│   └── AlfaBankServerError          # 5xx (internal_error)
├── AlfaBankValidationError          # клиентская пре-валидация
└── AlfaBankTransportError           # таймаут / DNS / сеть
```

- Тело ошибки: `{"error": str, "error_description": str}` → `error_code`, message.
  429/503 приходят без тела — сообщение синтезируется из статуса.
- `raise_for_status(status_code, response_body, request_id, headers)` — модульная функция,
  вызывается транспортом. `__str__` = `[HTTP {status}] [{error_code}] {description}`,
  тела длиннее ~250 символов усечены. `request_id` — из `x-traceid`.
- fin-doctor читает `status_code`/`request_id`/`response_body` — имена атрибутов сохраняем 1:1
  с podpislon.

## 6. Поток данных

Resource (валидация аргументов) → `transport.request(method, path, params, idempotent=...)`
(auth-заголовок → rate limit → httpx → retry loop → `Response`) → `raise_for_status` при не-2xx →
`Model.model_validate(json)` → типизированный результат. httpx-типы наружу не протекают.

## 7. Тестирование

- pytest + pytest-asyncio (`asyncio_mode = "auto"`) + respx; конфиг в pyproject.
- Фикстуры conftest: `client` (`AlfaBankClient(api_key="test-key", rate_limit=None, max_retries=0)`
  с `aclose()`), `mock_api` (respx-роутер на PRODUCTION_BASE_URL).
- **Фикстуры ответов — реальные моки банка** из `specs/alfa-api/mocks/`
  (statement.json c RUR+SWIFT блоками и числами-вместо-строк; statement-summary.json;
  customer-info-v2.json с `unknownField`) — не выдуманные ответы.
- Обязательное покрытие: конструктор (ровно один способ auth; оба формата заголовка;
  sync/async token_provider); маппинг ошибок по статусам, включая безтелые 429/503 и
  `Retry-After`; коэрция моделей (Decimal-суммы, числа→строки, unknownField, все форматы дат);
  обе формы `_links` (с `?` и без) и автопагинация iter_transactions на 2+ страницах;
  RetryPolicy-матрица (как test_retries.py в podpislon); rate limiter; экранирование
  query-параметров; `x-traceid` → request_id; oauth-хелпер (respx-мок /oidc/token).
- Ошибки podpislon не повторяем: без deprecated event_loop-фикстуры (loop_scope через конфиг),
  без dead code в retry-цикле, единый стиль аннотаций (`X | None`, `list[...]`).

## 8. Упаковка и CI

- hatchling + hatch-vcs (версия из git-тегов `v*`, `_version.py` в .gitignore, фолбэк
  `0.0.0+unknown`), `requires-python = ">=3.10"`, классификаторы 3.10–3.13, `py.typed`,
  `Typing :: Typed`.
- Зависимости: `httpx>=0.25`, `pydantic>=2.5`. Extras: `dev` (pytest, pytest-asyncio, pytest-cov,
  respx, ruff, mypy).
- Ruff: line-length 100, target py310, select `E,F,W,I,B,UP,N,C4,SIM,RUF`. Mypy strict +
  pydantic-плагин.
- GitHub Actions: `tests.yml` (матрица 3.10–3.13 ubuntu + 3.12 windows; fetch-depth 0;
  ruff → mypy → pytest+coverage), `publish.yml` (PyPI Trusted Publishing по тегу `v*`).
- README (RU): быстрый старт, оба способа auth, пагинация, обработка ошибок, sandbox,
  таблица соответствия эндпоинтам; CHANGELOG.md; examples/.

## 9. Допущения и риски (проверить на песочнице при получении доступа)

1. **Продовый base_url** `https://baas.alfabank.ru` и префикс `/api` — из косвенных источников
   (Java SDK банка использует настраиваемый contextPath, дефолт `/api`; в репо банка продовый URL
   не встречается). Потому оба параметра конфигурируемы, а спека платежей вообще отсутствует.
2. Пути `/{api_prefix}/statement/...` vs `/jp/v1/statement/...` в спеках расходятся — следуем
   Java-клиенту банка (contextPath + короткий путь); при расхождении на живом API лечится
   `api_prefix=`.
3. Контракт `/oidc/token` не проверен (потому oauth — experimental).
4. Требования mTLS для прода неизвестны — закрыто параметрами `cert`/`verify`/`http_client`.
5. Rate limits не документированы — limiter выключен по умолчанию, 429 ретраится с backoff.
6. Вебхуков нет — подтверждено отсутствием любых упоминаний; потребитель делает polling.

## 10. Интеграция с fin-doctor (справочно, вне скоупа SDK)

Паттерн повторяет Подпислон: новый `IntegrationKind.ALFABANK` + `ALTER TYPE` миграция;
credentials (api_key или client_id/secret/refresh_token) — в `BusinessIntegration.credentials`
JSONB per-business; `alfabank_test_connection()` — дешёвый `customer.info()`; клиент открывается
per-request `async with AlfaBankClient(...)`; синк выписок — периодическая задача, маппящая
`Transaction` → `Operation` через существующий импорт-движок (дедупликация по `uuid` транзакции).
