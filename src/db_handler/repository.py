"""Generic repository over a :class:`DatabaseManager`."""
from __future__ import annotations

from typing import Any, Generic, Optional, Type, TypeVar

from pydantic import BaseModel

from db_handler.manager import DatabaseManager

T = TypeVar("T", bound=BaseModel)


class BaseRepository(Generic[T]):
    """One repository instance per table.

    Subclass to add table-specific queries::

        class AttorneyRepo(BaseRepository[Attorney]):
            def __init__(self, manager: DatabaseManager):
                super().__init__(manager, "attorneys", Attorney)

            def by_firm_id(self, firm_id: int) -> list[Attorney]:
                rows, _ = self.select_many({"firm_id": firm_id})
                return rows
    """

    def __init__(
        self,
        manager: DatabaseManager,
        table_name: str,
        model_class: Type[T],
    ):
        self.manager = manager
        self.table_name = table_name
        self.model_class = model_class

    def select_one(
        self,
        condition: dict[str, Any],
        selection: str = "*",
    ) -> Optional[T]:
        return self.manager.select_one(
            self.table_name, self.model_class, condition, selection
        )

    def select_many(
        self,
        condition: dict[str, Any],
        sort_by: Optional[str] = None,
        sort_direction: str = "asc",
        start: Optional[int] = None,
        end: Optional[int] = None,
        selection: str = "*",
    ) -> tuple[list[T], int]:
        return self.manager.select_many(
            self.table_name,
            self.model_class,
            condition,
            sort_by,
            sort_direction,
            start,
            end,
            selection,
        )

    def insert(self, data: dict[str, Any]) -> T:
        return self.manager.insert(self.table_name, data, self.model_class)

    def upsert(self, data: dict[str, Any], on_conflict: str) -> T:
        return self.manager.upsert(
            self.table_name, data, self.model_class, on_conflict
        )

    def update(
        self,
        record_id: Any,
        data: dict[str, Any],
        id_column: str = "id",
    ) -> T:
        return self.manager.update(
            self.table_name, record_id, data, self.model_class, id_column
        )

    def delete(self, record_id: Any, id_column: str = "id") -> bool:
        return self.manager.delete(self.table_name, record_id, id_column)

    def exists(self, field: str, value: Any) -> bool:
        return self.manager.exists(self.table_name, field, value)
