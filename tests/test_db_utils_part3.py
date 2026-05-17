"""
tests/test_db_utils.py
batch/db_utils.py のユニットテスト（インメモリ SQLite + tmp_path）
dedupe_duplicate_toilets, ensure_schema, load_json, upsert_toilets,
toilet_db_values, update_metadata_from_db, upsert_metadata 等

関連: batch/db_utils.py, tests/test_batch_db_operations.py
"""

import sqlite3

import db_utils
import pytest


class TestUpsertToilets:
    def test_inserts_new_rows(self):
        conn = sqlite3.connect(":memory:")
        try:
            cur = conn.cursor()
            db_utils.ensure_schema(cur)
            toilets = [
                {"title": "A", "category": "公園", "address": "東京都",
                 "lat": 35.0, "lng": 139.0, "rating": 4.0, "review_count": 10,
                 "is_public_toilet": False, "toilet_score": 80.0, "confidence": 0.8,
                 "toilet_review_count": 2, "prefecture": "東京都", "sample_reviews": []},
                {"title": "B", "category": "駅", "address": "大阪府",
                 "lat": 34.0, "lng": 135.0, "rating": 3.0, "review_count": 5,
                 "is_public_toilet": True, "toilet_score": 60.0, "confidence": 0.5,
                 "toilet_review_count": 1, "prefecture": "大阪府", "sample_reviews": []},
            ]
            db_utils.upsert_toilets(cur, toilets)
            count = cur.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
            assert count == 2
        finally:
            conn.close()

    def test_updates_existing_row_by_unique_key(self):
        conn = sqlite3.connect(":memory:")
        try:
            cur = conn.cursor()
            db_utils.ensure_schema(cur)
            toilet = {
                "title": "A", "category": "公園", "address": "東京都",
                "lat": 35.0, "lng": 139.0, "rating": 4.0, "review_count": 10,
                "is_public_toilet": False, "toilet_score": 80.0, "confidence": 0.8,
                "toilet_review_count": 2, "prefecture": "東京都", "sample_reviews": [],
            }
            db_utils.upsert_toilets(cur, [toilet])
            updated = {**toilet, "category": "更新済", "toilet_score": 95.0}
            db_utils.upsert_toilets(cur, [updated])
            count = cur.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
            assert count == 1
            cat = cur.execute("SELECT category FROM toilets WHERE title = 'A'").fetchone()[0]
            assert cat == "更新済"
        finally:
            conn.close()

    def test_empty_list_does_nothing(self):
        conn = sqlite3.connect(":memory:")
        try:
            cur = conn.cursor()
            db_utils.ensure_schema(cur)
            db_utils.upsert_toilets(cur, [])
            count = cur.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
            assert count == 0
        finally:
            conn.close()

    def test_prefecture_auto_filled_from_address(self):
        conn = sqlite3.connect(":memory:")
        try:
            cur = conn.cursor()
            db_utils.ensure_schema(cur)
            toilet = {
                "title": "A", "category": "公園", "address": "大阪府大阪市",
                "lat": 34.0, "lng": 135.0, "rating": 3.0, "review_count": 5,
                "is_public_toilet": False, "toilet_score": 60.0, "confidence": 0.5,
                "toilet_review_count": 1, "prefecture": None, "sample_reviews": [],
            }
            db_utils.upsert_toilets(cur, [toilet])
            pref = cur.execute("SELECT prefecture FROM toilets").fetchone()[0]
            assert pref == "大阪府"
        finally:
            conn.close()



class TestUpsertMetadata:
    def test_inserts_new_key_values(self):
        conn = sqlite3.connect(":memory:")
        try:
            cur = conn.cursor()
            conn.execute(db_utils.METADATA_TABLE_SCHEMA)
            db_utils.upsert_metadata(cur, {"area_name": "テスト", "total": "10"})
            rows = dict(cur.execute("SELECT key, value FROM metadata").fetchall())
            assert rows["area_name"] == "テスト"
            assert rows["total"] == "10"
        finally:
            conn.close()

    def test_updates_existing_key(self):
        conn = sqlite3.connect(":memory:")
        try:
            cur = conn.cursor()
            conn.execute(db_utils.METADATA_TABLE_SCHEMA)
            db_utils.upsert_metadata(cur, {"area_name": "旧"})
            db_utils.upsert_metadata(cur, {"area_name": "新"})
            rows = dict(cur.execute("SELECT key, value FROM metadata").fetchall())
            assert rows["area_name"] == "新"
        finally:
            conn.close()

    def test_empty_dict_does_nothing(self):
        conn = sqlite3.connect(":memory:")
        try:
            cur = conn.cursor()
            conn.execute(db_utils.METADATA_TABLE_SCHEMA)
            db_utils.upsert_metadata(cur, {})
            count = cur.execute("SELECT COUNT(*) FROM metadata").fetchone()[0]
            assert count == 0
        finally:
            conn.close()

    def test_converts_values_to_string(self):
        conn = sqlite3.connect(":memory:")
        try:
            cur = conn.cursor()
            conn.execute(db_utils.METADATA_TABLE_SCHEMA)
            db_utils.upsert_metadata(cur, {"total": 42, "ratio": 0.5})
            rows = dict(cur.execute("SELECT key, value FROM metadata").fetchall())
            assert rows["total"] == "42"
            assert rows["ratio"] == "0.5"
        finally:
            conn.close()



