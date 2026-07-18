# mypy: disable-error-code="no-redef"
"""Post-scrape pipeline that publishes a verified JSON/SQLite snapshot."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

try:
    from .db_utils import DB_PATH
    from .exceptions import DataError
    from .utils import file_lock, logger
except ImportError:
    from db_utils import DB_PATH
    from exceptions import DataError
    from utils import file_lock, logger

SYNC_LOCK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", ".toilet_sync.lock")


def _run_checked(command: list[str], error_message: str) -> None:
    result = subprocess.run(command)
    if result.returncode != 0:
        raise DataError(error_message)


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
            ],
            "SQLite conversion failed",
        )

        rollback_json = os.path.join(temp_dir, "previous.json.gz")
        had_previous_json = os.path.exists(processed_path)
        if had_previous_json:
            shutil.copy2(processed_path, rollback_json)
        os.replace(temp_json, processed_path)
        try:
            os.replace(temp_db, DB_PATH)
        except OSError:
            if had_previous_json:
                os.replace(rollback_json, processed_path)
            else:
                os.remove(processed_path)
            raise
        logger.info("Published canonical JSON and SQLite snapshot")
