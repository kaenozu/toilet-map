from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS places (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_place_id TEXT,
    title TEXT NOT NULL,
    category TEXT,
    address TEXT,
    latitude REAL NOT NULL CHECK(latitude BETWEEN -90 AND 90),
    longitude REAL NOT NULL CHECK(longitude BETWEEN -180 AND 180),
    external_url TEXT,
    overall_rating REAL,
    overall_review_count INTEGER,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    UNIQUE(source, source_place_id)
);
CREATE TABLE IF NOT EXISTS toilets (
    id TEXT PRIMARY KEY,
    place_id TEXT NOT NULL REFERENCES places(id) ON DELETE CASCADE,
    toilet_type TEXT NOT NULL DEFAULT 'unknown',
    score REAL CHECK(score BETWEEN 0 AND 100),
    confidence REAL NOT NULL DEFAULT 0 CHECK(confidence BETWEEN 0 AND 1),
    review_count INTEGER NOT NULL DEFAULT 0 CHECK(review_count >= 0),
    score_status TEXT NOT NULL,
    scoring_version TEXT NOT NULL,
    scored_at TEXT,
    UNIQUE(place_id, toilet_type)
);
CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    place_id TEXT NOT NULL REFERENCES places(id) ON DELETE CASCADE,
    source_review_id TEXT,
    text TEXT NOT NULL,
    rating REAL,
    posted_at TEXT,
    collected_at TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    is_toilet_related INTEGER NOT NULL CHECK(is_toilet_related IN (0, 1)),
    UNIQUE(place_id, content_hash)
);
CREATE TABLE IF NOT EXISTS migration_rejections (
    id INTEGER PRIMARY KEY,
    source_index INTEGER NOT NULL,
    reason TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    rejected_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_places_location ON places(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_places_active ON places(is_active);
CREATE INDEX IF NOT EXISTS idx_toilets_score ON toilets(score_status, score);
CREATE INDEX IF NOT EXISTS idx_reviews_place ON reviews(place_id);
CREATE INDEX IF NOT EXISTS idx_rejections_reason ON migration_rejections(reason);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(Path(path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize(path: str | Path) -> None:
    database_path = Path(path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(database_path) as connection:
        connection.executescript(SCHEMA_SQL)
        connection.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