class TestUpdateMetadataFromDb:
    def test_populates_metadata_table(self):
        conn = sqlite3.connect(":memory:")
        try:
            _create_table(conn)
            _insert_toilet(conn)
            _insert_toilet(conn, title="トイレB", address="大阪府大阪市", prefecture="大阪府",
                            lat=34.0, lng=135.0, is_public_toilet=0, confidence=0.0)
            conn.commit()
            db_utils.update_metadata_from_db(conn)
            rows = dict(conn.execute("SELECT key, value FROM metadata").fetchall())
            assert rows["total"] == "2"
            assert rows["scored"] == "1"
            assert rows["public_toilets"] == "1"
            assert "db_synced_at" in rows
        finally:
            conn.close()

    def test_empty_table(self):
        conn = sqlite3.connect(":memory:")
        try:
            _create_table(conn)
            db_utils.update_metadata_from_db(conn)
            rows = dict(conn.execute("SELECT key, value FROM metadata").fetchall())
            assert rows["total"] == "0"
            assert rows["scored"] == "0"
            assert rows["public_toilets"] == "0"
        finally:
            conn.close()

    def test_preserves_existing_last_updated(self):
        conn = sqlite3.connect(":memory:")
        try:
            _create_table(conn)
            _insert_toilet(conn)
            conn.execute(
                "INSERT INTO metadata (key, value) VALUES (?, ?)",
                ("last_updated", "2026-05-10 12:00:00"),
            )
            conn.commit()
            db_utils.update_metadata_from_db(conn)
            lu = conn.execute(
                "SELECT value FROM metadata WHERE key = 'last_updated'"
            ).fetchone()[0]
            assert lu == "2026-05-10 12:00:00"
        finally:
            conn.close()



class TestEnsureSchemaRetry:
    def test_succeeds_after_dedup(self, monkeypatch):
        conn = sqlite3.connect(":memory:")
        try:
            cur = conn.cursor()
            cur.execute("CREATE TABLE toilets (id INTEGER PRIMARY KEY, lat REAL, lng REAL, title TEXT, category TEXT, address TEXT, rating REAL, review_count INTEGER, is_public_toilet BOOLEAN, toilet_score REAL, confidence REAL, toilet_review_count INTEGER, prefecture TEXT, sample_reviews_json TEXT, top_keywords TEXT)")
            cur.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
            cur.execute("INSERT INTO toilets (lat, lng, title) VALUES (35.0, 139.0, 'A')")
            cur.execute("INSERT INTO toilets (lat, lng, title) VALUES (35.0, 139.0, 'B')")
            db_utils.ensure_schema(cur)
            count = cur.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
            assert count == 1
        finally:
            conn.close()

    def test_raises_on_zero_deduped(self, monkeypatch):
        conn = sqlite3.connect(":memory:")
        try:
            cur = conn.cursor()
            cur.execute("CREATE TABLE toilets (id INTEGER PRIMARY KEY, lat REAL, lng REAL, title TEXT, category TEXT, address TEXT, rating REAL, review_count INTEGER, is_public_toilet BOOLEAN, toilet_score REAL, confidence REAL, toilet_review_count INTEGER, prefecture TEXT, sample_reviews_json TEXT, top_keywords TEXT)")
            cur.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
            cur.execute("INSERT INTO toilets (lat, lng, title) VALUES (35.0, 139.0, 'A')")
            cur.execute("INSERT INTO toilets (lat, lng, title) VALUES (35.0, 139.0, 'B')")
            monkeypatch.setattr(db_utils, "dedupe_duplicate_toilets", lambda cur: 0)
            with pytest.raises(sqlite3.IntegrityError):
                db_utils.ensure_schema(cur)
        finally:
            conn.close()

def _create_table(conn):
    conn.execute(db_utils.TOILET_TABLE_SCHEMA)
    conn.execute(db_utils.METADATA_TABLE_SCHEMA)
    conn.commit()



def _insert_toilet(conn, **overrides):
    values = {
        "title": "テストトイレ",
        "category": "公園",
        "address": "東京都渋谷区",
        "lat": 35.68,
        "lng": 139.69,
        "rating": 4.0,
        "review_count": 10,
        "is_public_toilet": 1,
        "toilet_score": 80.0,
        "confidence": 0.8,
        "toilet_review_count": 2,
        "prefecture": "東京都",
        "sample_reviews_json": "[]",
    }
    values.update(overrides)
    conn.execute(
        "INSERT INTO toilets (title, category, address, lat, lng, rating, review_count, "
        "is_public_toilet, toilet_score, confidence, toilet_review_count, prefecture, sample_reviews_json) "
        "VALUES (:title, :category, :address, :lat, :lng, :rating, :review_count, "
        ":is_public_toilet, :toilet_score, :confidence, :toilet_review_count, :prefecture, :sample_reviews_json)",
        values,
    )



