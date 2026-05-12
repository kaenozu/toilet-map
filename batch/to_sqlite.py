"""
batch/to_sqlite.py
JSON データを SQLite データベースに変換し、検索と読み込みを高速化する。
--incremental でマージモード (既存データ保持)

関連ファイル:
  - batch/db_utils.py (共通ユーティリティ)
  - data/toilets.db (出力 DB)
"""
import sqlite3
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_JSON_PATH = os.path.join(SCRIPT_DIR, "..", "data", "toilets.json.gz")
sys.path.insert(0, SCRIPT_DIR)

from db_utils import (  # noqa: E402
    DB_PATH, ensure_schema,
    fix_null_prefectures, update_metadata_from_db,
    load_json, upsert_metadata, upsert_toilets,
)


def _convert_core(
    json_path: str,
    db_path: str,
    incremental: bool = False,
) -> int:
    """JSON → SQLite 変換のコア処理。総件数を返す。"""
    from utils import logger

    data = load_json(json_path)
    metadata = data.get("metadata", {})
    toilets = data.get("toilets", [])

    conn = sqlite3.connect(db_path)
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

    total = cur.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
    conn.close()
    return total


def json_to_sqlite(json_path: str, incremental: bool = False) -> None:
    from utils import logger

    if not incremental and os.path.exists(DB_PATH):
        import shutil
        backup_path = f"{DB_PATH}.bak"
        shutil.copy2(DB_PATH, backup_path)
        logger.info(f"Existing database backed up to {backup_path}")

    logger.info(f"Converting {json_path} to SQLite (incremental={incremental})...")
    total = _convert_core(json_path, DB_PATH, incremental)
    logger.info(f"SQLite conversion complete: {DB_PATH} ({total} toilets)")


def merge(json_path: str, db_path: str = DB_PATH) -> None:
    from utils import logger
    logger.info(f"Merging {json_path} into SQLite...")
    total = _convert_core(json_path, db_path, incremental=True)
    conn = sqlite3.connect(db_path)
    try:
        null_pref = conn.execute(
            "SELECT COUNT(*) FROM toilets WHERE prefecture IS NULL OR prefecture = ''"
        ).fetchone()[0]
    finally:
        conn.close()
    logger.info(f"Done: {total} total toilets, {null_pref} remaining NULL prefecture")


if __name__ == "__main__":
    incremental = "--incremental" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--incremental"]
    path = args[0] if args else DEFAULT_JSON_PATH
    if incremental:
        merge(path)
    else:
        json_to_sqlite(path)
