"""Supabase implementation of :class:`DatabaseManager`."""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Optional, Type, TypeVar

from httpx import ConnectError
from postgrest.base_request_builder import APIResponse
from postgrest.exceptions import APIError
from postgrest.types import CountMethod
from pydantic import BaseModel
from supabase import Client, create_client
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from db_handler._json import json_safe
from db_handler.manager import DatabaseManager, NotNull, Overlaps

LOGGER = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_DUPLICATE_KEY_RE = re.compile(r"Key \(([^)]+)\)=\(([^)]+)\) already exists")

_RETRY = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(APIError),
    reraise=True,
)


class SupabaseManager(DatabaseManager):
    """A :class:`DatabaseManager` backed by Supabase / PostgREST.

    Credentials resolve in this order:

    1. Explicit ``url`` / ``key`` constructor arguments.
    2. ``SUPABASE_URL`` and ``SUPABASE_SERVICE_ROLE_KEY`` (or ``SUPABASE_KEY``)
       environment variables.

    Parameters
    ----------
    url:
        Supabase project URL. Falls back to ``SUPABASE_URL``.
    key:
        Supabase service-role or anon key. Falls back to
        ``SUPABASE_SERVICE_ROLE_KEY`` then ``SUPABASE_KEY``.
    client:
        Pre-built :class:`supabase.Client`. If supplied, ``url``/``key`` are
        ignored. Useful for tests or custom client configuration.
    verify_connection:
        If True (default) call ``client.auth.get_user()`` on init to fail fast
        on bad credentials. Set False in offline tests.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        key: Optional[str] = None,
        *,
        client: Optional[Client] = None,
        verify_connection: bool = True,
    ):
        if client is not None:
            self.client = client
            self.url = url
            self.key = key
            return

        self.url = url or os.environ.get("SUPABASE_URL")
        self.key = (
            key
            or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
            or os.environ.get("SUPABASE_KEY")
        )
        if not self.url or not self.key:
            raise ValueError(
                "Supabase URL and key must be provided either as arguments or "
                "via SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY env vars."
            )

        try:
            self.client = create_client(self.url, self.key)
            if verify_connection:
                self.client.auth.get_user()
            LOGGER.info("Connected to Supabase at %s", self.url)
        except ConnectError:
            LOGGER.error("Failed to connect to Supabase: network unreachable.")
            raise
        except APIError as e:
            LOGGER.error("Supabase API error during connect (check key): %s", e)
            raise
        except Exception as e:
            LOGGER.error("Unexpected Supabase connection error: %s", e)
            raise

    @staticmethod
    def _apply_condition(query, condition: dict[str, Any]):
        for field, value in condition.items():
            if isinstance(value, NotNull):
                query = query.not_.is_(field, "null")
            elif isinstance(value, Overlaps):
                query = query.ov(field, value.values)
            elif value is None:
                query = query.is_(field, "null")
            elif isinstance(value, (list, tuple, set)):
                query = query.in_(field, list(value))
            else:
                query = query.eq(field, value)
        return query

    @_RETRY
    def select_one(
        self,
        table: str,
        result_type: Type[T],
        condition: dict[str, Any],
        selection: str = "*",
    ) -> Optional[T]:
        query = self.client.table(table).select(selection)
        query = self._apply_condition(query, condition)

        try:
            result: APIResponse = query.single().execute()
        except APIError as e:
            if e.code == "PGRST116":
                return None
            LOGGER.error(
                "select_one failed on %s with condition %s: %s",
                table, condition, e,
            )
            raise

        if isinstance(result.data, dict):
            return result_type(**result.data)
        return None

    @_RETRY
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
        query = self.client.table(table).select(selection, count=CountMethod.exact)
        query = self._apply_condition(query, condition)

        if sort_by:
            query = query.order(
                sort_by,
                desc=(sort_direction.strip().lower() == "desc"),
            )
        if start is not None and end is not None:
            query = query.range(start, end)

        result = query.execute()
        if not result.data:
            return [], result.count or 0
        return [result_type(**item) for item in result.data], result.count or 0

    @_RETRY
    def insert(
        self,
        table: str,
        data: dict[str, Any],
        result_type: Type[T],
    ) -> T:
        if isinstance(data, str):
            raise ValueError(
                "insert() data must be a dict, not a JSON string."
            )

        payload = json_safe(data)
        try:
            result = self.client.table(table).insert(payload).execute()
        except APIError as e:
            if e.code == "23505":
                raise self._duplicate_key_error(e) from e
            LOGGER.error("Error inserting into %s: %s", table, e)
            raise

        if not result.data:
            raise ValueError(
                f"Insert returned no data for table {table}; payload={payload}"
            )
        return result_type(**result.data[0])

    @_RETRY
    def upsert(
        self,
        table: str,
        data: dict[str, Any],
        result_type: Type[T],
        on_conflict: str,
    ) -> T:
        if isinstance(data, str):
            raise ValueError(
                "upsert() data must be a dict, not a JSON string."
            )

        payload = json_safe(data)
        result = (
            self.client.table(table)
            .upsert(payload, on_conflict=on_conflict)
            .execute()
        )
        if not result.data:
            raise ValueError(
                f"Upsert returned no data for table {table}; payload={payload}"
            )
        return result_type(**result.data[0])

    @_RETRY
    def update(
        self,
        table: str,
        record_id: Any,
        data: dict[str, Any],
        result_type: Type[T],
        id_column: str = "id",
    ) -> T:
        payload = json_safe(data)
        result = (
            self.client.table(table)
            .update(payload)
            .eq(id_column, record_id)
            .execute()
        )
        if not result.data:
            raise ValueError(
                f"Update on {table}.{id_column}={record_id} returned no rows."
            )
        return result_type(**result.data[0])

    @_RETRY
    def delete(
        self,
        table: str,
        record_id: Any,
        id_column: str = "id",
    ) -> bool:
        self.client.table(table).delete().eq(id_column, record_id).execute()
        return True

    @_RETRY
    def exists(self, table: str, field: str, value: Any) -> bool:
        try:
            result = (
                self.client.table(table)
                .select("*", count=CountMethod.exact, head=True)
                .eq(field, value)
                .execute()
            )
            return (result.count or 0) > 0
        except APIError as e:
            if e.code == "PGRST116":
                return False
            LOGGER.error("exists() failed on %s.%s=%r: %s", table, field, value, e)
            raise

    @staticmethod
    def _duplicate_key_error(e: APIError) -> KeyError:
        match = _DUPLICATE_KEY_RE.search(e.details or "")
        if match:
            key_name, key_value = match.group(1), match.group(2)
            return KeyError(
                f"Duplicate key: {key_name}={key_value!r}"
            )
        return KeyError(f"Duplicate key error: {e.details}")
