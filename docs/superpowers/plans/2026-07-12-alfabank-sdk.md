# alfabank-sdk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Async Python SDK for Alfa-Bank Alfa API (h2h): account statements, turnover summary, customer info — mirroring podpislon-sdk architecture, published as `alfabank-sdk` (import `alfabank`).

**Architecture:** Three layers — `AlfaBankClient` facade → private `Transport` (httpx, idempotency-aware retries, optional rate limiter, own `Response` wrapper) → resource classes returning pydantic-v2 models. Dual auth (`ApiKey`/`Bearer`) through a `token_provider` seam; experimental `alfabank.oauth` module. No webhooks (the API has none).

**Tech Stack:** Python >=3.10, httpx>=0.25, pydantic>=2.5, hatchling+hatch-vcs, pytest+pytest-asyncio+respx, ruff, mypy(strict).

Spec: `docs/superpowers/specs/2026-07-12-alfabank-sdk-design.md`. Ground truth for wire formats: `specs/alfa-api/` (vendored bank OpenAPI YAMLs + realistic mocks).

## Global Constraints

- `requires-python = ">=3.10"`; runtime deps ONLY `httpx>=0.25` and `pydantic>=2.5`.
- Async-only (`httpx.AsyncClient`). No sync API.
- Wire protocol is camelCase JSON → models use `alias_generator=to_camel`, `populate_by_name=True`, `extra="ignore"`, `coerce_numbers_to_str=True`. Money amounts are `Decimal`, never float.
- Exceptions all prefixed `AlfaBank`; `AlfaBankAPIError` carries `status_code`, `error_code`, `response_body`, `request_id` (fin-doctor reads these attribute names — do not rename).
- `request_id` comes from the **`x-traceid`** response header.
- Constants: `PRODUCTION_BASE_URL = "https://baas.alfabank.ru"`, `SANDBOX_BASE_URL = "https://sandbox.alfabank.ru"`, default `api_prefix = "/api"`.
- Error body shape: `{"error": "<code>", "error_description": "<text>"}`; 429/503 arrive with NO body.
- Tests: pytest + pytest-asyncio (`asyncio_mode = "auto"`) + respx. Response fixtures load the vendored bank mocks from `specs/alfa-api/mocks/` — do not invent payloads where a mock exists.
- Lint/type: ruff (line-length 100, target py310, select `E,F,W,I,B,UP,N,C4,SIM,RUF`, ignore E501), mypy strict + pydantic plugin, run against `src/alfabank`.
- Every module starts with a docstring. `from __future__ import annotations` in every source file. Style `X | None`, `list[...]` (no `Optional`/`List`).
- All commands below assume the project venv: create once via `uv venv .venv && uv pip install -e ".[dev]"`. Run tools as `.venv/Scripts/python -m pytest ...` (Windows). If `uv` is unavailable: `python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"`.
- Commit after every task (conventional messages: `feat:`, `test:`, `docs:`, `ci:`, `chore:`).

## File Structure

```
pyproject.toml                      # hatchling+hatch-vcs, deps, pytest/ruff/mypy/coverage config
src/alfabank/
├── __init__.py                     # public re-exports, __all__, __version__
├── py.typed                        # PEP 561 marker (empty file)
├── client.py                       # AlfaBankClient facade + URL/UA constants
├── auth.py                         # ApiKeyAuth, BearerAuth, TokenProvider, resolve_authorization
├── oauth.py                        # experimental OAuth helpers + OAuthTokenProvider
├── _transport.py                   # RetryPolicy, Response, Transport
├── _utils.py                       # AsyncRateLimiter, page_from_href
├── exceptions.py                   # hierarchy + raise_for_status
├── enums.py                        # str-based enums
├── models/
│   ├── __init__.py                 # re-exports
│   ├── common.py                   # _AlfaBase, Money
│   ├── statement.py                # Transaction & nested blocks, StatementPage, StatementSummary
│   └── customer.py                 # CustomerInfo, Account & nested blocks
└── resources/
    ├── __init__.py                 # re-exports
    ├── _base.py                    # Resource
    ├── statements.py               # StatementsResource
    └── customer.py                 # CustomerResource
tests/
├── __init__.py                     # empty; makes `from tests.conftest import ...` importable
├── conftest.py                     # mock loader fixture; later: base_url/mock_api/client fixtures
├── test_package.py                 # smoke import
├── test_exceptions.py
├── test_enums.py
├── test_models_common.py
├── test_utils.py
├── test_models_statement.py
├── test_models_customer.py
├── test_auth.py
├── test_retry_policy.py            # RetryPolicy + Response (pure unit)
├── test_transport.py               # Transport over respx
├── test_statements_resource.py
├── test_customer_resource.py
├── test_client.py
├── test_oauth.py
└── test_public_api.py
examples/basic_usage.py, examples/fastapi_integration.py
.github/workflows/tests.yml, .github/workflows/publish.yml
README.md, CHANGELOG.md
```

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`, `src/alfabank/__init__.py`, `src/alfabank/py.typed`, `tests/__init__.py`, `tests/test_package.py`, `README.md` (stub)

**Interfaces:**
- Consumes: nothing
- Produces: installable package `alfabank` with `__version__: str`; pytest/ruff/mypy configured. Later tasks import `alfabank.*` and run `.venv/Scripts/python -m pytest`.

- [ ] **Step 1: Write the failing smoke test**

`tests/test_package.py`:

```python
"""Smoke test: the package installs and exposes a version."""

from __future__ import annotations


def test_package_imports() -> None:
    import alfabank

    assert isinstance(alfabank.__version__, str)
    assert alfabank.__version__
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling", "hatch-vcs"]
build-backend = "hatchling.build"

[project]
name = "alfabank-sdk"
dynamic = ["version"]
description = "Async Python SDK for the Alfa-Bank Alfa API (h2h): statements, turnover summary, customer info"
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
authors = [{ name = "Nikita Belan" }]
keywords = ["alfabank", "alfa-api", "bank", "statements", "sdk", "async"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Typing :: Typed",
]
dependencies = [
    "httpx>=0.25",
    "pydantic>=2.5",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "pytest-cov",
    "respx>=0.21",
    "ruff",
    "mypy",
]

[tool.hatch.version]
source = "vcs"

[tool.hatch.version.raw-options]
local_scheme = "no-local-version"

[tool.hatch.build.hooks.vcs]
version-file = "src/alfabank/_version.py"

[tool.hatch.build.targets.wheel]
packages = ["src/alfabank"]

[tool.pytest.ini_options]
addopts = "-ra -q --strict-markers"
testpaths = ["tests"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "N", "C4", "SIM", "RUF"]
ignore = ["E501"]

[tool.mypy]
strict = true
plugins = ["pydantic.mypy"]

[tool.coverage.run]
branch = true
source = ["alfabank"]
```

- [ ] **Step 3: Create the package**

`src/alfabank/__init__.py`:

```python
"""alfabank-sdk: async Python SDK for the Alfa-Bank Alfa API (h2h)."""

from __future__ import annotations

try:
    from alfabank._version import __version__
except ImportError:  # pragma: no cover - version file is generated at build time
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
```

`src/alfabank/py.typed`: create as an **empty file**.

`tests/__init__.py`: create as an **empty file** (lets tests import shared constants via `from tests.conftest import ...`).

`README.md` (stub; full content in Task 15):

```markdown
# alfabank-sdk

Async Python SDK для Alfa API Альфа-Банка (h2h): выписки, сводка оборотов, информация об организации.

Документация появится по мере реализации. Спека: `docs/superpowers/specs/2026-07-12-alfabank-sdk-design.md`.
```

- [ ] **Step 4: Install and verify the test passes**

```bash
uv venv .venv && uv pip install -e ".[dev]"
.venv/Scripts/python -m pytest tests/test_package.py -v
```

Expected: 1 passed. Also verify lint/type baseline:

```bash
.venv/Scripts/python -m ruff check src tests
.venv/Scripts/python -m mypy src/alfabank
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src tests README.md
git commit -m "feat: project scaffolding for alfabank-sdk (hatchling, ruff, mypy, pytest)"
```

---

### Task 2: Exceptions

**Files:**
- Create: `src/alfabank/exceptions.py`
- Test: `tests/test_exceptions.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `AlfaBankError(Exception)`, `AlfaBankConfigurationError`, `AlfaBankValidationError`, `AlfaBankTransportError`
  - `AlfaBankAPIError(message, *, status_code: int | None = None, error_code: str | None = None, response_body: Any = None, request_id: str | None = None)` and subclasses `AlfaBankAuthenticationError` (401), `AlfaBankPermissionError` (403), `AlfaBankNotFoundError` (404), `AlfaBankConflictError` (409), `AlfaBankRateLimitError` (429, extra attr `retry_after: float | None`), `AlfaBankServerError` (5xx)
  - `raise_for_status(*, status_code: int, response_body: Any, request_id: str | None = None, headers: Mapping[str, str] | None = None) -> None` — no-op for 200–399, raises mapped exception otherwise.

- [ ] **Step 1: Write the failing tests**

`tests/test_exceptions.py`:

```python
"""Tests for the exception hierarchy and HTTP status mapping."""

from __future__ import annotations

import pytest

from alfabank.exceptions import (
    AlfaBankAPIError,
    AlfaBankAuthenticationError,
    AlfaBankConfigurationError,
    AlfaBankConflictError,
    AlfaBankError,
    AlfaBankNotFoundError,
    AlfaBankPermissionError,
    AlfaBankRateLimitError,
    AlfaBankServerError,
    AlfaBankTransportError,
    AlfaBankValidationError,
    raise_for_status,
)


def test_hierarchy() -> None:
    for exc_type in (
        AlfaBankConfigurationError,
        AlfaBankAPIError,
        AlfaBankValidationError,
        AlfaBankTransportError,
    ):
        assert issubclass(exc_type, AlfaBankError)
    for exc_type in (
        AlfaBankAuthenticationError,
        AlfaBankPermissionError,
        AlfaBankNotFoundError,
        AlfaBankConflictError,
        AlfaBankRateLimitError,
        AlfaBankServerError,
    ):
        assert issubclass(exc_type, AlfaBankAPIError)


def test_api_error_str_contains_status_and_code() -> None:
    exc = AlfaBankAPIError(
        "Something failed",
        status_code=400,
        error_code="invalid_request",
        response_body={"error": "invalid_request"},
        request_id="a57610880b621435",
    )
    text = str(exc)
    assert "[HTTP 400]" in text
    assert "invalid_request" in text
    assert exc.status_code == 400
    assert exc.error_code == "invalid_request"
    assert exc.request_id == "a57610880b621435"


@pytest.mark.parametrize("status", [200, 204, 302, 399])
def test_raise_for_status_success_is_noop(status: int) -> None:
    raise_for_status(status_code=status, response_body=None)


@pytest.mark.parametrize(
    ("status", "error_code", "expected_type"),
    [
        (401, "invalid_token", AlfaBankAuthenticationError),
        (403, "insufficient_scope", AlfaBankPermissionError),
        (404, "unknown_endpoint", AlfaBankNotFoundError),
        (409, "conflict", AlfaBankConflictError),
        (500, "internal_error", AlfaBankServerError),
        (503, None, AlfaBankServerError),
    ],
)
def test_raise_for_status_maps_statuses(
    status: int, error_code: str | None, expected_type: type[AlfaBankAPIError]
) -> None:
    body = (
        {"error": error_code, "error_description": "details here"}
        if error_code is not None
        else None
    )
    with pytest.raises(expected_type) as exc_info:
        raise_for_status(status_code=status, response_body=body, request_id="trace-1")
    exc = exc_info.value
    assert exc.status_code == status
    assert exc.error_code == error_code
    assert exc.request_id == "trace-1"
    assert exc.response_body == body


def test_unmapped_4xx_is_plain_api_error() -> None:
    with pytest.raises(AlfaBankAPIError) as exc_info:
        raise_for_status(
            status_code=400,
            response_body={"error": "invalid_request", "error_description": "bad"},
        )
    assert type(exc_info.value) is AlfaBankAPIError
    assert exc_info.value.error_code == "invalid_request"


def test_rate_limit_extracts_retry_after_and_survives_empty_body() -> None:
    with pytest.raises(AlfaBankRateLimitError) as exc_info:
        raise_for_status(
            status_code=429,
            response_body=None,
            headers={"retry-after": "7"},
        )
    exc = exc_info.value
    assert exc.retry_after == 7.0
    assert exc.status_code == 429
    assert str(exc)  # message synthesized despite empty body


def test_rate_limit_invalid_retry_after_is_none() -> None:
    with pytest.raises(AlfaBankRateLimitError) as exc_info:
        raise_for_status(status_code=429, response_body=None, headers={"Retry-After": "nope"})
    assert exc_info.value.retry_after is None


def test_long_body_truncated_in_message() -> None:
    with pytest.raises(AlfaBankAPIError) as exc_info:
        raise_for_status(status_code=400, response_body={"error_description": "x" * 1000})
    assert len(str(exc_info.value)) < 500
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_exceptions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'alfabank.exceptions'`

