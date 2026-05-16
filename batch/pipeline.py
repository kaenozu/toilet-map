"""
batch/pipeline.py
スクレイプ完了後のデータ処理パイプライン
生データ → JSON → SQLite の更新を直列実行
"""
import subprocess
import sys
import os
from utils import logger, file_lock
from exceptions import DataError

SYNC_LOCK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", ".toilet_sync.lock")


def run_postprocess_pipeline(input_path: str, processed_path: str, script_dir: str) -> None:
    with file_lock(SYNC_LOCK_PATH):
        logger.info("Processing data (incremental merge)...")
        process_result = subprocess.run(
            [sys.executable, os.path.join(script_dir, "process_data.py"), input_path, processed_path, "--incremental"],
        )
        if process_result.returncode != 0:
            raise DataError("Data processing failed")

        logger.info("Refreshing SQLite cache...")
        sqlite_result = subprocess.run(
            [sys.executable, os.path.join(script_dir, "to_sqlite.py"), processed_path, "--incremental"],
        )
        if sqlite_result.returncode != 0:
            raise DataError("SQLite conversion failed")
