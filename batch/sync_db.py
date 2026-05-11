"""
batch/sync_db.py
JSON と SQLite を同期する。to_sqlite.py への互換ラッパー。
update_data.bat から呼ばれる。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from to_sqlite import DEFAULT_JSON_PATH, json_to_sqlite as _json_to_sqlite


def sync_json_to_sqlite(json_path: str) -> None:
    """JSON データで SQLite データベースを上書き更新。"""
    _json_to_sqlite(json_path, incremental=False)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_JSON_PATH
    sync_json_to_sqlite(path)