"""Shared database typing for dictionary-row psycopg connections."""

from psycopg import Connection
from psycopg.rows import DictRow

__all__ = ["DbConnection"]

DbConnection = Connection[DictRow]
