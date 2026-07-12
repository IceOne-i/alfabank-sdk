"""Shared pytest fixtures for alfabank-sdk tests."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import respx

_MOCKS_DIR = Path(__file__).resolve().parent.parent / "specs" / "alfa-api" / "mocks"

TEST_BASE_URL = "https://baas.alfabank.ru"


@pytest.fixture
def load_mock() -> Callable[[str], Any]:
    """Load a vendored bank mock JSON by path relative to specs/alfa-api/mocks/."""

    def _load(relpath: str) -> Any:
        return json.loads((_MOCKS_DIR / relpath).read_text(encoding="utf-8"))

    return _load


@pytest.fixture
def base_url() -> str:
    return TEST_BASE_URL


@pytest.fixture
def mock_api(base_url: str) -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=base_url, assert_all_called=False) as router:
        yield router
