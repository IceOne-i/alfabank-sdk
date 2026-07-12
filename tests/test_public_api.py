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
