"""Cross-check and repair the canonical JSON, SQLite, and manifest snapshot."""

from __future__ import annotations

import gzip
import importlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from types import ModuleType


def _load_module(name: str) -> ModuleType:
    if __package__:
        return importlib.import_module(f".{name}", package=__package__)
    return importlib.import_module(name)


_db_utils = _load_module("db_utils")
_to_sqlite = _load_module("to_sqlite")

DB_PATH = _db_utils.DB_PATH
JSON_PATH = _db_utils.JSON_PATH
database_requires_rebuild = _db_utils.database_requires_rebuild
_convert_core = _to_sqlite._convert_core

MANIFEST_PATH = os.path.join(os.path.dirname(DB_PATH), "snapshot.json")


def _json_snapshot_id(path: str) -> str | None:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    value = (payload.get("metadata") or {}).get("snapshot_id")
    return str(value) if value else None


def _database_snapshot_id(path: str) -> str | None:
    with sqlite3.connect(path) as connection:
        row = connection.execute("SELECT value FROM metadata WHERE key = 'snapshot_id'").fetchone()
    return str(row[0]) if row and row[0] else None


def _manifest_snapshot_id(path: str) -> str | None:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    value = payload.get("snapshot_id")
    return str(value) if value else None


def snapshot_ids_match(
    json_path: str = JSON_PATH,
    db_path: str = DB_PATH,
    manifest_path: str = MANIFEST_PATH,
) -> bool:
    try:
        ids = {
            _json_snapshot_id(json_path),
            _database_snapshot_id(db_path),
            _manifest_snapshot_id(manifest_path),
        }
    except (OSError, ValueError, json.JSONDecodeError, sqlite3.DatabaseError):
        return False
    return None not in ids and len(ids) == 1


def ensure_snapshot_current(
    json_path: str = JSON_PATH,
    db_path: str = DB_PATH,
    manifest_path: str = MANIFEST_PATH,
) -> None:
    if not database_requires_rebuild(db_path) and snapshot_ids_match(json_path, db_path, manifest_path):
        return
    if not os.path.exists(json_path):
        raise FileNotFoundError(json_path)

    db_dir = os.path.dirname(os.path.abspath(db_path))
    os.makedirs(db_dir, exist_ok=True)
    fd, temp_db = tempfile.mkstemp(prefix=".toilets-rebuild-", suffix=".db", dir=db_dir)
    os.close(fd)
    try:
        os.remove(temp_db)
        _convert_core(json_path, temp_db, incremental=False)
        json_id = _json_snapshot_id(json_path)
        if not json_id:
            raise ValueError("canonical JSON is missing metadata.snapshot_id")
        with sqlite3.connect(temp_db) as connection:
            connection.execute(
                "INSERT INTO metadata (key, value) VALUES ('snapshot_id', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (json_id,),
            )
            connection.commit()
        os.replace(temp_db, db_path)
        Path(manifest_path).write_text(
            json.dumps({"snapshot_id": json_id}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    finally:
        if os.path.exists(temp_db):
            os.remove(temp_db)
