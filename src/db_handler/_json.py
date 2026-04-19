"""Internal JSON-coercion helpers."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID


def json_safe(data: Any) -> Any:
    """Recursively coerce values that PostgREST/httpx cannot serialize natively.

    Handles ``datetime``, ``date``, ``Enum``, ``UUID``, and ``Decimal`` values
    nested inside dicts and lists. Pydantic models are dumped via ``model_dump``.
    Unknown types are returned as-is so the underlying serializer can raise.
    """
    if isinstance(data, dict):
        return {k: json_safe(v) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [json_safe(v) for v in data]
    if isinstance(data, (datetime, date)):
        return data.isoformat()
    if isinstance(data, Enum):
        return data.value
    if isinstance(data, UUID):
        return str(data)
    if isinstance(data, Decimal):
        return str(data)
    if hasattr(data, "model_dump"):
        return json_safe(data.model_dump())
    return data
