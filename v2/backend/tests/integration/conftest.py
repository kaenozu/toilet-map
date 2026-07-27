"""
v2/backend/tests/integration/conftest.py

PostgreSQL database fixture for integration tests.
Applies migrations once per session. Skips all tests when psycopg
or a real PostgreSQL instance is unavailable.

Related: app/db.py, app/migrations.py
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.db import DATABASE_URL
from app.migrations import apply_migrations

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def _real_psycopg():
    """Return the psycopg module only if it's the real one (not the test stub)."""
    import sys

    mod = sys.modules.get("psycopg")
    if mod is None:
        return None
    connect = getattr(mod, "connect", None)
    if connect is None:
        return None
    try:
        conn = connect(DATABASE_URL)
        conn.close()
        return mod
    except RuntimeError:
        return None  # test stub raised RuntimeError
    except Exception:
        return mod  # real psycopg, DB just isn't reachable


PSYCOPG = _real_psycopg()


def _connect(**kwargs):
    assert PSYCOPG is not None
    return PSYCOPG.connect(DATABASE_URL, **kwargs)


def truncate_all() -> None:
    conn = _connect()
    conn.autocommit = True
    tables = conn.execute(
        """
        SELECT tablename FROM pg_catalog.pg_tables
         WHERE schemaname = 'public' AND tablename != 'schema_migrations'
        """
    ).fetchall()
    for row in tables:
        conn.execute(f'TRUNCATE TABLE "{row[0]}" CASCADE')
    conn.close()


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integration: requires a real PostgreSQL database")
    config.addinivalue_line(
        "markers",
        "slow: test that takes longer than a few seconds to run",
    )


@pytest.fixture(scope="session")
def _schema() -> None:
    if PSYCOPG is None:
        pytest.skip("psycopg is not installed or DB is unreachable")
    conn = _connect()
    try:
        apply_migrations(conn, MIGRATIONS_DIR)
    finally:
        conn.close()


@pytest.fixture
def db(_schema: None) -> Iterator:
    conn = _connect()
    try:
        yield conn
    finally:
        conn.close()
