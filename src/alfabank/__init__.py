"""alfabank-sdk: unofficial async Python SDK for the Alfa-Bank Alfa API (h2h).

This SDK is **not affiliated** with, endorsed by, or in any way officially
connected with Alfa-Bank (АО «Альфа-Банк», https://alfabank.ru).

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

__all__ = [  # noqa: RUF022 - sorted() order is mandated by test_all_is_sorted; RUF022 wants isort-style order
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
