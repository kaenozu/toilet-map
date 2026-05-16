"""
batch/sync_db.py
JSON と SQLite を同期する。to_sqlite.py への互換ラッパー。
update_data.bat から呼ばれる。

Deprecation notice: This is a thin wrapper for backward compatibility.
Use `python batch/to_sqlite.py <json_path> --full` directly instead.
"""
import sys

from to_sqlite import DEFAULT_JSON_PATH
from to_sqlite import json_to_sqlite as _json_to_sqlite


def sync_json_to_sqlite(json_path: str) -> None:
    """JSON データで SQLite データベースを上書き更新。"""
    _json_to_sqlite(json_path, incremental=False)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_JSON_PATH
    sync_json_to_sqlite(path)
