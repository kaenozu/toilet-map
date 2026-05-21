"""
batch/db_utils.py
SQLite 共通ユーティリティ (to_sqlite.py, merge_to_db.py で共用)
"""
import gzip
import json
import os
import sqlite3
from datetime import datetime

from utils import extract_prefecture

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "toilets.db")


TOILET_TABLE_SCHEMA = """
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
        sample_reviews_json TEXT,
        top_keywords TEXT,
        equipment TEXT
    )
"""

METADATA_TABLE_SCHEMA = """
    CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_pref ON toilets(prefecture)",
    "CREATE INDEX IF NOT EXISTS idx_score ON toilets(toilet_score)",
]

TOILET_UNIQUE_INDEX = "CREATE UNIQUE INDEX IF NOT EXISTS ux_toilets_key ON toilets(lat, lng)"

TOILET_UPSERT_SQL = """
    INSERT INTO toilets (
        title, category, address, lat, lng, rating, review_count,
        is_public_toilet, toilet_score, confidence, toilet_review_count,
        prefecture, sample_reviews_json, top_keywords, equipment
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(lat, lng) DO UPDATE SET
        title = excluded.title,
        category = excluded.category,
        address = excluded.address,
        rating = excluded.rating,
        review_count = excluded.review_count,
        is_public_toilet = excluded.is_public_toilet,
        toilet_score = excluded.toilet_score,
        confidence = excluded.confidence,
        toilet_review_count = excluded.toilet_review_count,
        prefecture = excluded.prefecture,
        sample_reviews_json = excluded.sample_reviews_json,
        top_keywords = excluded.top_keywords,
        equipment = excluded.equipment
"""


def get_schema_sql() -> list[str]:
    return [TOILET_TABLE_SCHEMA, METADATA_TABLE_SCHEMA] + INDEXES


def dedupe_duplicate_toilets(cur: sqlite3.Cursor) -> int:
    """既存の重複行を座標単位で 1 件にまとめる。"""
    before = cur.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
    cur.execute(
        """
        DELETE FROM toilets
        WHERE lat IS NOT NULL
          AND lng IS NOT NULL
          AND id NOT IN (
              SELECT MIN(id)
              FROM toilets
              WHERE lat IS NOT NULL
                AND lng IS NOT NULL
              GROUP BY ROUND(lat, 5), ROUND(lng, 5)
          )
        """
    )
    after = cur.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
    return before - after


def _migrate_schema(cur: sqlite3.Cursor) -> None:
    """Add missing columns from schema upgrades."""
    existing = {row[1] for row in cur.execute("PRAGMA table_info(toilets)")}
    for col_name, col_type in [("top_keywords", "TEXT"), ("equipment", "TEXT")]:
        if col_name not in existing:
            cur.execute(f"ALTER TABLE toilets ADD COLUMN {col_name} {col_type}")


def ensure_schema(cur: sqlite3.Cursor) -> None:
    for sql in (TOILET_TABLE_SCHEMA, METADATA_TABLE_SCHEMA):
        cur.execute(sql)
    for sql in INDEXES:
        cur.execute(sql)
    _migrate_schema(cur)
    for _ in range(3):
        try:
            cur.execute(TOILET_UNIQUE_INDEX)
            return
        except sqlite3.IntegrityError:
            removed = dedupe_duplicate_toilets(cur)
            if removed == 0:
                raise


def fix_null_prefectures(conn: sqlite3.Connection) -> int:
    """prefecture が NULL または空文字の行を住所から修復"""
    cur = conn.cursor()
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


def update_metadata_from_db(conn: sqlite3.Connection) -> None:
    """DBの内容から metadata テーブルを更新"""
    cur = conn.cursor()
    total = cur.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
    scored = cur.execute("SELECT COUNT(*) FROM toilets WHERE confidence > 0").fetchone()[0]
    public = cur.execute("SELECT COUNT(*) FROM toilets WHERE is_public_toilet = 1").fetchone()[0]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_updated_row = cur.execute("SELECT value FROM metadata WHERE key = 'last_updated'").fetchone()
    last_updated = last_updated_row[0] if last_updated_row and last_updated_row[0] else now

    for key, value in [
        ("total", str(total)),
        ("scored", str(scored)),
        ("public_toilets", str(public)),
        ("last_updated", last_updated),
        ("db_synced_at", now),
    ]:
        cur.execute(
            "INSERT INTO metadata (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def upsert_metadata(cur: sqlite3.Cursor, metadata: dict) -> None:
    """metadata テーブルへ key/value を upsert する"""
    for key, value in metadata.items():
        cur.execute(
            "INSERT INTO metadata (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )


def load_json(path: str) -> dict:
    """JSON (gz対応) を読み込む"""
    if path.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def reviews_to_json(reviews: list) -> str:
    return json.dumps(reviews, ensure_ascii=False)


def keywords_to_json(keywords: list) -> str:
    return json.dumps(keywords, ensure_ascii=False)


def upsert_toilets(cur: sqlite3.Cursor, toilets: list[dict]) -> None:
    """toilets テーブルへまとめて upsert する"""
    cur.executemany(TOILET_UPSERT_SQL, (toilet_db_values(toilet) for toilet in toilets))


def toilet_db_values(toilet: dict) -> tuple:
    """toilets テーブルに書き込む列の値をまとめて返す"""
    address = toilet.get("address", "")
    prefecture = toilet.get("prefecture") or extract_prefecture(address)
    return (
        toilet.get("title", ""),
        toilet.get("category", ""),
        address,
        toilet.get("lat"),
        toilet.get("lng"),
        toilet.get("rating"),
        toilet.get("review_count"),
        toilet.get("is_public_toilet"),
        toilet.get("toilet_score"),
        toilet.get("confidence"),
        toilet.get("toilet_review_count"),
        prefecture,
        reviews_to_json(toilet.get("sample_reviews", [])),
        keywords_to_json(toilet.get("top_keywords", [])),
        keywords_to_json(toilet.get("equipment", [])),
    )
