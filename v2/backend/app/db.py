from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from psycopg import Connection, connect
from psycopg.rows import dict_row

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://toilet_map:toilet_map@localhost:5432/toilet_map",
).replace("postgresql+psycopg://", "postgresql://")


@contextmanager
def database() -> Iterator[Connection]:
    with connect(DATABASE_URL, row_factory=dict_row) as connection:
        yield connection


def apply_schema(schema_path: Path | None = None) -> None:
    path = schema_path or Path(__file__).resolve().parents[1] / "schema.sql"
    sql = path.read_text(encoding="utf-8")
    with database() as connection:
        connection.execute(sql)
        connection.commit()
