"""
tests/test_db_utils.py
batch/db_utils.py のユニットテスト（インメモリ SQLite + tmp_path）
dedupe_duplicate_toilets, ensure_schema, load_json, upsert_toilets,
toilet_db_values, update_metadata_from_db, upsert_metadata 等

関連: batch/db_utils.py, tests/test_batch_db_operations.py
"""

import sqlite3

import db_utils


class TestGetSchemaSql:
    def test_returns_list_of_sql_strings(self):
        schema = db_utils.get_schema_sql()
        assert len(schema) == 4
        assert all(isinstance(s, str) for s in schema)

    def test_includes_toilet_table(self):
        schema = db_utils.get_schema_sql()
        assert any("CREATE TABLE IF NOT EXISTS toilets" in s for s in schema)

    def test_includes_indexes(self):
        schema = db_utils.get_schema_sql()
        assert any("idx_pref" in s for s in schema)
        assert any("idx_score" in s for s in schema)



class TestDedupeDuplicateToilets:
    def test_no_duplicates_returns_zero(self):
        conn = sqlite3.connect(":memory:")
        try:
            _create_table(conn)
            _insert_toilet(conn)
            _insert_toilet(conn, title="別のトイレ", lat=35.70, lng=139.71)
            conn.commit()
            cur = conn.cursor()
            removed = db_utils.dedupe_duplicate_toilets(cur)
            assert removed == 0
        finally:
            conn.close()

    def test_removes_duplicate_coordinates(self):
        conn = sqlite3.connect(":memory:")
        try:
            _create_table(conn)
            _insert_toilet(conn)
            _insert_toilet(conn, title="重複トイレ")
            conn.commit()
            cur = conn.cursor()
            removed = db_utils.dedupe_duplicate_toilets(cur)
            assert removed == 1
            remaining = cur.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
            assert remaining == 1
        finally:
            conn.close()

    def test_keeps_first_occurrence(self):
        conn = sqlite3.connect(":memory:")
        try:
            _create_table(conn)
            _insert_toilet(conn, title="オリジナル")
            _insert_toilet(conn, title="重複", category="更新後")
            conn.commit()
            cur = conn.cursor()
            db_utils.dedupe_duplicate_toilets(cur)
            title = cur.execute("SELECT title FROM toilets").fetchone()[0]
            assert title == "オリジナル"
        finally:
            conn.close()

    def test_multiple_duplicates_of_same_point(self):
        conn = sqlite3.connect(":memory:")
        try:
            _create_table(conn)
            for i in range(5):
                _insert_toilet(conn, title=f"重複{i}")
            conn.commit()
            cur = conn.cursor()
            removed = db_utils.dedupe_duplicate_toilets(cur)
            assert removed == 4
            remaining = cur.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
            assert remaining == 1
        finally:
            conn.close()

    def test_null_coordinates_not_affected(self):
        conn = sqlite3.connect(":memory:")
        try:
            _create_table(conn)
            _insert_toilet(conn, lat=None, lng=None)
            _insert_toilet(conn, title="トイレB", lat=None, lng=None)
            conn.commit()
            cur = conn.cursor()
            removed = db_utils.dedupe_duplicate_toilets(cur)
            assert removed == 0
            remaining = cur.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
            assert remaining == 2
        finally:
            conn.close()

    def test_empty_table_returns_zero(self):
        conn = sqlite3.connect(":memory:")
        try:
            _create_table(conn)
            cur = conn.cursor()
            removed = db_utils.dedupe_duplicate_toilets(cur)
            assert removed == 0
        finally:
            conn.close()



class TestEnsureSchema:
    def test_creates_tables(self):
        conn = sqlite3.connect(":memory:")
        try:
            cur = conn.cursor()
            db_utils.ensure_schema(cur)
            tables = cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            table_names = [t[0] for t in tables]
            assert "toilets" in table_names
            assert "metadata" in table_names
        finally:
            conn.close()

    def test_creates_indexes(self):
        conn = sqlite3.connect(":memory:")
        try:
            cur = conn.cursor()
            db_utils.ensure_schema(cur)
            indexes = cur.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
            ).fetchall()
            index_names = [ix[0] for ix in indexes]
            assert "idx_pref" in index_names
            assert "idx_score" in index_names
        finally:
            conn.close()

    def test_creates_unique_index(self):
        conn = sqlite3.connect(":memory:")
        try:
            cur = conn.cursor()
            db_utils.ensure_schema(cur)
            indexes = cur.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='ux_toilets_key'"
            ).fetchall()
            assert len(indexes) == 1
        finally:
            conn.close()

    def test_idempotent(self):
        conn = sqlite3.connect(":memory:")
        try:
            cur = conn.cursor()
            db_utils.ensure_schema(cur)
            db_utils.ensure_schema(cur)
            db_utils.ensure_schema(cur)
            assert True
        finally:
            conn.close()

    def test_idempotent_with_duplicate_data(self):
        conn = sqlite3.connect(":memory:")
        try:
            cur = conn.cursor()
            cur.execute(db_utils.TOILET_TABLE_SCHEMA)
            cur.execute(db_utils.METADATA_TABLE_SCHEMA)
            _insert_toilet(conn, title="同タイトル", lat=35.68, lng=139.69)
            _insert_toilet(conn, title="同タイトル", lat=35.68, lng=139.69)
            conn.commit()
            db_utils.ensure_schema(cur)
            count = cur.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
            assert count == 1
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



