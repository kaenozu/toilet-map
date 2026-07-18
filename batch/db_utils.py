# mypy: disable-error-code="no-redef"
"""SQLite schema, migration and serialization helpers."""

from __future__ import annotations

import gzip
import json
import os
import sqlite3
import tempfile
from datetime import datetime

try:
    from .identity import build_source_id
    from .utils import extract_prefecture, logger
except ImportError:
    from identity import build_source_id
    from utils import extract_prefecture, logger

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "toilets.db")
JSON_PATH = os.path.join(PROJECT_ROOT, "data", "toilets.json.gz")

TOILET_TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS toilets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT,
    title TEXT,
    category TEXT,
    address TEXT,
    lat REAL,
    lng REAL,
    phone TEXT,
    rating REAL,
    review_count INTEGER,
    link TEXT,
    is_public_toilet BOOLEAN,
    toilet_score REAL,
    confidence REAL,
    toilet_review_count INTEGER,
    prefecture TEXT,
    sample_reviews_json TEXT,
    top_keywords TEXT
)
"""
METADATA_TABLE_SCHEMA = "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)"
INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_pref ON toilets(prefecture)",
    "CREATE INDEX IF NOT EXISTS idx_score ON toilets(toilet_score)",
]
SOURCE_ID_UNIQUE_INDEX = "CREATE UNIQUE INDEX IF NOT EXISTS ux_toilets_key ON toilets(source_id)"
TOILET_UNIQUE_INDEX = SOURCE_ID_UNIQUE_INDEX
REQUIRED_COLUMNS = {"source_id": "TEXT", "phone": "TEXT", "link": "TEXT"}

TOILET_UPSERT_SQL = """
INSERT INTO toilets (
    source_id, title, category, address, lat, lng, phone, rating, review_count,
    link, is_public_toilet, toilet_score, confidence, toilet_review_count,
    prefecture, sample_reviews_json, top_keywords
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(source_id) DO UPDATE SET
    title = excluded.title,
    category = excluded.category,
    address = excluded.address,
    lat = excluded.lat,
    lng = excluded.lng,
    phone = excluded.phone,
    rating = excluded.rating,
    review_count = excluded.review_count,
    link = excluded.link,
    is_public_toilet = excluded.is_public_toilet,
    toilet_score = excluded.toilet_score,
    confidence = excluded.confidence,
    toilet_review_count = excluded.toilet_review_count,
    prefecture = excluded.prefecture,
    sample_reviews_json = excluded.sample_reviews_json,
    top_keywords = excluded.top_keywords
"""


def get_schema_sql() -> list[str]:
    return [TOILET_TABLE_SCHEMA, METADATA_TABLE_SCHEMA, *INDEXES]


def _table_columns(cur: sqlite3.Cursor, table: str = "toilets") -> set[str]:
    return {str(row[1]) for row in cur.execute(f"PRAGMA table_info({table})").fetchall()}


def _add_missing_columns(cur: sqlite3.Cursor) -> bool:
    columns = _table_columns(cur)
    changed = False
    for name, sql_type in REQUIRED_COLUMNS.items():
        if name not in columns:
            cur.execute(f"ALTER TABLE toilets ADD COLUMN {name} {sql_type}")
            changed = True
    return changed


def backfill_source_ids(cur: sqlite3.Cursor) -> int:
    rows = cur.execute("SELECT id, title, address, lat, lng, source_id FROM toilets ORDER BY id").fetchall()
    updated = 0
    for row_id, title, address, lat, lng, existing in rows:
        source_id = str(existing or "").strip()
        if not source_id:
            source_id = build_source_id({"title": title, "address": address, "lat": lat, "lng": lng})
            cur.execute("UPDATE toilets SET source_id = ? WHERE id = ?", (source_id, row_id))
            updated += 1
    return updated


def _legacy_coordinate_duplicates(cur: sqlite3.Cursor) -> int:
    return cur.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT ROUND(lat, 5), ROUND(lng, 5), COUNT(*) AS count
            FROM toilets
            WHERE lat IS NOT NULL AND lng IS NOT NULL
            GROUP BY ROUND(lat, 5), ROUND(lng, 5)
            HAVING count > 1
        )
        """
    ).fetchone()[0]


def dedupe_duplicate_toilets(cur: sqlite3.Cursor) -> int:
    """Deduplicate stable IDs; legacy rows without IDs fall back to coordinates."""
    before = cur.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
    columns = _table_columns(cur)
    has_stable_ids = "source_id" in columns and cur.execute(
        "SELECT 1 FROM toilets WHERE source_id IS NOT NULL AND source_id != '' LIMIT 1"
    ).fetchone() is not None
    if has_stable_ids:
        cur.execute(
            """
            DELETE FROM toilets
            WHERE source_id IS NOT NULL AND source_id != ''
              AND id NOT IN (
                  SELECT MIN(id) FROM toilets
                  WHERE source_id IS NOT NULL AND source_id != ''
                  GROUP BY source_id
              )
            """
        )
    else:
        cur.execute(
            """
            DELETE FROM toilets
            WHERE lat IS NOT NULL AND lng IS NOT NULL
              AND id NOT IN (
                  SELECT MIN(id) FROM toilets
                  WHERE lat IS NOT NULL AND lng IS NOT NULL
                  GROUP BY ROUND(lat, 5), ROUND(lng, 5)
              )
            """
        )
    after = cur.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
    return before - after


