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
