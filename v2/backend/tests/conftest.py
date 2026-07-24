"""Test-only fallback stubs when psycopg is unavailable locally."""

from __future__ import annotations

import sys
import types

try:
    import psycopg  # noqa: F401
except ModuleNotFoundError:
    module = types.ModuleType("psycopg")

    class Connection:  # pragma: no cover - typing fallback only.
        pass

    def connect(*args, **kwargs):  # pragma: no cover - DB tests require real psycopg.
        raise RuntimeError("psycopg is required for database integration tests")

    module.Connection = Connection
    module.connect = connect
    rows = types.ModuleType("psycopg.rows")
    rows.dict_row = object()
    sys.modules["psycopg"] = module
    sys.modules["psycopg.rows"] = rows
