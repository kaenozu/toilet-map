"""
batch/to_sqlite.py
JSON データを SQLite データベースに変換し、検索と読み込みを高速化する。
--incremental でマージモード (既存データ保持)

関連ファイル:
  - batch/merge_to_db.py (マージ専用スクリプト)
  - batch/db_utils.py (共通ユーティリティ)
  - data/toilets.db (出力 DB)
"""
import sqlite3
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from db_utils import (
    DB_PATH, ensure_schema,
    fix_null_prefectures, update_metadata_from_db,
    load_json, upsert_metadata, upsert_toilets,
)


def json_to_sqlite(json_path: str, incremental: bool = False) -> None:
    from utils import logger

    logger.info(f"Converting {json_path} to SQLite (incremental={incremental})...")

    data = load_json(json_path)
    metadata = data.get("metadata", {})
    toilets = data.get("toilets", [])

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    if not incremental:
        cur.execute("DROP TABLE IF EXISTS toilets")
        cur.execute("DROP TABLE IF EXISTS metadata")

    ensure_schema(cur)

    upsert_metadata(cur, metadata)
    upsert_toilets(cur, toilets)

    fixed = fix_null_prefectures(conn)
    logger.info(f"Upserted {len(toilets)} toilets, prefecture fixed: {fixed}")

    update_metadata_from_db(conn)

    conn.commit()
    conn.close()
    logger.info(f"SQLite conversion complete: {DB_PATH}")


if __name__ == "__main__":
    incremental = "--incremental" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--incremental"]
    path = args[0] if args else "data/toilets.json.gz"
    json_to_sqlite(path, incremental=incremental)
