"""Database connection and schema migration entrypoints."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from psycopg import Connection, connect
from psycopg.rows import DictRow, dict_row

from .migrations import apply_migrations

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://toilet_map:toilet_map@localhost:5432/toilet_map",
).replace("postgresql+psycopg://", "postgresql://")


@contextmanager
def database() -> Iterator[Connection[DictRow]]:
    connection: Connection[DictRow] = connect(
        DATABASE_URL,
        row_factory=dict_row,
    )
    with connection:
        yield connection


def apply_schema(migrations_path: Path | None = None) -> list[str]:
    """Apply all pending versioned migrations and return their versions."""
    with database() as connection:
        applied = apply_migrations(connection, migrations_path)
        connection.commit()
    return applied
