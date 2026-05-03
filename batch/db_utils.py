"""
batch/db_utils.py
SQLite 共通ユーティリティ (to_sqlite.py, merge_to_db.py で共用)
"""
import sqlite3
import json
import gzip
import os
import sys
from datetime import datetime
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "toilets.db")

sys.path.insert(0, os.path.dirname(__file__))
from scoring_config import PREFECTURES

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
        sample_reviews_json TEXT
    )
"""

METADATA_TABLE_SCHEMA = """
    CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_pref ON toilets(prefecture)",
    "CREATE INDEX IF NOT EXISTS idx_score ON toilets(toilet_score)",
]


def get_schema_sql() -> list[str]:
    return [TOILET_TABLE_SCHEMA, METADATA_TABLE_SCHEMA] + INDEXES


def ensure_schema(cur: sqlite3.Cursor) -> None:
    for sql in get_schema_sql():
        cur.execute(sql)


def extract_prefecture(address: str) -> str:
    """住所文字列から都道府県を抽出"""
    if not address:
        return ""
    for pref in PREFECTURES:
        if pref in address:
            return pref
    return ""


def fix_null_prefectures(conn: sqlite3.Connection) -> int:
    """prefecture が NULL または空文字の行を地址から修復"""
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


def load_json(path: str) -> dict:
    """JSON (gz対応) を読み込む"""
    if path.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def reviews_to_json(reviews: list) -> str:
    return json.dumps(reviews, ensure_ascii=False)


def toilet_db_values(toilet: dict) -> tuple:
    """toilets テーブルに書き込む 13 列分の値をまとめて返す"""
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
    )


def toilet_db_update_values(toilet: dict) -> tuple:
    """toilets テーブル更新用の 10 列分の値を返す"""
    values = toilet_db_values(toilet)
    return (
        values[1],  # category
        values[2],  # address
        values[5],  # rating
        values[6],  # review_count
        values[7],  # is_public_toilet
        values[8],  # toilet_score
        values[9],  # confidence
        values[10], # toilet_review_count
        values[11], # prefecture
        values[12], # sample_reviews_json
    )
