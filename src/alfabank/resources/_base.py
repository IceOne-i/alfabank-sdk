"""Base class for API resources."""

from __future__ import annotations

from alfabank._transport import Transport


class Resource:
    """Holds the shared transport; concrete resources add endpoint methods."""

    __slots__ = ("_transport",)

    def __init__(self, transport: Transport) -> None:
        self._transport = transport
