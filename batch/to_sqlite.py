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
    load_json, toilet_db_values, toilet_db_update_values,
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

    if incremental:
        existing = cur.execute(
            "SELECT id, title, lat, lng FROM toilets"
        ).fetchall()
        existing_keys = {(r[1], r[2], r[3]): r[0] for r in existing}
        new_count = 0
        updated_count = 0

        for t in toilets:
            values = toilet_db_values(t)
            title, lat, lng = values[0], values[3], values[4]
            key = (title, lat, lng)

            if key in existing_keys:
                eid = existing_keys[key]
                cur.execute("""
                    UPDATE toilets SET
                        category = ?, address = ?, rating = ?, review_count = ?,
                        is_public_toilet = ?, toilet_score = ?, confidence = ?,
                        toilet_review_count = ?, prefecture = ?, sample_reviews_json = ?
                    WHERE id = ?
                """, toilet_db_update_values(t) + (eid,))
                updated_count += 1
            else:
                cur.execute("""
                    INSERT INTO toilets (
                        title, category, address, lat, lng, rating, review_count,
                        is_public_toilet, toilet_score, confidence, toilet_review_count,
                        prefecture, sample_reviews_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, values)
                new_count += 1

        fixed = fix_null_prefectures(conn)
        logger.info(f"Incremental merge: +{new_count} new, ~{updated_count} updated, prefecture fixed: {fixed}")

        for k, v in metadata.items():
            cur.execute(
                "INSERT INTO metadata (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (k, str(v)),
            )
        update_metadata_from_db(conn)
    else:
        for k, v in metadata.items():
            cur.execute("INSERT INTO metadata (key, value) VALUES (?, ?)", (k, str(v)))

        for t in toilets:
            cur.execute("""
                INSERT INTO toilets (
                    title, category, address, lat, lng, rating, review_count,
                    is_public_toilet, toilet_score, confidence, toilet_review_count,
                    prefecture, sample_reviews_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, toilet_db_values(t))

    conn.commit()
    conn.close()
    logger.info(f"SQLite conversion complete: {DB_PATH}")


if __name__ == "__main__":
    incremental = "--incremental" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--incremental"]
    path = args[0] if args else "data/toilets.json.gz"
    json_to_sqlite(path, incremental=incremental)