def ensure_schema(cur: sqlite3.Cursor) -> None:
    cur.execute(TOILET_TABLE_SCHEMA)
    cur.execute(METADATA_TABLE_SCHEMA)
    migrated = _add_missing_columns(cur)
    cur.execute("DROP INDEX IF EXISTS ux_toilets_key")
    cur.execute("DROP INDEX IF EXISTS ux_toilets_source_id")
    if migrated:
        dedupe_duplicate_toilets(cur)
        if _legacy_coordinate_duplicates(cur):
            raise sqlite3.IntegrityError("legacy coordinate duplicates remain")
    backfill_source_ids(cur)
    dedupe_duplicate_toilets(cur)
    for sql in INDEXES:
        cur.execute(sql)
    cur.execute(SOURCE_ID_UNIQUE_INDEX)


def database_requires_rebuild(db_path: str = DB_PATH) -> bool:
    if not os.path.exists(db_path):
        return True
    try:
        conn = sqlite3.connect(db_path)
        try:
            columns = _table_columns(conn.cursor())
            return not set(REQUIRED_COLUMNS).issubset(columns)
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        return True


def ensure_database_current(json_path: str = JSON_PATH, db_path: str = DB_PATH) -> None:
    if not database_requires_rebuild(db_path):
        return
    if not os.path.exists(json_path):
        raise FileNotFoundError(json_path)
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    fd, temp_db = tempfile.mkstemp(prefix=".toilets-migration-", suffix=".db", dir=os.path.dirname(db_path))
    os.close(fd)
    try:
        os.remove(temp_db)
        try:
            from .to_sqlite import _convert_core
        except ImportError:
            from to_sqlite import _convert_core
        _convert_core(json_path, temp_db, incremental=False)
        os.replace(temp_db, db_path)
        logger.info(f"Rebuilt outdated SQLite database from {json_path}")
    finally:
        if os.path.exists(temp_db):
            os.remove(temp_db)


def toilet_db_values(toilet: dict) -> tuple:
    """Historical 14-field tuple retained for external callers and tests."""
    address = str(toilet.get("address") or "")
    prefecture = toilet.get("prefecture") or extract_prefecture(address)
    return (
        toilet.get("title", ""), toilet.get("category", ""), address,
        toilet.get("lat"), toilet.get("lng"), toilet.get("rating"),
        toilet.get("review_count"), toilet.get("is_public_toilet"),
        toilet.get("toilet_score"), toilet.get("confidence"),
        toilet.get("toilet_review_count"), prefecture,
        reviews_to_json(toilet.get("sample_reviews", [])),
        keywords_to_json(toilet.get("top_keywords", [])),
    )


def _toilet_db_values_v2(toilet: dict) -> tuple:
    address = str(toilet.get("address") or "")
    prefecture = toilet.get("prefecture") or extract_prefecture(address)
    source_id = build_source_id(toilet)
    return (
        source_id, toilet.get("title", ""), toilet.get("category", ""), address,
        toilet.get("lat"), toilet.get("lng"), toilet.get("phone", ""),
        toilet.get("rating"), toilet.get("review_count"), toilet.get("link", ""),
        toilet.get("is_public_toilet"), toilet.get("toilet_score"),
        toilet.get("confidence"), toilet.get("toilet_review_count"), prefecture,
        reviews_to_json(toilet.get("sample_reviews", [])),
        keywords_to_json(toilet.get("top_keywords", [])),
    )


def upsert_toilets(cur: sqlite3.Cursor, toilets: list[dict]) -> None:
    cur.executemany(TOILET_UPSERT_SQL, (_toilet_db_values_v2(toilet) for toilet in toilets))


def fix_null_prefectures(conn: sqlite3.Connection) -> int:
    cur = conn.cursor()
    rows = cur.execute("SELECT id, address FROM toilets WHERE prefecture IS NULL OR prefecture = ''").fetchall()
    fixed = 0
    for row_id, address in rows:
        prefecture = extract_prefecture(address or "")
        if prefecture:
            cur.execute("UPDATE toilets SET prefecture = ? WHERE id = ?", (prefecture, row_id))
            fixed += 1
    return fixed


def update_metadata_from_db(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    total = cur.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
    scored = cur.execute("SELECT COUNT(*) FROM toilets WHERE confidence > 0").fetchone()[0]
    public = cur.execute("SELECT COUNT(*) FROM toilets WHERE is_public_toilet = 1").fetchone()[0]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = cur.execute("SELECT value FROM metadata WHERE key = 'last_updated'").fetchone()
    last_updated = row[0] if row and row[0] else now
    for key, value in [
        ("total", str(total)),
        ("scored", str(scored)),
        ("public_toilets", str(public)),
        ("last_updated", last_updated),
        ("db_synced_at", now),
    ]:
        cur.execute(
            "INSERT INTO metadata (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def upsert_metadata(cur: sqlite3.Cursor, metadata: dict) -> None:
    for key, value in metadata.items():
        cur.execute(
            "INSERT INTO metadata (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )


def load_json(path: str) -> dict:
    if path.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as file:
            return json.load(file)
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def reviews_to_json(reviews: list) -> str:
    return json.dumps(reviews, ensure_ascii=False)


def keywords_to_json(keywords: list) -> str:
    return json.dumps(keywords, ensure_ascii=False)
