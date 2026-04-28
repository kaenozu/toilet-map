"""
batch/to_sqlite.py
JSON データを SQLite データベースに変換し、検索と読み込みを高速化する。
--incremental でマージモード (既存データ保持)

関連ファイル:
  - batch/merge_to_db.py (マージ専用スクリプト)
  - batch/scoring_config.py (PREFECTURES)
  - data/toilets.db (出力 DB)
"""
import sqlite3
import json
import os
import sys
import gzip
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.dirname(__file__))
from utils import logger
from scoring_config import PREFECTURES

DB_PATH = "data/toilets.db"


def _extract_prefecture(address: str) -> str:
    if not address:
        return ""
    for pref in PREFECTURES:
        if pref in address:
            return pref
    return ""


def _ensure_schema(cur: sqlite3.Cursor) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS toilets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            category TEXT,
            address TEXT,
            lat REAL,
            lng REAL,
            rating REAL,
            review_count INTEGER,
            is_public_toilet BOOLEAN,
            toilet_score REAL,
            confidence REAL,
            toilet_review_count INTEGER,
            prefecture TEXT,
            sample_reviews_json TEXT
        )
    """)
    cur.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pref ON toilets(prefecture)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_score ON toilets(toilet_score)")


def _load_json(json_path: str) -> dict:
    if json_path.endswith(".gz"):
        with gzip.open(json_path, "rt", encoding="utf-8") as f:
            return json.load(f)
    else:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)


def json_to_sqlite(json_path: str, incremental: bool = False) -> None:
    logger.info(f"Converting {json_path} to SQLite (incremental={incremental})...")

    data = _load_json(json_path)
    metadata = data.get("metadata", {})
    toilets = data.get("toilets", [])

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    if not incremental:
        cur.execute("DROP TABLE IF EXISTS toilets")
        cur.execute("DROP TABLE IF EXISTS metadata")

    _ensure_schema(cur)

    if incremental:
        existing = cur.execute(
            "SELECT id, title, lat, lng FROM toilets"
        ).fetchall()
        existing_keys = {(r[1], r[2], r[3]): r[0] for r in existing}
        new_count = 0
        updated_count = 0

        for t in toilets:
            title = t.get("title", "")
            lat = t.get("lat")
            lng = t.get("lng")
            address = t.get("address", "")
            prefecture = t.get("prefecture") or _extract_prefecture(address)
            reviews_json = json.dumps(t.get("sample_reviews", []), ensure_ascii=False)
            key = (title, lat, lng)

            if key in existing_keys:
                eid = existing_keys[key]
                cur.execute("""
                    UPDATE toilets SET
                        category = ?, address = ?, rating = ?, review_count = ?,
                        is_public_toilet = ?, toilet_score = ?, confidence = ?,
                        toilet_review_count = ?, prefecture = ?, sample_reviews_json = ?
                    WHERE id = ?
                """, (
                    t.get("category"), address, t.get("rating"), t.get("review_count"),
                    t.get("is_public_toilet"), t.get("toilet_score"), t.get("confidence"),
                    t.get("toilet_review_count"), prefecture, reviews_json, eid,
                ))
                updated_count += 1
            else:
                cur.execute("""
                    INSERT INTO toilets (
                        title, category, address, lat, lng, rating, review_count,
                        is_public_toilet, toilet_score, confidence, toilet_review_count,
                        prefecture, sample_reviews_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    title, t.get("category"), address, lat, lng,
                    t.get("rating"), t.get("review_count"), t.get("is_public_toilet"),
                    t.get("toilet_score"), t.get("confidence"), t.get("toilet_review_count"),
                    prefecture, reviews_json,
                ))
                new_count += 1

        null_rows = cur.execute(
            "SELECT id, address FROM toilets WHERE prefecture IS NULL OR prefecture = ''"
        ).fetchall()
        fixed = 0
        for row_id, address in null_rows:
            pref = _extract_prefecture(address or "")
            if pref:
                cur.execute("UPDATE toilets SET prefecture = ? WHERE id = ?", (pref, row_id))
                fixed += 1

        logger.info(f"Incremental merge: +{new_count} new, ~{updated_count} updated, prefectures fixed: {fixed}")

        for k, v in metadata.items():
            cur.execute(
                "INSERT INTO metadata (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (k, str(v)),
            )
        total = cur.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
        scored = cur.execute("SELECT COUNT(*) FROM toilets WHERE confidence > 0").fetchone()[0]
        public = cur.execute("SELECT COUNT(*) FROM toilets WHERE is_public_toilet = 1").fetchone()[0]
        now = datetime.now().strftime("%Y-%m-%d")
        for k, v in [("total", total), ("scored", scored), ("public_toilets", public), ("last_updated", now)]:
            cur.execute(
                "INSERT INTO metadata (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (k, str(v)),
            )
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
            """, (
                t.get("title", ""), t.get("category", ""), t.get("address", ""),
                t.get("lat"), t.get("lng"), t.get("rating"), t.get("review_count"),
                t.get("is_public_toilet"), t.get("toilet_score"), t.get("confidence"),
                t.get("toilet_review_count"), t.get("prefecture"),
                json.dumps(t.get("sample_reviews", []), ensure_ascii=False)
            ))

    conn.commit()
    conn.close()
    logger.info(f"SQLite conversion complete: {DB_PATH}")


if __name__ == "__main__":
    incremental = "--incremental" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--incremental"]
    path = args[0] if args else "data/toilets.json.gz"
    json_to_sqlite(path, incremental=incremental)