- [ ] **Step 3: Implement `src/alfabank/exceptions.py`**

```python
"""Exception hierarchy for alfabank-sdk and HTTP status -> exception mapping.

The Alfa API reports errors via HTTP status codes with a JSON body of the
shape ``{"error": "<code>", "error_description": "<text>"}``. 429 and 503
responses arrive without a body.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_MAX_BODY_CHARS = 250


def _short_repr(value: Any) -> str:
    text = repr(value)
    if len(text) > _MAX_BODY_CHARS:
        return text[:_MAX_BODY_CHARS] + "..."
    return text


class AlfaBankError(Exception):
    """Base class for all alfabank-sdk errors."""


class AlfaBankConfigurationError(AlfaBankError):
    """Invalid client configuration (bad constructor arguments, credentials)."""


class AlfaBankValidationError(AlfaBankError):
    """Client-side validation failed before any network I/O."""


class AlfaBankTransportError(AlfaBankError):
    """Network-level failure: timeout, DNS, connection problems."""


class AlfaBankAPIError(AlfaBankError):
    """Non-success HTTP response from the Alfa API."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
        response_body: Any = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.response_body = response_body
        self.request_id = request_id

    def __str__(self) -> str:
        parts = []
        if self.status_code is not None:
            parts.append(f"[HTTP {self.status_code}]")
        if self.error_code:
            parts.append(f"[{self.error_code}]")
        parts.append(self.message)
        return " ".join(parts)


class AlfaBankAuthenticationError(AlfaBankAPIError):
    """401: the access token / API key is missing, expired or invalid."""


class AlfaBankPermissionError(AlfaBankAPIError):
    """403: insufficient scope or no access to the requested account."""


class AlfaBankNotFoundError(AlfaBankAPIError):
    """404: endpoint or entity not found / not active."""


class AlfaBankConflictError(AlfaBankAPIError):
    """409: conflicting state (e.g. duplicate externalId on payments)."""


class AlfaBankRateLimitError(AlfaBankAPIError):
    """429: rate limit exceeded. ``retry_after`` holds the server hint, if any."""

    def __init__(
        self,
        message: str,
        *,
        retry_after: float | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class AlfaBankServerError(AlfaBankAPIError):
    """5xx: internal error on the bank side."""


_DEFAULT_MESSAGES: dict[int, str] = {
    401: "Authentication failed",
    403: "Insufficient privileges",
    404: "Not found",
    409: "Conflict",
    429: "Rate limit exceeded",
}


def _parse_retry_after(headers: Mapping[str, str] | None) -> float | None:
    if not headers:
        return None
    raw = None
    for key, value in headers.items():
        if key.lower() == "retry-after":
            raw = value
            break
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def raise_for_status(
    *,
    status_code: int,
    response_body: Any,
    request_id: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> None:
    """Raise the mapped :class:`AlfaBankAPIError` subclass for non-2xx/3xx statuses.

    Statuses in the 200-399 range are treated as success (mirrors the bank's
    own reference client).
    """
    if 200 <= status_code < 400:
        return

    error_code: str | None = None
    description: str | None = None
    if isinstance(response_body, Mapping):
        raw_code = response_body.get("error")
        raw_description = response_body.get("error_description")
        error_code = str(raw_code) if raw_code is not None else None
        description = str(raw_description) if raw_description is not None else None

    message = description or _DEFAULT_MESSAGES.get(
        status_code, f"Alfa API request failed with HTTP {status_code}"
    )
    if response_body is not None and description is None:
        message = f"{message}: {_short_repr(response_body)}"
    if len(message) > _MAX_BODY_CHARS:
        message = message[:_MAX_BODY_CHARS] + "..."

    kwargs: dict[str, Any] = {
        "status_code": status_code,
        "error_code": error_code,
        "response_body": response_body,
        "request_id": request_id,
    }
    if status_code == 401:
        raise AlfaBankAuthenticationError(message, **kwargs)
    if status_code == 403:
        raise AlfaBankPermissionError(message, **kwargs)
    if status_code == 404:
        raise AlfaBankNotFoundError(message, **kwargs)
    if status_code == 409:
        raise AlfaBankConflictError(message, **kwargs)
    if status_code == 429:
        raise AlfaBankRateLimitError(
            message, retry_after=_parse_retry_after(headers), **kwargs
        )
    if status_code >= 500:
        raise AlfaBankServerError(message, **kwargs)
    raise AlfaBankAPIError(message, **kwargs)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_exceptions.py -v`
Expected: all PASS. Then `.venv/Scripts/python -m ruff check src tests && .venv/Scripts/python -m mypy src/alfabank` — clean.

- [ ] **Step 5: Commit**

```bash
git add src/alfabank/exceptions.py tests/test_exceptions.py
git commit -m "feat: exception hierarchy with Alfa API status mapping"
```

---

### Task 3: Enums

**Files:**
- Create: `src/alfabank/enums.py`
- Test: `tests/test_enums.py`

**Interfaces:**
- Consumes: nothing
- Produces: `Direction` (DEBIT/CREDIT), `CurFormat` (CUR_TRANSFER="curTransfer", SWIFT_TRANSFER="swiftTransfer"), `OperationCode` ("01".."17" with `description` property), `CustomerStatus`, `CustomerCategory`, `BlockType`, `SpecConditionCode` (AI11..AI87 with `description` property). All `str`-mixin enums.

- [ ] **Step 1: Write the failing tests**

`tests/test_enums.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_enums.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'alfabank.enums'`

- [ ] **Step 3: Implement `src/alfabank/enums.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_enums.py -v`
Expected: all PASS. Ruff + mypy clean.

- [ ] **Step 5: Commit**

```bash
git add src/alfabank/enums.py tests/test_enums.py
git commit -m "feat: str-based enums for Alfa API wire values"
```

---

### Task 4: Model base and Money

**Files:**
- Create: `src/alfabank/models/__init__.py`, `src/alfabank/models/common.py`
- Test: `tests/test_models_common.py`

**Interfaces:**
- Consumes: nothing
- Produces: `_AlfaBase(BaseModel)` (camelCase aliases, lenient), `Money` with `amount: Decimal`, `currency_name: str | None`. `models/__init__.py` re-exports `Money` (extended in later tasks).

- [ ] **Step 1: Write the failing tests**

`tests/test_models_common.py`:

```python
"""Tests for the shared model base and Money."""

from __future__ import annotations

from decimal import Decimal

from alfabank.models.common import Money, _AlfaBase


class _Sample(_AlfaBase):
    some_field: str | None = None
    other_value: int | None = None


def test_camel_case_alias_accepted() -> None:
    obj = _Sample.model_validate({"someField": "x", "otherValue": 5})
    assert obj.some_field == "x"
    assert obj.other_value == 5


def test_populate_by_snake_name() -> None:
    assert _Sample(some_field="y").some_field == "y"


def test_unknown_fields_ignored() -> None:
    obj = _Sample.model_validate({"someField": "x", "unknownField": "ignored"})
    assert obj.some_field == "x"


def test_numbers_coerced_to_str() -> None:
    # The bank sends debtorCode/transactionReferenceNumber as JSON numbers.
    assert _Sample.model_validate({"someField": 69528}).some_field == "69528"


def test_money_uses_decimal() -> None:
    money = Money.model_validate({"amount": 1.01, "currencyName": "USD"})
    assert isinstance(money.amount, Decimal)
    assert money.amount == Decimal("1.01")
    assert money.currency_name == "USD"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_models_common.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'alfabank.models'`

- [ ] **Step 3: Implement**

`src/alfabank/models/common.py`:

```python
"""Shared pydantic base class and primitive value models."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _AlfaBase(BaseModel):
    """Base for all wire models.

    The Alfa API speaks camelCase JSON and is loose with types: real payloads
    contain unknown extra fields and JSON numbers where the spec says string.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
        coerce_numbers_to_str=True,
    )


class Money(_AlfaBase):
    """Denominated amount; Decimal to avoid float artifacts on money."""

    amount: Decimal
    currency_name: str | None = None
```

`src/alfabank/models/__init__.py`:

```python
"""Public pydantic models for the Alfa API."""

from alfabank.models.common import Money

__all__ = ["Money"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_models_common.py -v`
Expected: all PASS. Ruff + mypy clean.

- [ ] **Step 5: Commit**

```bash
git add src/alfabank/models tests/test_models_common.py
git commit -m "feat: shared model base (_AlfaBase) and Money with Decimal amounts"
```

---

### Task 5: Utilities — rate limiter and pagination href parsing

**Files:**
- Create: `src/alfabank/_utils.py`
- Test: `tests/test_utils.py`

