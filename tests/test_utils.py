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
