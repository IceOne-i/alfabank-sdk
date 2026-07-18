"""Smoke test: the package installs and exposes a version."""

from __future__ import annotations


def test_package_imports() -> None:
    import alfabank

    assert isinstance(alfabank.__version__, str)
    assert alfabank.__version__
