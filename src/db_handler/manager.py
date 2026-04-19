"""Backend-agnostic database manager interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class NotNull:
    """Sentinel value for ``IS NOT NULL`` conditions in queries.

    Use the module-level :data:`NOT_NULL` instance rather than constructing this
    class directly.
    """

    def __repr__(self) -> str:
        return "NOT_NULL"


NOT_NULL = NotNull()
"""Use as a condition value to filter for non-null fields.

Example::

    repo.select_many({"deleted_at": NOT_NULL})
"""


class Overlaps:
    """Sentinel for array-overlap conditions (PostgreSQL ``&&`` / PostgREST ``.ov``).

    Matches rows where the column's array shares at least one element with the
    supplied values.

    Example::

        repo.select_many({"tags": Overlaps(["urgent", "legal"])})
    """

    __slots__ = ("values",)

    def __init__(self, values: "list[Any] | tuple[Any, ...] | set[Any]"):
        self.values = list(values)

    def __repr__(self) -> str:
        return f"Overlaps({self.values!r})"


class DatabaseManager(ABC):
    """Abstract interface for a database backend.

    Concrete implementations (e.g. :class:`SupabaseManager`) translate these
    calls into backend-specific queries. Repositories depend only on this ABC.
    """

    @abstractmethod
    def select_one(
        self,
        table: str,
        result_type: Type[T],
        condition: dict[str, Any],
        selection: str = "*",
    ) -> Optional[T]:
        ...

    @abstractmethod
    def select_many(
        self,
        table: str,
        result_type: Type[T],
        condition: dict[str, Any],
        sort_by: Optional[str] = None,
        sort_direction: str = "asc",
        start: Optional[int] = None,
        end: Optional[int] = None,
        selection: str = "*",
    ) -> tuple[list[T], int]:
        ...

    @abstractmethod
    def insert(
        self,
        table: str,
        data: dict[str, Any],
        result_type: Type[T],
    ) -> T:
        ...

    @abstractmethod
    def upsert(
        self,
        table: str,
        data: dict[str, Any],
        result_type: Type[T],
        on_conflict: str,
    ) -> T:
        ...

    @abstractmethod
    def update(
        self,
        table: str,
        record_id: Any,
        data: dict[str, Any],
        result_type: Type[T],
        id_column: str = "id",
    ) -> T:
        ...

    @abstractmethod
    def delete(
        self,
        table: str,
        record_id: Any,
        id_column: str = "id",
    ) -> bool:
        ...

    @abstractmethod
    def exists(self, table: str, field: str, value: Any) -> bool:
        ...
