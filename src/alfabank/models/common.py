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
