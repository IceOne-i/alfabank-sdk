"""alfabank-sdk: async Python SDK for the Alfa-Bank Alfa API (h2h)."""

from __future__ import annotations

try:
    from alfabank._version import __version__
except ImportError:  # pragma: no cover - version file is generated at build time
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
