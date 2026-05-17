"""
batch/schema.py
SQLite database schema versioning and migration support.
Related: batch/to_sqlite.py, batch/verify_data.py, data/toilets.db
"""
import logging
import sqlite3

CURRENT_SCHEMA_VERSION = 1
logger = logging.getLogger(__name__)


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Read schema version from the _schema_version table."""
    try:
        row = conn.execute("SELECT version FROM _schema_version").fetchone()
        return row[0] if row else 0
    except sqlite3.OperationalError:
        return 0


def ensure_schema_version(conn: sqlite3.Connection) -> None:
    """Create _schema_version table if not present, then set version."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS _schema_version (version INTEGER NOT NULL)"
    )
    current = get_schema_version(conn)
    if current == 0:
        conn.execute("DELETE FROM _schema_version")
        conn.execute("INSERT INTO _schema_version (version) VALUES (?)", (CURRENT_SCHEMA_VERSION,))
        conn.commit()


def get_toilets_schema_sql() -> str:
    """Return the canonical CREATE TABLE statement for the toilets table."""
    return """CREATE TABLE IF NOT EXISTS toilets (
    place_id TEXT PRIMARY KEY,
    title TEXT,
    lat REAL,
    lng REAL,
    score REAL,
    review_count INTEGER,
    rating REAL,
    address TEXT,
    prefecture TEXT,
    link TEXT,
    sample_reviews_json TEXT,
    top_keywords TEXT,
    updated_at TEXT
)"""


def get_metadata_schema_sql() -> str:
    return "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)"
