"""
batch/to_sqlite.py
JSON データを SQLite データベースに変換し、検索と読み込みを高速化する。
"""
import sqlite3
import json
import gzip
from utils import logger

DB_PATH = "data/toilets.db"

def json_to_sqlite(json_path: str) -> None:
    logger.info(f"Converting {json_path} to SQLite...")
    
    if json_path.endswith(".gz"):
        with gzip.open(json_path, "rt", encoding="utf-8") as f:
            data = json.load(f)
    else:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

    metadata = data["metadata"]
    toilets = data["toilets"]

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # テーブル作成
    cur.execute("DROP TABLE IF EXISTS toilets")
    cur.execute("""
        CREATE TABLE toilets (
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
    
    cur.execute("DROP TABLE IF EXISTS metadata")
    cur.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")

    # メタデータ保存
    for k, v in metadata.items():
        cur.execute("INSERT INTO metadata (key, value) VALUES (?, ?)", (k, str(v)))

    # トイレデータ保存
    for t in toilets:
        cur.execute("""
            INSERT INTO toilets (
                title, category, address, lat, lng, rating, review_count,
                is_public_toilet, toilet_score, confidence, toilet_review_count,
                prefecture, sample_reviews_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            t["title"], t["category"], t["address"], t.get("lat"), t.get("lng"),
            t.get("rating"), t.get("review_count"), t.get("is_public_toilet"),
            t.get("toilet_score"), t.get("confidence"), t.get("toilet_review_count"),
            t.get("prefecture"), json.dumps(t.get("sample_reviews", []))
        ))

    # インデックス
    cur.execute("CREATE INDEX idx_pref ON toilets(prefecture)")
    cur.execute("CREATE INDEX idx_score ON toilets(toilet_score)")

    conn.commit()
    conn.close()
    logger.info(f"SQLite conversion complete: {DB_PATH}")

if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "data/toilets.json.gz"
    json_to_sqlite(path)