**Interfaces:**
- Consumes: nothing
- Produces: `AsyncRateLimiter(rate: int, per: float = 1.0)` with `async acquire() -> None`; `page_from_href(href: str) -> int | None` (accepts hrefs with and without leading `?` — the bank's spec shows `?page=3`, the real mock sends `page=3` without `?`).

- [ ] **Step 1: Write the failing tests**

`tests/test_utils.py`:

```python
"""Tests for internal utilities."""

from __future__ import annotations

import time

import pytest

from alfabank._utils import AsyncRateLimiter, page_from_href


@pytest.mark.parametrize(
    ("href", "expected"),
    [
        ("?accountNumber=40700010000006103990&statementDate=2018-03-15&page=3", 3),
        ("accountNumber=40700010000006103990&statementDate=2018-03-15&page=3", 3),
        ("?page=1", 1),
        ("accountNumber=1", None),
        ("", None),
        ("page=abc", None),
    ],
)
def test_page_from_href(href: str, expected: int | None) -> None:
    assert page_from_href(href) == expected


def test_rate_limiter_rejects_non_positive_rate() -> None:
    with pytest.raises(ValueError):
        AsyncRateLimiter(0)


async def test_rate_limiter_allows_burst_within_rate() -> None:
    limiter = AsyncRateLimiter(rate=5, per=1.0)
    start = time.monotonic()
    for _ in range(5):
        await limiter.acquire()
    assert time.monotonic() - start < 0.2


async def test_rate_limiter_delays_when_rate_exceeded() -> None:
    limiter = AsyncRateLimiter(rate=2, per=0.3)
    start = time.monotonic()
    for _ in range(3):
        await limiter.acquire()
    assert time.monotonic() - start >= 0.2  # third call had to wait ~0.3s window
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_utils.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'alfabank._utils'`

- [ ] **Step 3: Implement `src/alfabank/_utils.py`**

```python
"""Internal helpers: async rate limiting and statement pagination parsing."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from urllib.parse import parse_qs


def page_from_href(href: str) -> int | None:
    """Extract the ``page`` number from a statement ``_links`` href.

    The OpenAPI spec shows hrefs like ``?accountNumber=...&page=3`` while the
    bank's real mock sends them without the leading ``?`` — accept both.
    """
    query = href[1:] if href.startswith("?") else href
    values = parse_qs(query).get("page")
    if not values:
        return None
    try:
        return int(values[0])
    except ValueError:
        return None


class AsyncRateLimiter:
    """Sliding-window rate limiter: at most ``rate`` acquisitions per ``per`` seconds."""

    def __init__(self, rate: int, per: float = 1.0) -> None:
        if rate <= 0:
            raise ValueError("rate must be a positive integer")
        self._rate = rate
        self._per = per
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                while self._timestamps and now - self._timestamps[0] >= self._per:
                    self._timestamps.popleft()
                if len(self._timestamps) < self._rate:
                    self._timestamps.append(now)
                    return
                delay = self._per - (now - self._timestamps[0])
            await asyncio.sleep(max(delay, 0.001))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_utils.py -v`
Expected: all PASS. Ruff + mypy clean.

- [ ] **Step 5: Commit**

```bash
git add src/alfabank/_utils.py tests/test_utils.py
git commit -m "feat: async sliding-window rate limiter and _links page parsing"
```

---

### Task 6: Statement models

**Files:**
- Create: `src/alfabank/models/statement.py`, `tests/conftest.py`
- Modify: `src/alfabank/models/__init__.py`
- Test: `tests/test_models_statement.py`

**Interfaces:**
- Consumes: `_AlfaBase`, `Money` (Task 4); `Direction`, `OperationCode` (Task 3); `page_from_href` (Task 5)
- Produces: `CartInfo`, `DepartmentalInfo`, `RurTransfer`, `SwiftTransfer`, `CurTransfer(SwiftTransfer)`, `Transaction`, `StatementLink`, `StatementPage` (`links` aliased to `_links`; `has_next: bool`, `next_page: int | None`, `__iter__`, `__len__`), `StatementSummary`. Test fixture `load_mock` (loads JSON from `specs/alfa-api/mocks/`).

- [ ] **Step 1: Create the shared mock-loading fixture**

`tests/conftest.py` (new file; extended in Tasks 10 and 13):

```python
"""Shared pytest fixtures for alfabank-sdk tests."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

_MOCKS_DIR = Path(__file__).resolve().parent.parent / "specs" / "alfa-api" / "mocks"


@pytest.fixture
def load_mock() -> Callable[[str], Any]:
    """Load a vendored bank mock JSON by path relative to specs/alfa-api/mocks/."""

    def _load(relpath: str) -> Any:
        return json.loads((_MOCKS_DIR / relpath).read_text(encoding="utf-8"))

    return _load
```

- [ ] **Step 2: Write the failing tests**

`tests/test_models_statement.py`:

```python
"""Statement models validated against the bank's own mock payloads."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from alfabank.enums import Direction, OperationCode
from alfabank.models.statement import StatementPage, StatementSummary


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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_models_statement.py -v`
Expected: FAIL with `ImportError` (no `alfabank.models.statement`)

- [ ] **Step 4: Implement `src/alfabank/models/statement.py`**

```python
"""Models for GET /statement/transactions and GET /statement/summary."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import Field

from alfabank._utils import page_from_href
from alfabank.enums import Direction, OperationCode
from alfabank.models.common import Money, _AlfaBase


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
    direction: Direction | str | None = None
    amount: Money | None = None
    amount_rub: Money | None = None
    operation_code: OperationCode | str | None = None
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

    def __iter__(self):  # type: ignore[override]
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
```

Update `src/alfabank/models/__init__.py`:

```python
"""Public pydantic models for the Alfa API."""

from alfabank.models.common import Money
from alfabank.models.statement import (
    CartInfo,
    CurTransfer,
    DepartmentalInfo,
    RurTransfer,
    StatementLink,
    StatementPage,
    StatementSummary,
    SwiftTransfer,
    Transaction,
)

__all__ = [
    "CartInfo",
    "CurTransfer",
    "DepartmentalInfo",
    "Money",
    "RurTransfer",
    "StatementLink",
    "StatementPage",
    "StatementSummary",
    "SwiftTransfer",
    "Transaction",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_models_statement.py -v`
Expected: all PASS. Note: `tx.direction == Direction.DEBIT` works because the smart union picks the enum for known values; unknown values would fall back to `str` without raising. Ruff + mypy clean (the `__iter__` override needs the `# type: ignore[override]` shown above because pydantic's `BaseModel.__iter__` yields key/value pairs).

- [ ] **Step 6: Commit**

```bash
git add src/alfabank/models tests/conftest.py tests/test_models_statement.py
git commit -m "feat: statement models validated against vendored bank mocks"
```

---

### Task 7: Customer info models

**Files:**
- Create: `src/alfabank/models/customer.py`
- Modify: `src/alfabank/models/__init__.py`
- Test: `tests/test_models_customer.py`

**Interfaces:**
- Consumes: `_AlfaBase` (Task 4); `CustomerStatus`, `CustomerCategory`, `SpecConditionCode`, `BlockType` (Task 3); `load_mock` fixture (Task 6)
- Produces: `OrganizationForm`, `Address`, `SpecCondition`, `AccountBlockInfo`, `BankRef`, `Account`, `CustomerInfo` (`accounts: list[Account]`).

- [ ] **Step 1: Write the failing tests**

`tests/test_models_customer.py`:

```python
"""Customer-info models validated against the bank's own mock payload."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from alfabank.enums import CustomerCategory, CustomerStatus, SpecConditionCode
from alfabank.models.customer import BankRef, CustomerInfo


def test_customer_info_parses_bank_mock(load_mock: Callable[[str], Any]) -> None:
    info = CustomerInfo.model_validate(load_mock("customer-info/customer-info-v2.json"))

    assert info.organization_id == (
        "1ba92f29c6a39a60b5bf487a4c8c63631c10c6b3b98e0b7428668838c857b50b"
    )
    assert info.full_name == "Test Organization"
    assert info.inn == "0000000000"
    assert info.kpps == ["000000000"]
    assert info.status == CustomerStatus.ACTIVE
    assert info.category == CustomerCategory.OTHER
    assert info.registration_date == datetime(2020, 1, 1, tzinfo=timezone.utc)
    assert info.organization_form is not None
    assert info.organization_form.code == "00000"


def test_customer_addresses(load_mock: Callable[[str], Any]) -> None:
    info = CustomerInfo.model_validate(load_mock("customer-info/customer-info-v2.json"))
    address = info.addresses[0]
    assert address.type == "LEGAL_FULL"
    assert address.zip == "000000"
    assert address.country == "000"
    assert address.full_address == "Test Address"
    assert address.settlement_type == "city"


def test_customer_accounts(load_mock: Callable[[str], Any]) -> None:
    info = CustomerInfo.model_validate(load_mock("customer-info/customer-info-v2.json"))
    account = info.accounts[0]
    assert account.number == "00000000000000000000"
    assert account.type == "PAYMENT"
    assert account.open_date == date(2020, 1, 1)
    assert isinstance(account.amount_balance, Decimal)
    assert account.amount_balance == Decimal("1000.00")
    assert account.amount_holds == Decimal("0.00")
    assert account.amount_overdraft_limit is None  # absent in mock
    assert account.blocked_sums == []  # absent in mock -> default
    assert isinstance(account.bank, BankRef)  # empty {} object in mock
    assert account.bank.bic is None
    assert len(account.spec_conditions) == 10
    first = account.spec_conditions[0]
    assert first.code == SpecConditionCode.AI11
    assert first.value is False
    assert first.description == "Нельзя кредитовать"


def test_unknown_top_level_field_ignored(load_mock: Callable[[str], Any]) -> None:
    payload = load_mock("customer-info/customer-info-v2.json")
    assert "unknownField" in payload  # the bank mock deliberately includes it
    CustomerInfo.model_validate(payload)  # must not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_models_customer.py -v`
Expected: FAIL with `ImportError` (no `alfabank.models.customer`)

- [ ] **Step 3: Implement `src/alfabank/models/customer.py`**

```python
"""Models for GET /jp/v2/customer-info."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import Field

from alfabank.enums import BlockType, CustomerCategory, CustomerStatus, SpecConditionCode
from alfabank.models.common import _AlfaBase


class OrganizationForm(_AlfaBase):
    """Организационно-правовая форма."""

    full_name: str | None = None
    short_name: str | None = None
    type: str | None = None
    code: str | None = None


class Address(_AlfaBase):
    """Адрес организации."""

    type: str | None = None
    area: str | None = None
    building: str | None = None
    city: str | None = None
    country: str | None = None
    flat: str | None = None
    full_address: str | None = None
    house: str | None = None
    region: str | None = None
    settlement: str | None = None
    settlement_type: str | None = None
    street: str | None = None
    zip: str | None = None
    fias_code: str | None = None


class SpecCondition(_AlfaBase):
    """Специальное условие (ограничение) по счёту."""

    code: SpecConditionCode | str | None = None
    description: str | None = None
    value: bool | None = None


class AccountBlockInfo(_AlfaBase):
    """Блокировка суммы на счёте."""

    num: str | None = None
    begin_date: date | None = None
    cause: str | None = None
    initiator: str | None = None
    sum: Decimal | None = None
    block_type: BlockType | str | None = None


class BankRef(_AlfaBase):
    """Реквизиты банка, в котором открыт счёт."""

    bic: str | None = None
    correspondent_account_number: str | None = None


class Account(_AlfaBase):
    """Счёт организации с балансами и ограничениями."""

    number: str | None = None
    type: str | None = None
    type_name: str | None = None
    open_date: date | None = None
    currency_code: str | None = None
    transit_account_number: str | None = None
    client_name: str | None = None
    amount_balance: Decimal | None = None
    amount_total: Decimal | None = None
    amount_holds: Decimal | None = None
    amount_overdraft_own_funds: Decimal | None = None
    amount_overdraft_limit: Decimal | None = None
    spec_conditions: list[SpecCondition] = Field(default_factory=list)
    blocked_sums: list[AccountBlockInfo] = Field(default_factory=list)
    bank: BankRef | None = None


class CustomerInfo(_AlfaBase):
    """Профиль организации (GET /jp/v2/customer-info)."""

    organization_id: str | None = None
    full_name: str | None = None
    short_name: str | None = None
    inn: str | None = None
    ogrn: str | None = None
    okpo: str | None = None
    okved: str | None = None
    type: str | None = None
    phone: str | None = None
    email: str | None = None
    kpps: list[str] = Field(default_factory=list)
    organization_form: OrganizationForm | None = None
    category: CustomerCategory | str | None = None
    status: CustomerStatus | str | None = None
    registration_date: datetime | None = None
    addresses: list[Address] = Field(default_factory=list)
    accounts: list[Account] = Field(default_factory=list)
```

Update `src/alfabank/models/__init__.py` — replace the whole file with:

```python
"""Public pydantic models for the Alfa API."""

from alfabank.models.common import Money
from alfabank.models.customer import (
    Account,
    AccountBlockInfo,
    Address,
    BankRef,
    CustomerInfo,
    OrganizationForm,
    SpecCondition,
)
from alfabank.models.statement import (
    CartInfo,
    CurTransfer,
    DepartmentalInfo,
    RurTransfer,
    StatementLink,
    StatementPage,
    StatementSummary,
    SwiftTransfer,
    Transaction,
)

__all__ = [
    "Account",
    "AccountBlockInfo",
    "Address",
    "BankRef",
    "CartInfo",
    "CurTransfer",
    "CustomerInfo",
    "DepartmentalInfo",
    "Money",
    "OrganizationForm",
    "RurTransfer",
    "SpecCondition",
    "StatementLink",
    "StatementPage",
    "StatementSummary",
    "SwiftTransfer",
    "Transaction",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_models_customer.py -v`
Expected: all PASS. Ruff + mypy clean.

- [ ] **Step 5: Commit**

```bash
git add src/alfabank/models tests/test_models_customer.py
git commit -m "feat: customer-info models validated against vendored bank mock"
```

---

### Task 8: Auth providers

**Files:**
- Create: `src/alfabank/auth.py`
- Test: `tests/test_auth.py`

**Interfaces:**
- Consumes: `AlfaBankConfigurationError` (Task 2)
- Produces: `TokenProvider` type alias `Callable[[], str | Awaitable[str]]`; `ApiKeyAuth(api_key: str)` → callable returning `"ApiKey {key}"`; `BearerAuth(access_token: str)` → callable returning `"Bearer {token}"`; `async resolve_authorization(provider: TokenProvider) -> str`.

- [ ] **Step 1: Write the failing tests**

`tests/test_auth.py`:

```python
"""Tests for authorization providers."""

from __future__ import annotations

import pytest

from alfabank.auth import ApiKeyAuth, BearerAuth, resolve_authorization
from alfabank.exceptions import AlfaBankConfigurationError


def test_api_key_auth_header_value() -> None:
    assert ApiKeyAuth("sample-api-key")() == "ApiKey sample-api-key"


def test_bearer_auth_header_value() -> None:
    assert BearerAuth("eyJtoken")() == "Bearer eyJtoken"


@pytest.mark.parametrize("bad", ["", None, 123])
def test_api_key_auth_rejects_bad_values(bad: object) -> None:
    with pytest.raises(AlfaBankConfigurationError):
        ApiKeyAuth(bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", ["", None, 123])
def test_bearer_auth_rejects_bad_values(bad: object) -> None:
    with pytest.raises(AlfaBankConfigurationError):
        BearerAuth(bad)  # type: ignore[arg-type]


async def test_resolve_sync_provider() -> None:
    assert await resolve_authorization(lambda: "ApiKey k") == "ApiKey k"
    assert await resolve_authorization(ApiKeyAuth("k")) == "ApiKey k"


async def test_resolve_async_provider() -> None:
    async def provider() -> str:
        return "Bearer t"

    assert await resolve_authorization(provider) == "Bearer t"


async def test_resolve_rejects_empty_or_non_string() -> None:
    with pytest.raises(AlfaBankConfigurationError):
        await resolve_authorization(lambda: "")
    with pytest.raises(AlfaBankConfigurationError):
        await resolve_authorization(lambda: 42)  # type: ignore[arg-type,return-value]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'alfabank.auth'`

- [ ] **Step 3: Implement `src/alfabank/auth.py`**

```python
"""Authorization providers for the Alfa API.

The bank accepts two schemes in the same ``Authorization`` header:
``Bearer <access_token>`` (OAuth2 / AlfaID) and ``ApiKey <key>`` (developer
portal). A provider is any zero-argument sync or async callable returning the
full header value; it is re-resolved before every request, which lets
callers rotate tokens without recreating the client.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable

from alfabank.exceptions import AlfaBankConfigurationError

TokenProvider = Callable[[], "str | Awaitable[str]"]


def _require_non_empty_str(value: str, name: str) -> str:
    if not value or not isinstance(value, str):
        raise AlfaBankConfigurationError(f"{name} must be a non-empty string")
    return value


class ApiKeyAuth:
    """Static ``Authorization: ApiKey <key>`` provider."""

    __slots__ = ("_api_key",)

    def __init__(self, api_key: str) -> None:
        self._api_key = _require_non_empty_str(api_key, "api_key")

    def __call__(self) -> str:
        return f"ApiKey {self._api_key}"


class BearerAuth:
    """Static ``Authorization: Bearer <token>`` provider."""

    __slots__ = ("_access_token",)

    def __init__(self, access_token: str) -> None:
        self._access_token = _require_non_empty_str(access_token, "access_token")

    def __call__(self) -> str:
        return f"Bearer {self._access_token}"


async def resolve_authorization(provider: TokenProvider) -> str:
    """Call the provider (awaiting if needed) and validate the header value."""
    value = provider()
    if inspect.isawaitable(value):
        value = await value
    if not isinstance(value, str) or not value:
        raise AlfaBankConfigurationError(
            "token_provider must return a non-empty Authorization header string"
        )
    return value
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_auth.py -v`
Expected: all PASS. Ruff + mypy clean.

- [ ] **Step 5: Commit**

```bash
git add src/alfabank/auth.py tests/test_auth.py
git commit -m "feat: ApiKey/Bearer auth providers with async token_provider seam"
```

---

### Task 9: RetryPolicy and Response wrapper

**Files:**
- Create: `src/alfabank/_transport.py` (RetryPolicy + Response; Transport added in Task 10)
- Test: `tests/test_retry_policy.py`

**Interfaces:**
- Consumes: nothing (httpx exception types only)
- Produces:
  - `RetryPolicy(max_retries: int = 3, retry_non_idempotent: bool = False, backoff_factor: float = 0.5, max_backoff: float = 30.0)` with `should_retry_status(*, method, status_code, idempotent=None) -> bool`, `should_retry_exception(*, method, exc, idempotent=None) -> bool`, `backoff_delay(attempt, *, retry_after=None) -> float`
  - `Response(status_code: int, headers: Mapping[str, str], content: bytes)` with `.headers` (lower-cased dict), `.text`, `.is_json`, `.json_body`, `.request_id` (from `x-traceid`).

- [ ] **Step 1: Write the failing tests**

`tests/test_retry_policy.py`:

```python
"""Unit tests for RetryPolicy decisions and the Response wrapper."""

from __future__ import annotations

import httpx
import pytest

from alfabank._transport import Response, RetryPolicy


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS", "PUT", "DELETE"])
def test_idempotent_methods_retry_5xx(method: str) -> None:
    policy = RetryPolicy()
    assert policy.should_retry_status(method=method, status_code=500) is True
    assert policy.should_retry_status(method=method, status_code=503) is True


def test_post_does_not_retry_5xx_by_default() -> None:
    policy = RetryPolicy()
    assert policy.should_retry_status(method="POST", status_code=500) is False


@pytest.mark.parametrize("status", [408, 425, 429])
def test_pre_handler_statuses_retry_even_for_post(status: int) -> None:
    # These statuses mean the server never processed the request body.
    assert RetryPolicy().should_retry_status(method="POST", status_code=status) is True


def test_retry_non_idempotent_opts_into_5xx_retry_for_post() -> None:
    policy = RetryPolicy(retry_non_idempotent=True)
    assert policy.should_retry_status(method="POST", status_code=500) is True


def test_per_call_idempotent_override() -> None:
    policy = RetryPolicy()
    assert policy.should_retry_status(method="GET", status_code=500, idempotent=False) is False
    assert policy.should_retry_status(method="POST", status_code=500, idempotent=True) is True


def test_success_and_client_errors_never_retry() -> None:
    policy = RetryPolicy()
    assert policy.should_retry_status(method="GET", status_code=200) is False
    assert policy.should_retry_status(method="GET", status_code=404) is False


def test_connect_errors_retry_for_any_method() -> None:
    policy = RetryPolicy()
    exc = httpx.ConnectError("boom")
    assert policy.should_retry_exception(method="POST", exc=exc) is True
    assert policy.should_retry_exception(method="GET", exc=exc) is True


def test_read_errors_retry_only_for_idempotent() -> None:
    policy = RetryPolicy()
    exc = httpx.ReadTimeout("slow")
    assert policy.should_retry_exception(method="GET", exc=exc) is True
    assert policy.should_retry_exception(method="POST", exc=exc) is False


def test_backoff_delay_grows_and_caps() -> None:
    policy = RetryPolicy(backoff_factor=0.5, max_backoff=30.0)
    d0 = policy.backoff_delay(0)
    assert 0.375 <= d0 <= 0.625  # 0.5 * 2**0, jitter +-25%
    d_big = policy.backoff_delay(20)
    assert d_big <= 30.0 * 1.25


def test_backoff_delay_honors_retry_after() -> None:
    policy = RetryPolicy(backoff_factor=0.0)
    assert policy.backoff_delay(0, retry_after=10.0) >= 10.0


def test_zero_backoff_factor_gives_zero_delay() -> None:
    assert RetryPolicy(backoff_factor=0.0).backoff_delay(0) == 0.0


def test_response_wrapper() -> None:
    resp = Response(
        status_code=200,
        headers={"Content-Type": "application/json", "X-TraceId": "a57610880b621435"},
        content=b'{"a": 1}',
    )
    assert resp.status_code == 200
    assert resp.is_json is True
    assert resp.json_body == {"a": 1}
    assert resp.request_id == "a57610880b621435"
    assert resp.text == '{"a": 1}'


def test_response_non_json_body() -> None:
    resp = Response(status_code=503, headers={}, content=b"")
    assert resp.is_json is False
    assert resp.json_body is None
    assert resp.request_id is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_retry_policy.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'alfabank._transport'`

- [ ] **Step 3: Implement RetryPolicy and Response in `src/alfabank/_transport.py`**

```python
"""Private transport layer: retry policy, response wrapper, httpx plumbing.

Retries are idempotency-aware: GET/HEAD/OPTIONS/PUT/DELETE retry on any
transient failure, while POST/PATCH retry only when the server provably never
processed the request (connect-phase network errors or pre-handler statuses
408/425/429). This prevents duplicate side effects for future payment
endpoints while keeping v1's GET-only surface fully retried.
"""

from __future__ import annotations

import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

_IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "PUT", "DELETE"})
_PRE_HANDLER_STATUSES = frozenset({408, 425, 429})


@dataclass(frozen=True)
class RetryPolicy:
    """Decides whether a failed request may be retried and with what delay."""

    max_retries: int = 3
    retry_non_idempotent: bool = False
    backoff_factor: float = 0.5
    max_backoff: float = 30.0

    def _effective_idempotent(self, method: str, idempotent: bool | None) -> bool:
        if idempotent is not None:
            return idempotent
        return method.upper() in _IDEMPOTENT_METHODS

    def should_retry_status(
        self, *, method: str, status_code: int, idempotent: bool | None = None
    ) -> bool:
        if status_code in _PRE_HANDLER_STATUSES:
            return True
        if status_code < 500:
            return False
        return self._effective_idempotent(method, idempotent) or self.retry_non_idempotent

    def should_retry_exception(
        self, *, method: str, exc: Exception, idempotent: bool | None = None
    ) -> bool:
        if isinstance(exc, httpx.ConnectError | httpx.ConnectTimeout):
            return True  # connect never happened -> safe for any method
        if isinstance(exc, httpx.TimeoutException | httpx.TransportError):
            return self._effective_idempotent(method, idempotent) or self.retry_non_idempotent
        return False

    def backoff_delay(self, attempt: int, *, retry_after: float | None = None) -> float:
        base = min(self.backoff_factor * (2**attempt), self.max_backoff)
        delay = base + base * random.uniform(-0.25, 0.25)  # jitter; not cryptographic
        if retry_after is not None:
            delay = max(delay, retry_after)
        return max(delay, 0.0)


class Response:
    """Minimal response wrapper so httpx types never leak past the transport."""

    __slots__ = ("_content", "headers", "status_code")

    def __init__(self, status_code: int, headers: Mapping[str, str], content: bytes) -> None:
        self.status_code = status_code
        self.headers: dict[str, str] = {k.lower(): v for k, v in headers.items()}
        self._content = content

    @property
    def text(self) -> str:
        return self._content.decode("utf-8", errors="replace")

    @property
    def is_json(self) -> bool:
        return "json" in self.headers.get("content-type", "")

    @property
    def json_body(self) -> Any:
        if not self._content:
            return None
        try:
            return json.loads(self._content)
        except ValueError:
            return None

    @property
    def request_id(self) -> str | None:
        return self.headers.get("x-traceid")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_retry_policy.py -v`
Expected: all PASS. Ruff + mypy clean.

- [ ] **Step 5: Commit**

```bash
git add src/alfabank/_transport.py tests/test_retry_policy.py
git commit -m "feat: idempotency-aware RetryPolicy and Response wrapper"
```

---

### Task 10: Transport

**Files:**
- Modify: `src/alfabank/_transport.py` (append Transport), `tests/conftest.py` (add `base_url`/`mock_api` fixtures)
- Test: `tests/test_transport.py`

**Interfaces:**
- Consumes: `RetryPolicy`, `Response` (Task 9); `resolve_authorization`, `TokenProvider` (Task 8); `AsyncRateLimiter` (Task 5); `raise_for_status`, `AlfaBankTransportError` (Task 2)
- Produces: `Transport(*, token_provider, base_url, api_prefix="/api", timeout=30.0, retry_policy=None, rate_limiter=None, user_agent="alfabank-sdk", cert=None, verify=True, client=None)` with `async request(method, path, *, params=None, json_body=None, headers=None, idempotent=None) -> Response` and `async aclose()`. Paths are joined as `{api_prefix}{path}`; `params` entries with `None`/`""` values are dropped.

- [ ] **Step 1: Extend `tests/conftest.py`**

Append to `tests/conftest.py`:

```python
from collections.abc import Iterator

import respx

TEST_BASE_URL = "https://baas.alfabank.ru"


@pytest.fixture
def base_url() -> str:
    return TEST_BASE_URL


@pytest.fixture
def mock_api(base_url: str) -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=base_url, assert_all_called=False) as router:
        yield router
```

(Move the imports up to the imports block; keep one imports section at the top of the file.)

- [ ] **Step 2: Write the failing tests**

`tests/test_transport.py`:

```python
"""Transport tests over respx-mocked httpx."""

from __future__ import annotations

import httpx
import pytest
import respx

from alfabank._transport import Response, RetryPolicy, Transport
from alfabank.auth import ApiKeyAuth
from alfabank.exceptions import (
    AlfaBankNotFoundError,
    AlfaBankServerError,
    AlfaBankTransportError,
)
from tests.conftest import TEST_BASE_URL


def make_transport(**overrides: object) -> Transport:
    kwargs: dict[str, object] = {
        "token_provider": ApiKeyAuth("test-key"),
        "base_url": TEST_BASE_URL,
        "api_prefix": "/api",
        "timeout": 5.0,
        "retry_policy": RetryPolicy(max_retries=0, backoff_factor=0.0),
        "rate_limiter": None,
        "user_agent": "test-agent",
    }
    kwargs.update(overrides)
    return Transport(**kwargs)  # type: ignore[arg-type]


async def test_request_sends_default_headers_and_prefix(mock_api: respx.MockRouter) -> None:
    route = mock_api.get("/api/statement/summary").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    transport = make_transport()
    try:
        resp = await transport.request(
            "GET",
            "/statement/summary",
            params={"accountNumber": "40702810000000000001", "page": None, "curFormat": ""},
        )
    finally:
        await transport.aclose()

    assert isinstance(resp, Response)
    assert resp.json_body == {"ok": True}
    request = route.calls.last.request
    assert request.headers["Authorization"] == "ApiKey test-key"
    assert request.headers["Accept"] == "application/json"
    assert request.headers["User-Agent"] == "test-agent"
    # None/empty params are dropped
    assert "page" not in str(request.url)
    assert "curFormat" not in str(request.url)
    assert request.url.params["accountNumber"] == "40702810000000000001"


async def test_error_maps_and_carries_traceid(mock_api: respx.MockRouter) -> None:
    mock_api.get("/api/missing").mock(
        return_value=httpx.Response(
            404,
            json={"error": "unknown_endpoint", "error_description": "Endpoint is not found"},
            headers={"x-traceid": "trace-42"},
        )
    )
    transport = make_transport()
    try:
        with pytest.raises(AlfaBankNotFoundError) as exc_info:
            await transport.request("GET", "/missing")
    finally:
        await transport.aclose()
    assert exc_info.value.request_id == "trace-42"
    assert exc_info.value.error_code == "unknown_endpoint"


async def test_get_retries_5xx_then_succeeds(mock_api: respx.MockRouter) -> None:
    route = mock_api.get("/api/flaky").mock(
        side_effect=[
            httpx.Response(500, json={"error": "internal_error"}),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    transport = make_transport(retry_policy=RetryPolicy(max_retries=2, backoff_factor=0.0))
    try:
        resp = await transport.request("GET", "/flaky")
    finally:
        await transport.aclose()
    assert resp.json_body == {"ok": True}
    assert route.call_count == 2


async def test_get_raises_after_retries_exhausted(mock_api: respx.MockRouter) -> None:
    route = mock_api.get("/api/broken").mock(return_value=httpx.Response(500))
    transport = make_transport(retry_policy=RetryPolicy(max_retries=1, backoff_factor=0.0))
    try:
        with pytest.raises(AlfaBankServerError):
            await transport.request("GET", "/broken")
    finally:
        await transport.aclose()
    assert route.call_count == 2  # initial + 1 retry


async def test_post_5xx_not_retried(mock_api: respx.MockRouter) -> None:
    route = mock_api.post("/api/pay").mock(return_value=httpx.Response(500))
    transport = make_transport(retry_policy=RetryPolicy(max_retries=3, backoff_factor=0.0))
    try:
        with pytest.raises(AlfaBankServerError):
            await transport.request("POST", "/pay", json_body={"x": 1})
    finally:
        await transport.aclose()
    assert route.call_count == 1


async def test_post_connect_error_is_retried(mock_api: respx.MockRouter) -> None:
    route = mock_api.post("/api/pay").mock(
        side_effect=[httpx.ConnectError("refused"), httpx.Response(200, json={"ok": True})]
    )
    transport = make_transport(retry_policy=RetryPolicy(max_retries=1, backoff_factor=0.0))
    try:
        resp = await transport.request("POST", "/pay", json_body={"x": 1})
    finally:
        await transport.aclose()
    assert resp.json_body == {"ok": True}
    assert route.call_count == 2


async def test_timeout_wrapped_in_transport_error(mock_api: respx.MockRouter) -> None:
    mock_api.get("/api/slow").mock(side_effect=httpx.ReadTimeout("timeout"))
    transport = make_transport()
    try:
        with pytest.raises(AlfaBankTransportError):
            await transport.request("GET", "/slow")
    finally:
        await transport.aclose()


async def test_injected_client_is_not_closed(mock_api: respx.MockRouter) -> None:
    mock_api.get("/api/ping").mock(return_value=httpx.Response(200, json={}))
    external = httpx.AsyncClient(base_url=TEST_BASE_URL)
    transport = make_transport(client=external)
    await transport.request("GET", "/ping")
    await transport.aclose()
    assert external.is_closed is False
    await external.aclose()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_transport.py -v`
Expected: FAIL with `ImportError: cannot import name 'Transport'`

- [ ] **Step 4: Append Transport to `src/alfabank/_transport.py`**

Add to the imports at the top of the file:

```python
import asyncio
import logging

from alfabank._utils import AsyncRateLimiter
from alfabank.auth import TokenProvider, resolve_authorization
from alfabank.exceptions import AlfaBankTransportError, raise_for_status
```

Append after `Response`:

```python
_LOGGER = logging.getLogger("alfabank")


def _clean_params(params: Mapping[str, Any] | None) -> dict[str, str] | None:
    """Drop None/empty values (mirrors the bank's reference client) and stringify."""
    if not params:
        return None
    cleaned = {k: str(v) for k, v in params.items() if v is not None and v != ""}
    return cleaned or None


class Transport:
    """Owns the httpx client and all cross-cutting request concerns."""

    def __init__(
        self,
        *,
        token_provider: TokenProvider,
        base_url: str,
        api_prefix: str = "/api",
        timeout: float | httpx.Timeout = 30.0,
        retry_policy: RetryPolicy | None = None,
        rate_limiter: AsyncRateLimiter | None = None,
        user_agent: str = "alfabank-sdk",
        cert: Any = None,
        verify: Any = True,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._token_provider = token_provider
        self._api_prefix = "/" + api_prefix.strip("/") if api_prefix.strip("/") else ""
        self._retry_policy = retry_policy or RetryPolicy()
        self._rate_limiter = rate_limiter
        self._user_agent = user_agent
        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            self._client = httpx.AsyncClient(
                base_url=base_url.rstrip("/"), timeout=timeout, cert=cert, verify=verify
            )
            self._owns_client = True

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any = None,
        headers: Mapping[str, str] | None = None,
        idempotent: bool | None = None,
    ) -> Response:
        """Perform a request, retrying transient failures per the retry policy.

        Raises the mapped :class:`AlfaBankAPIError` subclass on HTTP errors and
        :class:`AlfaBankTransportError` on network failures.
        """
        url = self._api_prefix + (path if path.startswith("/") else "/" + path)
        clean = _clean_params(params)
        policy = self._retry_policy
        attempt = 0
        while True:
            if self._rate_limiter is not None:
                await self._rate_limiter.acquire()
            request_headers = {
                "Authorization": await resolve_authorization(self._token_provider),
                "Accept": "application/json",
                "User-Agent": self._user_agent,
            }
            if headers:
                request_headers.update(headers)
            try:
                raw = await self._client.request(
                    method, url, params=clean, json=json_body, headers=request_headers
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt < policy.max_retries and policy.should_retry_exception(
                    method=method, exc=exc, idempotent=idempotent
                ):
                    delay = policy.backoff_delay(attempt)
                    _LOGGER.debug(
                        "Retrying %s %s after %s (attempt %d, sleep %.2fs)",
                        method, url, type(exc).__name__, attempt + 1, delay,
                    )
                    await asyncio.sleep(delay)
                    attempt += 1
                    continue
                raise AlfaBankTransportError(f"{method} {url} failed: {exc}") from exc

            response = Response(
                status_code=raw.status_code, headers=raw.headers, content=raw.content
            )
            if 200 <= response.status_code < 400:
                return response

            if attempt < policy.max_retries and policy.should_retry_status(
                method=method, status_code=response.status_code, idempotent=idempotent
            ):
                retry_after_raw = response.headers.get("retry-after")
                try:
                    retry_after = float(retry_after_raw) if retry_after_raw else None
                except ValueError:
                    retry_after = None
                delay = policy.backoff_delay(attempt, retry_after=retry_after)
                _LOGGER.debug(
                    "Retrying %s %s after HTTP %d (attempt %d, sleep %.2fs)",
                    method, url, response.status_code, attempt + 1, delay,
                )
                await asyncio.sleep(delay)
                attempt += 1
                continue

            raise_for_status(
                status_code=response.status_code,
                response_body=response.json_body if response.is_json else (response.text or None),
                request_id=response.request_id,
                headers=response.headers,
            )
            raise AssertionError("unreachable")  # raise_for_status always raises here

    async def aclose(self) -> None:
        if self._owns_client and not self._client.is_closed:
            await self._client.aclose()
```

Note: `Response(...)` accepts `raw.headers` (httpx Headers is a Mapping) — no conversion needed.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_transport.py tests/test_retry_policy.py -v`
Expected: all PASS. Ruff + mypy clean.

- [ ] **Step 6: Commit**

```bash
git add src/alfabank/_transport.py tests/conftest.py tests/test_transport.py
git commit -m "feat: async Transport with retries, rate limiting and error mapping"
```

---

### Task 11: Statements resource

**Files:**
- Create: `src/alfabank/resources/__init__.py`, `src/alfabank/resources/_base.py`, `src/alfabank/resources/statements.py`
- Test: `tests/test_statements_resource.py`

**Interfaces:**
- Consumes: `Transport` (Task 10), `StatementPage`/`StatementSummary`/`Transaction` (Task 6), `CurFormat` (Task 3), `AlfaBankValidationError` (Task 2)
- Produces: `Resource(transport)` base; `StatementsResource` with:
  - `async transactions(account_number: str, statement_date: date | str, *, page: int = 1, cur_format: CurFormat | str | None = None) -> StatementPage` → `GET {prefix}/statement/transactions`
  - `async iter_transactions(account_number, statement_date, *, cur_format=None, start_page: int = 1) -> AsyncIterator[Transaction]`
  - `async summary(account_number: str, statement_date: date | str) -> StatementSummary` → `GET {prefix}/statement/summary`

- [ ] **Step 1: Write the failing tests**

`tests/test_statements_resource.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_statements_resource.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'alfabank.resources'`

- [ ] **Step 3: Implement**

`src/alfabank/resources/_base.py`:

```python
"""Base class for API resources."""

from __future__ import annotations

from alfabank._transport import Transport


class Resource:
    """Holds the shared transport; concrete resources add endpoint methods."""

    __slots__ = ("_transport",)

    def __init__(self, transport: Transport) -> None:
        self._transport = transport
```

`src/alfabank/resources/statements.py`:

```python
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
```

`src/alfabank/resources/__init__.py`:

```python
"""API resource classes."""

from alfabank.resources.statements import StatementsResource

__all__ = ["StatementsResource"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_statements_resource.py -v`
Expected: all PASS. Ruff + mypy clean.

- [ ] **Step 5: Commit**

```bash
git add src/alfabank/resources tests/test_statements_resource.py
git commit -m "feat: statements resource with validation and auto-pagination"
```

---

### Task 12: Customer resource

**Files:**
- Create: `src/alfabank/resources/customer.py`
- Modify: `src/alfabank/resources/__init__.py`
- Test: `tests/test_customer_resource.py`

**Interfaces:**
- Consumes: `Resource` (Task 11), `Transport` (Task 10), `CustomerInfo` (Task 7)
- Produces: `CustomerResource` with `async info() -> CustomerInfo` → `GET {prefix}/jp/v2/customer-info`.

- [ ] **Step 1: Write the failing tests**

`tests/test_customer_resource.py`:

```python
"""CustomerResource tests over respx with the bank's own mock."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest
import respx

from alfabank._transport import RetryPolicy, Transport
from alfabank.auth import ApiKeyAuth
from alfabank.models.customer import CustomerInfo
from alfabank.resources.customer import CustomerResource
from tests.conftest import TEST_BASE_URL


@pytest.fixture
async def customer() -> AsyncIterator[CustomerResource]:
    transport = Transport(
        token_provider=ApiKeyAuth("test-key"),
        base_url=TEST_BASE_URL,
        retry_policy=RetryPolicy(max_retries=0, backoff_factor=0.0),
    )
    try:
        yield CustomerResource(transport)
    finally:
        await transport.aclose()


async def test_info_hits_versioned_path_and_parses(
    customer: CustomerResource,
    mock_api: respx.MockRouter,
    load_mock: Callable[[str], Any],
) -> None:
    route = mock_api.get("/api/jp/v2/customer-info").mock(
        return_value=httpx.Response(
            200, json=load_mock("customer-info/customer-info-v2.json")
        )
    )
    info = await customer.info()
    assert isinstance(info, CustomerInfo)
    assert info.inn == "0000000000"
    assert len(info.accounts) == 1
    assert route.call_count == 1
    assert route.calls.last.request.url.path == "/api/jp/v2/customer-info"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_customer_resource.py -v`
Expected: FAIL with `ModuleNotFoundError` (no `alfabank.resources.customer`)

- [ ] **Step 3: Implement**

`src/alfabank/resources/customer.py`:

```python
"""Customer resource: organization profile with accounts and balances."""

from __future__ import annotations

from alfabank.models.customer import CustomerInfo
from alfabank.resources._base import Resource


class CustomerResource(Resource):
    """Информация об организации."""

    # ---- GET /jp/v2/customer-info ----
    async def info(self) -> CustomerInfo:
        """Профиль организации: реквизиты, адреса, счета с балансами."""
        response = await self._transport.request("GET", "/jp/v2/customer-info")
        return CustomerInfo.model_validate(response.json_body)
```

Update `src/alfabank/resources/__init__.py`:

```python
"""API resource classes."""

from alfabank.resources.customer import CustomerResource
from alfabank.resources.statements import StatementsResource

__all__ = ["CustomerResource", "StatementsResource"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_customer_resource.py -v`
Expected: all PASS. Ruff + mypy clean.

- [ ] **Step 5: Commit**

```bash
git add src/alfabank/resources tests/test_customer_resource.py
git commit -m "feat: customer-info resource"
```

---

### Task 13: Client facade

**Files:**
- Create: `src/alfabank/client.py`
- Modify: `tests/conftest.py` (add `client` fixture)
- Test: `tests/test_client.py`

**Interfaces:**
- Consumes: `Transport`, `RetryPolicy` (Tasks 9-10); `ApiKeyAuth`, `BearerAuth`, `TokenProvider` (Task 8); `StatementsResource`, `CustomerResource` (Tasks 11-12); `AsyncRateLimiter` (Task 5); `AlfaBankConfigurationError` (Task 2)
- Produces:
  - `PRODUCTION_BASE_URL = "https://baas.alfabank.ru"`, `SANDBOX_BASE_URL = "https://sandbox.alfabank.ru"`, `DEFAULT_TIMEOUT = 30.0`, `DEFAULT_USER_AGENT`
  - `AlfaBankClient(*, api_key=None, access_token=None, token_provider=None, base_url=PRODUCTION_BASE_URL, api_prefix="/api", timeout=DEFAULT_TIMEOUT, max_retries=3, retry_non_idempotent=False, rate_limit=None, user_agent=DEFAULT_USER_AGENT, cert=None, verify=True, http_client=None)` with attributes `statements`, `customer`; `async request(method, path, **kwargs) -> Any`; `__aenter__`/`__aexit__`/`aclose()`.

- [ ] **Step 1: Write the failing tests**

`tests/test_client.py`:

```python
"""AlfaBankClient facade tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest
import respx

from alfabank.client import (
    PRODUCTION_BASE_URL,
    SANDBOX_BASE_URL,
    AlfaBankClient,
)
from alfabank.exceptions import AlfaBankConfigurationError
from alfabank.models.customer import CustomerInfo


def test_url_constants() -> None:
    assert PRODUCTION_BASE_URL == "https://baas.alfabank.ru"
    assert SANDBOX_BASE_URL == "https://sandbox.alfabank.ru"


def test_requires_exactly_one_auth_method() -> None:
    with pytest.raises(AlfaBankConfigurationError):
        AlfaBankClient()
    with pytest.raises(AlfaBankConfigurationError):
        AlfaBankClient(api_key="k", access_token="t")
    with pytest.raises(AlfaBankConfigurationError):
        AlfaBankClient(api_key="k", token_provider=lambda: "Bearer x")


def test_rejects_empty_credentials() -> None:
    with pytest.raises(AlfaBankConfigurationError):
        AlfaBankClient(api_key="")
    with pytest.raises(AlfaBankConfigurationError):
        AlfaBankClient(access_token="")


async def test_api_key_auth_end_to_end(
    mock_api: respx.MockRouter, load_mock: Callable[[str], Any]
) -> None:
    route = mock_api.get("/api/jp/v2/customer-info").mock(
        return_value=httpx.Response(
            200, json=load_mock("customer-info/customer-info-v2.json")
        )
    )
    async with AlfaBankClient(api_key="sample-api-key", rate_limit=None, max_retries=0) as client:
        info = await client.customer.info()
    assert isinstance(info, CustomerInfo)
    assert route.calls.last.request.headers["Authorization"] == "ApiKey sample-api-key"


async def test_access_token_auth_end_to_end(mock_api: respx.MockRouter) -> None:
    route = mock_api.get("/api/jp/v2/customer-info").mock(
        return_value=httpx.Response(200, json={})
    )
    async with AlfaBankClient(access_token="eyJtoken", max_retries=0) as client:
        await client.customer.info()
    assert route.calls.last.request.headers["Authorization"] == "Bearer eyJtoken"


async def test_async_token_provider_used(mock_api: respx.MockRouter) -> None:
    route = mock_api.get("/api/jp/v2/customer-info").mock(
        return_value=httpx.Response(200, json={})
    )

    async def provider() -> str:
        return "Bearer from-provider"

    async with AlfaBankClient(token_provider=provider, max_retries=0) as client:
        await client.customer.info()
    assert route.calls.last.request.headers["Authorization"] == "Bearer from-provider"


async def test_api_prefix_override(mock_api: respx.MockRouter) -> None:
    route = mock_api.get("/api/jp/v1/statement/summary").mock(
        return_value=httpx.Response(200, json={})
    )
    async with AlfaBankClient(api_key="k", api_prefix="/api/jp/v1", max_retries=0) as client:
        await client.statements.summary("40702810102300000001", "2023-01-30")
    assert route.call_count == 1


async def test_raw_request_escape_hatch(mock_api: respx.MockRouter) -> None:
    mock_api.get("/api/some/unwrapped").mock(
        return_value=httpx.Response(200, json={"raw": True})
    )
    async with AlfaBankClient(api_key="k", max_retries=0) as client:
        body = await client.request("GET", "/some/unwrapped")
    assert body == {"raw": True}


async def test_aclose_is_idempotent() -> None:
    client = AlfaBankClient(api_key="k")
    await client.aclose()
    await client.aclose()  # second close must not raise


async def test_injected_http_client_not_closed(mock_api: respx.MockRouter) -> None:
    mock_api.get("/api/jp/v2/customer-info").mock(return_value=httpx.Response(200, json={}))
    external = httpx.AsyncClient(base_url=PRODUCTION_BASE_URL)
    async with AlfaBankClient(api_key="k", http_client=external, max_retries=0) as client:
        await client.customer.info()
    assert external.is_closed is False
    await external.aclose()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'alfabank.client'`

- [ ] **Step 3: Implement `src/alfabank/client.py`**

```python
"""AlfaBankClient: the public facade of alfabank-sdk.

Example:
    async with AlfaBankClient(api_key="...") as client:
        async for tx in client.statements.iter_transactions(
            "40702810102300000001", date(2026, 7, 1)
        ):
            print(tx.payment_purpose, tx.amount)
"""

from __future__ import annotations

from types import TracebackType
from typing import Any

import httpx

from alfabank._transport import RetryPolicy, Transport
from alfabank._utils import AsyncRateLimiter
from alfabank.auth import ApiKeyAuth, BearerAuth, TokenProvider
from alfabank.exceptions import AlfaBankConfigurationError
from alfabank.resources.customer import CustomerResource
from alfabank.resources.statements import StatementsResource

try:
    from alfabank._version import __version__ as _sdk_version
except ImportError:  # pragma: no cover - version file is generated at build time
    _sdk_version = "0.0.0+unknown"

PRODUCTION_BASE_URL = "https://baas.alfabank.ru"
SANDBOX_BASE_URL = "https://sandbox.alfabank.ru"
DEFAULT_TIMEOUT = 30.0
DEFAULT_USER_AGENT = f"alfabank-sdk/{_sdk_version}"


class AlfaBankClient:
    """Async client for the Alfa-Bank Alfa API (h2h).

    Exactly one of ``api_key``, ``access_token`` or ``token_provider`` is
    required. ``base_url``/``api_prefix`` default to production values that
    are configurable because the bank's gateway paths differ per contract
    (see the design spec's assumptions section).
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        access_token: str | None = None,
        token_provider: TokenProvider | None = None,
        base_url: str = PRODUCTION_BASE_URL,
        api_prefix: str = "/api",
        timeout: float | httpx.Timeout = DEFAULT_TIMEOUT,
        max_retries: int = 3,
        retry_non_idempotent: bool = False,
        rate_limit: int | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
        cert: Any = None,
        verify: Any = True,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        provided = [v for v in (api_key, access_token, token_provider) if v is not None]
        if len(provided) != 1:
            raise AlfaBankConfigurationError(
                "Provide exactly one of api_key, access_token or token_provider"
            )
        if not base_url or not isinstance(base_url, str):
            raise AlfaBankConfigurationError("base_url must be a non-empty string")

        provider: TokenProvider
        if api_key is not None:
            provider = ApiKeyAuth(api_key)
        elif access_token is not None:
            provider = BearerAuth(access_token)
        else:
            assert token_provider is not None
            provider = token_provider

        self._closed = False
        self._transport = Transport(
            token_provider=provider,
            base_url=base_url,
            api_prefix=api_prefix,
            timeout=timeout,
            retry_policy=RetryPolicy(
                max_retries=max_retries, retry_non_idempotent=retry_non_idempotent
            ),
            rate_limiter=AsyncRateLimiter(rate_limit) if rate_limit else None,
            user_agent=user_agent,
            cert=cert,
            verify=verify,
            client=http_client,
        )
        self.statements = StatementsResource(self._transport)
        self.customer = CustomerResource(self._transport)

    async def request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Escape hatch: raw request to any endpoint, returns decoded JSON."""
        response = await self._transport.request(method, path, **kwargs)
        return response.json_body

    async def aclose(self) -> None:
        if not self._closed:
            self._closed = True
            await self._transport.aclose()

    async def __aenter__(self) -> AlfaBankClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()
```

- [ ] **Step 4: Add the shared client fixture**

Append to `tests/conftest.py`:

```python
from collections.abc import AsyncIterator

from alfabank.client import AlfaBankClient


@pytest.fixture
async def client() -> AsyncIterator[AlfaBankClient]:
    instance = AlfaBankClient(api_key="test-key", rate_limit=None, max_retries=0)
    try:
        yield instance
    finally:
        await instance.aclose()
```

(Move imports to the top imports block. The import is `from alfabank.client import ...` for now — the top-level re-export appears only in Task 15, which flips this line to `from alfabank import AlfaBankClient`.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_client.py -v`
Expected: all PASS. Then the full suite: `.venv/Scripts/python -m pytest -q` — all PASS. Ruff + mypy clean.

- [ ] **Step 6: Commit**

```bash
git add src/alfabank/client.py tests/conftest.py tests/test_client.py
git commit -m "feat: AlfaBankClient facade with dual auth and resource wiring"
```

---

### Task 14: OAuth helper (experimental)

**Files:**
- Create: `src/alfabank/oauth.py`
- Test: `tests/test_oauth.py`

**Interfaces:**
- Consumes: `raise_for_status`, `AlfaBankTransportError` (Task 2); `AlfaBankClient` (Task 13, integration test only)
- Produces: `PRODUCTION_TOKEN_URL`, `SANDBOX_TOKEN_URL`; `TokenPair` (pydantic: `access_token`, `token_type`, `expires_in`, `refresh_token`, `scope`); `async exchange_authorization_code(*, client_id, client_secret, code, redirect_uri, token_url=PRODUCTION_TOKEN_URL, http_client=None) -> TokenPair`; `async refresh_access_token(*, client_id, client_secret, refresh_token, token_url=PRODUCTION_TOKEN_URL, http_client=None) -> TokenPair`; `OAuthTokenProvider(*, client_id, client_secret, refresh_token, token_url=PRODUCTION_TOKEN_URL, leeway=60.0, http_client=None)` — async callable usable as `token_provider=`.

- [ ] **Step 1: Write the failing tests**

`tests/test_oauth.py`:

```python
"""Tests for the experimental OAuth helper (respx-mocked /oidc/token)."""

from __future__ import annotations

from urllib.parse import parse_qs

import httpx
import pytest
import respx

from alfabank.client import AlfaBankClient
from alfabank.exceptions import AlfaBankAPIError
from alfabank.oauth import (
    PRODUCTION_TOKEN_URL,
    SANDBOX_TOKEN_URL,
    OAuthTokenProvider,
    TokenPair,
    exchange_authorization_code,
    refresh_access_token,
)

TOKEN_RESPONSE = {
    "access_token": "t1",
    "token_type": "Bearer",
    "expires_in": 3600,
    "refresh_token": "rt2",
    "scope": "statements",
}


def test_token_url_constants() -> None:
    assert PRODUCTION_TOKEN_URL == "https://baas.alfabank.ru/oidc/token"
    assert SANDBOX_TOKEN_URL == "https://sandbox.alfabank.ru/oidc/token"


@respx.mock
async def test_exchange_authorization_code_posts_form() -> None:
    route = respx.post(PRODUCTION_TOKEN_URL).mock(
        return_value=httpx.Response(200, json=TOKEN_RESPONSE)
    )
    pair = await exchange_authorization_code(
        client_id="cid",
        client_secret="secret",
        code="auth-code",
        redirect_uri="https://example.com/cb",
    )
    assert isinstance(pair, TokenPair)
    assert pair.access_token == "t1"
    assert pair.refresh_token == "rt2"
    form = parse_qs(route.calls.last.request.content.decode())
    assert form["grant_type"] == ["authorization_code"]
    assert form["code"] == ["auth-code"]
    assert form["redirect_uri"] == ["https://example.com/cb"]
    assert form["client_id"] == ["cid"]
    assert form["client_secret"] == ["secret"]


@respx.mock
async def test_refresh_access_token_posts_form() -> None:
    route = respx.post(SANDBOX_TOKEN_URL).mock(
        return_value=httpx.Response(200, json=TOKEN_RESPONSE)
    )
    pair = await refresh_access_token(
        client_id="cid",
        client_secret="secret",
        refresh_token="rt1",
        token_url=SANDBOX_TOKEN_URL,
    )
    assert pair.access_token == "t1"
    form = parse_qs(route.calls.last.request.content.decode())
    assert form["grant_type"] == ["refresh_token"]
    assert form["refresh_token"] == ["rt1"]


@respx.mock
async def test_token_endpoint_error_is_mapped() -> None:
    respx.post(PRODUCTION_TOKEN_URL).mock(
        return_value=httpx.Response(
            400, json={"error": "invalid_grant", "error_description": "code expired"}
        )
    )
    with pytest.raises(AlfaBankAPIError) as exc_info:
        await refresh_access_token(client_id="c", client_secret="s", refresh_token="rt")
    assert exc_info.value.error_code == "invalid_grant"


@respx.mock
async def test_provider_caches_until_expiry() -> None:
    route = respx.post(PRODUCTION_TOKEN_URL).mock(
        return_value=httpx.Response(200, json=TOKEN_RESPONSE)
    )
    provider = OAuthTokenProvider(
        client_id="cid", client_secret="secret", refresh_token="rt1"
    )
    assert await provider() == "Bearer t1"
    assert await provider() == "Bearer t1"
    assert route.call_count == 1  # second call served from cache


@respx.mock
async def test_provider_refreshes_expired_token_and_rotates_refresh_token() -> None:
    route = respx.post(PRODUCTION_TOKEN_URL).mock(
        side_effect=[
            httpx.Response(
                200,
                json={"access_token": "t1", "expires_in": 1, "refresh_token": "rt2"},
            ),
            httpx.Response(
                200,
                json={"access_token": "t2", "expires_in": 3600, "refresh_token": "rt3"},
            ),
        ]
    )
    # leeway larger than expires_in -> token is treated as expired immediately
    provider = OAuthTokenProvider(
        client_id="cid", client_secret="secret", refresh_token="rt1", leeway=10.0
    )
    assert await provider() == "Bearer t1"
    assert await provider() == "Bearer t2"
    assert route.call_count == 2
    # the second request must use the rotated refresh token from the first response
    second_form = parse_qs(route.calls[1].request.content.decode())
    assert second_form["refresh_token"] == ["rt2"]


async def test_provider_plugs_into_client(mock_api: respx.MockRouter) -> None:
    mock_api.post("/oidc/token").mock(return_value=httpx.Response(200, json=TOKEN_RESPONSE))
    api_route = mock_api.get("/api/jp/v2/customer-info").mock(
        return_value=httpx.Response(200, json={})
    )
    provider = OAuthTokenProvider(
        client_id="cid", client_secret="secret", refresh_token="rt1"
    )
    async with AlfaBankClient(token_provider=provider, max_retries=0) as client:
        await client.customer.info()
    assert api_route.calls.last.request.headers["Authorization"] == "Bearer t1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_oauth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'alfabank.oauth'`

- [ ] **Step 3: Implement `src/alfabank/oauth.py`**

```python
"""EXPERIMENTAL: OAuth2 helpers for AlfaID token acquisition and refresh.

The ``/oidc/token`` contract is documented indirectly (the endpoint URLs come
from official FAQ snippets) and has NOT been verified against a live sandbox.
Known lifetimes: authorization code ~120s, refresh_token ~180 days.

The rest of the SDK does not depend on this module: ``OAuthTokenProvider`` is
just one possible ``token_provider`` for :class:`alfabank.AlfaBankClient`.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict

from alfabank.exceptions import AlfaBankTransportError, raise_for_status

PRODUCTION_TOKEN_URL = "https://baas.alfabank.ru/oidc/token"
SANDBOX_TOKEN_URL = "https://sandbox.alfabank.ru/oidc/token"


class TokenPair(BaseModel):
    """Response of the OAuth token endpoint (snake_case per RFC 6749)."""

    model_config = ConfigDict(extra="ignore")

    access_token: str
    token_type: str | None = None
    expires_in: int | None = None
    refresh_token: str | None = None
    scope: str | None = None


async def _request_token(
    data: dict[str, str], *, token_url: str, http_client: httpx.AsyncClient | None = None
) -> TokenPair:
    owns_client = http_client is None
    client = http_client or httpx.AsyncClient()
    try:
        try:
            response = await client.post(
                token_url, data=data, headers={"Accept": "application/json"}
            )
        except httpx.HTTPError as exc:
            raise AlfaBankTransportError(f"POST {token_url} failed: {exc}") from exc
        body: Any
        try:
            body = response.json()
        except ValueError:
            body = response.text or None
        raise_for_status(
            status_code=response.status_code,
            response_body=body,
            request_id=response.headers.get("x-traceid"),
            headers=response.headers,
        )
        return TokenPair.model_validate(body)
    finally:
        if owns_client:
            await client.aclose()


async def exchange_authorization_code(
    *,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    token_url: str = PRODUCTION_TOKEN_URL,
    http_client: httpx.AsyncClient | None = None,
) -> TokenPair:
    """Exchange an authorization code (TTL ~120s) for access+refresh tokens."""
    return await _request_token(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        token_url=token_url,
        http_client=http_client,
    )


async def refresh_access_token(
    *,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    token_url: str = PRODUCTION_TOKEN_URL,
    http_client: httpx.AsyncClient | None = None,
) -> TokenPair:
    """Obtain a fresh access token using a refresh token (TTL ~180 days)."""
    return await _request_token(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        token_url=token_url,
        http_client=http_client,
    )


class OAuthTokenProvider:
    """Caching token provider: refreshes the access token when it expires.

    Plug into ``AlfaBankClient(token_provider=...)``. Refresh-token rotation
    is handled: if the endpoint returns a new refresh_token, it replaces the
    stored one for subsequent refreshes.
    """

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        token_url: str = PRODUCTION_TOKEN_URL,
        leeway: float = 60.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._token_url = token_url
        self._leeway = leeway
        self._http_client = http_client
        self._access_token: str | None = None
        self._expires_at: float | None = None
        self._lock = asyncio.Lock()

    def _is_expired(self) -> bool:
        if self._access_token is None:
            return True
        if self._expires_at is None:
            return False  # no expires_in reported -> assume long-lived
        return time.monotonic() >= self._expires_at

    async def __call__(self) -> str:
        async with self._lock:
            if self._is_expired():
                pair = await refresh_access_token(
                    client_id=self._client_id,
                    client_secret=self._client_secret,
                    refresh_token=self._refresh_token,
                    token_url=self._token_url,
                    http_client=self._http_client,
                )
                self._access_token = pair.access_token
                if pair.refresh_token:
                    self._refresh_token = pair.refresh_token
                self._expires_at = (
                    time.monotonic() + pair.expires_in - self._leeway
                    if pair.expires_in is not None
                    else None
                )
            assert self._access_token is not None
            return f"Bearer {self._access_token}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_oauth.py -v`
Expected: all PASS. Ruff + mypy clean.

- [ ] **Step 5: Commit**

```bash
git add src/alfabank/oauth.py tests/test_oauth.py
git commit -m "feat: experimental OAuth helper with caching token provider"
```

---

### Task 15: Public API, README, examples, CHANGELOG

**Files:**
- Modify: `src/alfabank/__init__.py`, `tests/conftest.py` (flip client import), `README.md`
- Create: `examples/basic_usage.py`, `examples/fastapi_integration.py`, `CHANGELOG.md`
- Test: `tests/test_public_api.py`

**Interfaces:**
- Consumes: everything from Tasks 2-14
- Produces: flat public API `from alfabank import AlfaBankClient, Money, Transaction, ...` with explicit `__all__`.

- [ ] **Step 1: Write the failing test**

`tests/test_public_api.py`:

```python
"""The public API surface: everything importable from the top-level package."""

from __future__ import annotations

import alfabank


def test_public_api_surface() -> None:
    expected = {
        # client
        "AlfaBankClient",
        "PRODUCTION_BASE_URL",
        "SANDBOX_BASE_URL",
        # auth
        "ApiKeyAuth",
        "BearerAuth",
        # enums
        "BlockType",
        "CurFormat",
        "CustomerCategory",
        "CustomerStatus",
        "Direction",
        "OperationCode",
        "SpecConditionCode",
        # models
        "Account",
        "AccountBlockInfo",
        "Address",
        "BankRef",
        "CartInfo",
        "CurTransfer",
        "CustomerInfo",
        "DepartmentalInfo",
        "Money",
        "OrganizationForm",
        "RurTransfer",
        "SpecCondition",
        "StatementLink",
        "StatementPage",
        "StatementSummary",
        "SwiftTransfer",
        "Transaction",
        # exceptions
        "AlfaBankAPIError",
        "AlfaBankAuthenticationError",
        "AlfaBankConfigurationError",
        "AlfaBankConflictError",
        "AlfaBankError",
        "AlfaBankNotFoundError",
        "AlfaBankPermissionError",
        "AlfaBankRateLimitError",
        "AlfaBankServerError",
        "AlfaBankTransportError",
        "AlfaBankValidationError",
        # version
        "__version__",
    }
    assert expected <= set(alfabank.__all__)
    for name in expected:
        assert getattr(alfabank, name) is not None


def test_all_is_sorted() -> None:
    assert list(alfabank.__all__) == sorted(alfabank.__all__)


def test_oauth_is_a_submodule() -> None:
    from alfabank import oauth

    assert hasattr(oauth, "OAuthTokenProvider")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_public_api.py -v`
Expected: FAIL (`__all__` only contains `__version__`)

- [ ] **Step 3: Rewrite `src/alfabank/__init__.py`**

```python
"""alfabank-sdk: async Python SDK for the Alfa-Bank Alfa API (h2h).

Quickstart:
    from alfabank import AlfaBankClient

    async with AlfaBankClient(api_key="...") as client:
        info = await client.customer.info()
"""

from __future__ import annotations

from alfabank.auth import ApiKeyAuth, BearerAuth
from alfabank.client import (
    PRODUCTION_BASE_URL,
    SANDBOX_BASE_URL,
    AlfaBankClient,
)
from alfabank.enums import (
    BlockType,
    CurFormat,
    CustomerCategory,
    CustomerStatus,
    Direction,
    OperationCode,
    SpecConditionCode,
)
from alfabank.exceptions import (
    AlfaBankAPIError,
    AlfaBankAuthenticationError,
    AlfaBankConfigurationError,
    AlfaBankConflictError,
    AlfaBankError,
    AlfaBankNotFoundError,
    AlfaBankPermissionError,
    AlfaBankRateLimitError,
    AlfaBankServerError,
    AlfaBankTransportError,
    AlfaBankValidationError,
)
from alfabank.models import (
    Account,
    AccountBlockInfo,
    Address,
    BankRef,
    CartInfo,
    CurTransfer,
    CustomerInfo,
    DepartmentalInfo,
    Money,
    OrganizationForm,
    RurTransfer,
    SpecCondition,
    StatementLink,
    StatementPage,
    StatementSummary,
    SwiftTransfer,
    Transaction,
)

try:
    from alfabank._version import __version__
except ImportError:  # pragma: no cover - version file is generated at build time
    __version__ = "0.0.0+unknown"

__all__ = [
    "Account",
    "AccountBlockInfo",
    "Address",
    "AlfaBankAPIError",
    "AlfaBankAuthenticationError",
    "AlfaBankClient",
    "AlfaBankConfigurationError",
    "AlfaBankConflictError",
    "AlfaBankError",
    "AlfaBankNotFoundError",
    "AlfaBankPermissionError",
    "AlfaBankRateLimitError",
    "AlfaBankServerError",
    "AlfaBankTransportError",
    "AlfaBankValidationError",
    "ApiKeyAuth",
    "BankRef",
    "BearerAuth",
    "BlockType",
    "CartInfo",
    "CurFormat",
    "CurTransfer",
    "CustomerCategory",
    "CustomerInfo",
    "CustomerStatus",
    "DepartmentalInfo",
    "Direction",
    "Money",
    "OperationCode",
    "OrganizationForm",
    "PRODUCTION_BASE_URL",
    "RurTransfer",
    "SANDBOX_BASE_URL",
    "SpecCondition",
    "SpecConditionCode",
    "StatementLink",
    "StatementPage",
    "StatementSummary",
    "SwiftTransfer",
    "Transaction",
    "__version__",
]
```

In `tests/conftest.py`, ensure the client fixture imports via the package root: `from alfabank import AlfaBankClient` (flip it if Task 13 used `alfabank.client`).

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python -m pytest tests/test_public_api.py -v` — PASS, then the full suite `.venv/Scripts/python -m pytest -q` — all PASS.

- [ ] **Step 5: Write README.md (full replacement)**

````markdown
# alfabank-sdk

Асинхронный Python SDK для **Alfa API** Альфа-Банка (интеграция host-to-host):
выписки по счетам, сводка оборотов, информация об организации и её счетах.

- Python >= 3.10, полностью async (httpx), строгая типизация (pydantic v2, `py.typed`)
- Деньги — `Decimal`, никаких float
- Ретраи с учётом идемпотентности, опциональный rate limiter
- Две схемы аутентификации банка: `ApiKey` и `Bearer` + шов `token_provider` под OAuth

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
````

- [ ] **Step 6: Create examples**

`examples/basic_usage.py`:

```python
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
```

`examples/fastapi_integration.py`:

```python
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
```

`CHANGELOG.md`:

```markdown
# Changelog

## [Unreleased]

### Added
- `AlfaBankClient` — async-клиент Alfa API (h2h): выписки, сводка оборотов, customer-info.
- Две схемы аутентификации (`ApiKey`, `Bearer`) + `token_provider` для внешнего управления токенами.
- Экспериментальный модуль `alfabank.oauth` (обмен кода, refresh, кэширующий провайдер).
- Идемпотентные ретраи с backoff, опциональный rate limiter, маппинг ошибок API.
- Модели pydantic v2 с `Decimal` для денежных сумм; проверены на моках банка.
```

- [ ] **Step 7: Run the full suite, lint the examples too**

```bash
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m ruff check src tests examples
.venv/Scripts/python -m mypy src/alfabank
```

Expected: all PASS / clean. (Examples are NOT type-checked by mypy and `fastapi` is not installed — that's fine, ruff only.)

- [ ] **Step 8: Commit**

```bash
git add src/alfabank/__init__.py tests/test_public_api.py tests/conftest.py README.md CHANGELOG.md examples
git commit -m "feat: public API surface, README, examples, changelog"
```

---

### Task 16: CI workflows and final verification

**Files:**
- Create: `.github/workflows/tests.yml`, `.github/workflows/publish.yml`

**Interfaces:**
- Consumes: the finished package
- Produces: CI running ruff → mypy → pytest on a version matrix; PyPI publishing on `v*` tags via Trusted Publishing.

- [ ] **Step 1: Create `.github/workflows/tests.yml`**

```yaml
name: tests

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest]
        python-version: ["3.10", "3.11", "3.12", "3.13"]
        include:
          - os: windows-latest
            python-version: "3.12"
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # hatch-vcs needs tags
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
      - name: Install
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"
      - name: Ruff
        run: python -m ruff check src tests examples
      - name: Mypy
        run: python -m mypy src/alfabank
      - name: Pytest
        run: python -m pytest --cov=alfabank --cov-report=term-missing
```

- [ ] **Step 2: Create `.github/workflows/publish.yml`**

```yaml
name: publish

on:
  push:
    tags: ["v*"]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Build distributions
        run: |
          python -m pip install --upgrade pip build
          python -m build
      - uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/

  publish:
    needs: build
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write  # PyPI Trusted Publishing
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/
      - uses: pypa/gh-action-pypi-publish@release/v1
```

- [ ] **Step 3: Final full verification**

```bash
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m ruff check src tests examples
.venv/Scripts/python -m mypy src/alfabank
.venv/Scripts/python -m pip install build && .venv/Scripts/python -m build
```

Expected: tests pass, lint/type clean, `dist/` contains a wheel and sdist; the wheel contains `alfabank/py.typed` and `alfabank/_version.py` (check with `python -c "import zipfile,glob; print(zipfile.ZipFile(glob.glob('dist/*.whl')[0]).namelist())"`).

- [ ] **Step 4: Commit**

```bash
git add .github
git commit -m "ci: tests matrix and PyPI trusted publishing workflows"
```

---

## Post-plan notes (not tasks)

- **Publishing:** the first release is `git tag v0.1.0 && git push --tags` after configuring the PyPI Trusted Publisher (project `alfabank-sdk`, environment `pypi`). Not part of this plan.
- **Live verification:** base_url/api_prefix/oauth assumptions must be re-checked against the real sandbox once credentials exist (spec section 9).
- **fin-doctor integration** (new `IntegrationKind.ALFABANK`, statement sync worker) is a separate project in the fin-doctor repo — see spec section 10.

