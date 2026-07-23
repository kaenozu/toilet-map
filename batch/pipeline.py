# mypy: disable-error-code="no-redef"
"""Post-scrape pipeline that publishes a verified JSON/SQLite snapshot."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import uuid

try:
    from .db_utils import DB_PATH
    from .exceptions import DataError
    from .utils import file_lock, logger
except ImportError:
    from db_utils import DB_PATH
    from exceptions import DataError
    from utils import file_lock, logger

SYNC_LOCK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", ".toilet_sync.lock")
SNAPSHOT_MANIFEST_PATH = os.path.join(os.path.dirname(DB_PATH), "snapshot.json")


def _run_checked(command: list[str], error_message: str) -> None:
    result = subprocess.run(command)
    if result.returncode != 0:
        raise DataError(error_message)


def _write_manifest(path: str, snapshot_id: str) -> None:
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump({"snapshot_id": snapshot_id}, file)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temp_path, path)


def _tag_staged_snapshot(json_path: str, db_path: str, snapshot_id: str) -> None:
    import gzip

    with gzip.open(json_path, "rt", encoding="utf-8") as file:
        payload = json.load(file)
    payload.setdefault("metadata", {})["snapshot_id"] = snapshot_id
    temp_json = f"{json_path}.tagged"
    with gzip.open(temp_json, "wt", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False)
    os.replace(temp_json, json_path)

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "INSERT INTO metadata (key, value) VALUES ('snapshot_id', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (snapshot_id,),
        )
        connection.commit()


def run_postprocess_pipeline(input_path: str, processed_path: str, script_dir: str) -> None:
    """Build both artifacts in a temp directory and publish only after both succeed."""
    data_dir = os.path.dirname(os.path.abspath(processed_path))
    os.makedirs(data_dir, exist_ok=True)

    with file_lock(SYNC_LOCK_PATH), tempfile.TemporaryDirectory(
        prefix="toilet-snapshot-", dir=data_dir
    ) as temp_dir:
        temp_json = os.path.join(temp_dir, os.path.basename(processed_path))
        temp_db = os.path.join(temp_dir, os.path.basename(DB_PATH))

        if os.path.exists(processed_path):
            shutil.copy2(processed_path, temp_json)

        logger.info("Processing data into a staged snapshot...")
        _run_checked(
            [sys.executable, os.path.join(script_dir, "process_data.py"), input_path, temp_json, "--incremental"],
            "Data processing failed",
        )

        logger.info("Building staged SQLite snapshot...")
        _run_checked(
            [
                sys.executable,
                os.path.join(script_dir, "to_sqlite.py"),
                temp_json,
                "--db-path",
                temp_db,
                "--incremental",
            ],
            "SQLite conversion failed",
        )

        snapshot_id = uuid.uuid4().hex
        _tag_staged_snapshot(temp_json, temp_db, snapshot_id)

        rollback_json = os.path.join(temp_dir, "previous.json.gz")
        rollback_db = os.path.join(temp_dir, "previous.db")
        had_previous_json = os.path.exists(processed_path)
        had_previous_db = os.path.exists(DB_PATH)
        if had_previous_json:
            shutil.copy2(processed_path, rollback_json)
        if had_previous_db:
            shutil.copy2(DB_PATH, rollback_db)

        try:
            os.replace(temp_db, DB_PATH)
            os.replace(temp_json, processed_path)
            _write_manifest(SNAPSHOT_MANIFEST_PATH, snapshot_id)
        except OSError:
            if had_previous_db and os.path.exists(rollback_db):
                os.replace(rollback_db, DB_PATH)
            elif os.path.exists(DB_PATH):
                os.remove(DB_PATH)
            if had_previous_json and os.path.exists(rollback_json):
                os.replace(rollback_json, processed_path)
            elif os.path.exists(processed_path):
                os.remove(processed_path)
            raise
        logger.info("Published canonical JSON and SQLite snapshot %s", snapshot_id)
