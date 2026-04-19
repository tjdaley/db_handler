"""Pydantic-typed repository pattern over Supabase."""

from db_handler.manager import DatabaseManager, NOT_NULL, NotNull, Overlaps
from db_handler.repository import BaseRepository
from db_handler.supabase_manager import SupabaseManager

__all__ = [
    "BaseRepository",
    "DatabaseManager",
    "NOT_NULL",
    "NotNull",
    "Overlaps",
    "SupabaseManager",
]

__version__ = "0.1.0"
