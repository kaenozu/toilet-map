"""
batch/merge_to_db.py
JSON データを既存 SQLite にマージし、都道府県 NULL を修復する。

関連ファイル:
  - batch/to_sqlite.py (フルリプレース版)
  - batch/scoring_config.py (PREFECTURES)
  - data/toilets.db (出力 DB)
  - data/toilets.json.gz (入力 JSON)
"""
import sqlite3
import json
import gzip
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from scoring_config import PREFECTURES
from utils import logger

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "toilets.db")


def extract_prefecture(address: str) -> str:
    if not address:
        return ""
    for pref in PREFECTURES:
        if pref in address:
            return pref
    return ""


def load_json(path: str) -> dict:
    if path.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    else:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


def ensure_schema(cur: sqlite3.Cursor) -> None:
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


def fix_prefectures(cur: sqlite3.Cursor) -> int:
    rows = cur.execute(
        "SELECT id, address FROM toilets WHERE prefecture IS NULL OR prefecture = ''"
    ).fetchall()
    fixed = 0
    for row_id, address in rows:
        pref = extract_prefecture(address or "")
        if pref:
            cur.execute("UPDATE toilets SET prefecture = ? WHERE id = ?", (pref, row_id))
            fixed += 1
    return fixed


def upsert_toilets(cur: sqlite3.Cursor, toilets: list[dict]) -> tuple[int, int]:
    new_count = 0
    updated_count = 0
    for t in toilets:
        title = t.get("title", "")
        lat = t.get("lat")
        lng = t.get("lng")
        address = t.get("address", "")
        prefecture = t.get("prefecture") or extract_prefecture(address)
        reviews_json = json.dumps(t.get("sample_reviews", []), ensure_ascii=False)

        existing = cur.execute(
            "SELECT id FROM toilets WHERE title = ? AND lat = ? AND lng = ?",
            (title, lat, lng),
        ).fetchone()

        if existing:
            cur.execute("""
                UPDATE toilets SET
                    category = ?, address = ?, rating = ?, review_count = ?,
                    is_public_toilet = ?, toilet_score = ?, confidence = ?,
                    toilet_review_count = ?, prefecture = ?, sample_reviews_json = ?
                WHERE id = ?
            """, (
                t.get("category"), address, t.get("rating"), t.get("review_count"),
                t.get("is_public_toilet"), t.get("toilet_score"), t.get("confidence"),
                t.get("toilet_review_count"), prefecture, reviews_json, existing[0],
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
    return new_count, updated_count


def update_metadata(cur: sqlite3.Cursor) -> None:
    total = cur.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
    scored = cur.execute("SELECT COUNT(*) FROM toilets WHERE confidence > 0").fetchone()[0]
    public = cur.execute("SELECT COUNT(*) FROM toilets WHERE is_public_toilet = 1").fetchone()[0]
    now = datetime.now().strftime("%Y-%m-%d")

    for key, value in [
        ("total", str(total)),
        ("scored", str(scored)),
        ("public_toilets", str(public)),
        ("last_updated", now),
    ]:
        cur.execute(
            "INSERT INTO metadata (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def merge(json_path: str, db_path: str = DB_PATH) -> None:
    logger.info(f"Loading JSON: {json_path}")
    data = load_json(json_path)
    toilets = data.get("toilets", [])
    logger.info(f"JSON toilets: {len(toilets)}")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    ensure_schema(cur)

    logger.info("Fixing prefecture=NULL rows...")
    fixed = fix_prefectures(cur)
    logger.info(f"Fixed {fixed} prefecture entries")

    logger.info("Merging toilets (UPSERT by title+lat+lng)...")
    new_count, updated_count = upsert_toilets(cur, toilets)
    logger.info(f"Merged: +{new_count} new, ~{updated_count} updated")

    update_metadata(cur)

    conn.commit()
    total = cur.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
    null_pref = cur.execute("SELECT COUNT(*) FROM toilets WHERE prefecture IS NULL OR prefecture = ''").fetchone()[0]
    conn.close()

    logger.info(f"Done: {total} total toilets, {null_pref} remaining NULL prefecture")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/toilets.json.gz"
    merge(path)
