"""
batch/merge_to_db.py
JSON データを既存 SQLite にマージし、都道府県 NULL を修復する。

関連ファイル:
  - batch/to_sqlite.py (フルリプレース版)
  - batch/db_utils.py (共通ユーティリティ)
  - data/toilets.db (出力 DB)
  - data/toilets.json.gz (入力 JSON)
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


def merge(json_path: str, db_path: str = DB_PATH) -> None:
    from utils import logger

    logger.info(f"Loading JSON: {json_path}")
    data = load_json(json_path)
    metadata = data.get("metadata", {})
    toilets = data.get("toilets", [])
    logger.info(f"JSON toilets: {len(toilets)}")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    ensure_schema(cur)

    upsert_metadata(cur, metadata)

    logger.info("Merging toilets (UPSERT by title+lat+lng)...")
    upsert_toilets(cur, toilets)
    logger.info(f"Upserted {len(toilets)} toilets")

    logger.info("Fixing prefecture=NULL rows...")
    fixed = fix_null_prefectures(conn)
    logger.info(f"Fixed {fixed} prefecture entries")

    update_metadata_from_db(conn)

    conn.commit()
    total = cur.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
    null_pref = cur.execute("SELECT COUNT(*) FROM toilets WHERE prefecture IS NULL OR prefecture = ''").fetchone()[0]
    conn.close()

    logger.info(f"Done: {total} total toilets, {null_pref} remaining NULL prefecture")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/toilets.json.gz"
    merge(path)
