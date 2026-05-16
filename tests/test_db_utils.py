"""
tests/test_db_utils.py
batch/db_utils.py のユニットテスト（インメモリ SQLite + tmp_path）
dedupe_duplicate_toilets, ensure_schema, load_json, upsert_toilets,
toilet_db_values, update_metadata_from_db, upsert_metadata 等

関連: batch/db_utils.py, tests/test_batch_db_operations.py
"""

import gzip
import json
import sqlite3

import db_utils
import pytest


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


class TestFixNullPrefectures:
    def test_fixes_from_address(self):
        conn = sqlite3.connect(":memory:")
        try:
            _create_table(conn)
            _insert_toilet(conn, address="東京都渋谷区", prefecture="")
            _insert_toilet(conn, title="トイレB", address="大阪府大阪市", prefecture=None)
            conn.commit()
            fixed = db_utils.fix_null_prefectures(conn)
            assert fixed == 2
            prefs = conn.execute("SELECT prefecture FROM toilets ORDER BY id").fetchall()
            assert prefs[0][0] == "東京都"
            assert prefs[1][0] == "大阪府"
        finally:
            conn.close()

    def test_already_fixed_returns_zero(self):
        conn = sqlite3.connect(":memory:")
        try:
            _create_table(conn)
            _insert_toilet(conn)
            _insert_toilet(conn, title="トイレB", address="大阪府大阪市", prefecture="大阪府")
            conn.commit()
            fixed = db_utils.fix_null_prefectures(conn)
            assert fixed == 0
        finally:
            conn.close()

    def test_no_address_returns_zero(self):
        conn = sqlite3.connect(":memory:")
        try:
            _create_table(conn)
            _insert_toilet(conn, address="", prefecture="")
            conn.commit()
            fixed = db_utils.fix_null_prefectures(conn)
            assert fixed == 0
        finally:
            conn.close()

    def test_non_japanese_address_no_fix(self):
        conn = sqlite3.connect(":memory:")
        try:
            _create_table(conn)
            _insert_toilet(conn, address="123 Main St", prefecture="")
            conn.commit()
            fixed = db_utils.fix_null_prefectures(conn)
            assert fixed == 0
        finally:
            conn.close()

    def test_empty_table_returns_zero(self):
        conn = sqlite3.connect(":memory:")
        try:
            _create_table(conn)
            fixed = db_utils.fix_null_prefectures(conn)
            assert fixed == 0
        finally:
            conn.close()


class TestLoadJson:
    def test_loads_json_file(self, tmp_path):
        data = {"key": "value", "num": 42}
        path = tmp_path / "data.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        result = db_utils.load_json(str(path))
        assert result == data

    def test_loads_gz_file(self, tmp_path):
        data = {"key": "value", "num": 42}
        path = tmp_path / "data.json.gz"
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump(data, f)
        result = db_utils.load_json(str(path))
        assert result == data

    def test_loads_json_array(self, tmp_path):
        data = [{"a": 1}, {"b": 2}]
        path = tmp_path / "array.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        result = db_utils.load_json(str(path))
        assert result == data

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            db_utils.load_json(str(tmp_path / "nonexistent.json"))

    def test_invalid_json_raises(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not-json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            db_utils.load_json(str(path))

    def test_empty_json(self, tmp_path):
        path = tmp_path / "empty.json"
        path.write_text("{}", encoding="utf-8")
        assert db_utils.load_json(str(path)) == {}


class TestReviewsToJson:
    def test_empty_list(self):
        assert db_utils.reviews_to_json([]) == "[]"

    def test_single_review(self):
        reviews = [{"text": "きれい", "rating": 5}]
        result = db_utils.reviews_to_json(reviews)
        assert "きれい" in result
        assert json.loads(result) == reviews

    def test_multiple_reviews(self):
        reviews = [
            {"text": "clean", "rating": 5},
            {"text": "dirty", "rating": 1},
        ]
        result = db_utils.reviews_to_json(reviews)
        parsed = json.loads(result)
        assert len(parsed) == 2

    def test_non_ascii_preserved(self):
        reviews = [{"text": "トイレがきれい"}]
        result = db_utils.reviews_to_json(reviews)
        assert "トイレ" in result


class TestToiletDbValues:
    def test_returns_13_elements(self):
        toilet = {
            "title": "A", "category": "公園", "address": "東京都",
            "lat": 35.0, "lng": 139.0,
            "rating": 3.5, "review_count": 10,
            "is_public_toilet": True,
            "toilet_score": 80.0, "confidence": 0.8,
            "toilet_review_count": 2,
            "prefecture": "東京都",
            "sample_reviews": [],
        }
        values = db_utils.toilet_db_values(toilet)
        assert len(values) == 14


    def test_prefecture_from_address_when_missing(self):
        toilet = {
            "title": "A", "category": "公衆トイレ", "address": "大阪府大阪市",
            "lat": 34.0, "lng": 135.0,
            "rating": 3.0, "review_count": 5,
            "is_public_toilet": True,
            "toilet_score": 70.0, "confidence": 0.5,
            "toilet_review_count": 1,
            "prefecture": None,
            "sample_reviews": [],
        }
        values = db_utils.toilet_db_values(toilet)
        assert values[11] == "大阪府"

    def test_missing_fields_use_defaults(self):
        values = db_utils.toilet_db_values({})
        assert len(values) == 14
        assert values[0] == ""
        assert values[3] is None

    def test_empty_sample_reviews(self):
        toilet = {
            "title": "T", "category": "C", "address": "A",
            "lat": 1.0, "lng": 2.0,
            "rating": 3.0, "review_count": 0,
            "is_public_toilet": False,
            "toilet_score": 0.0, "confidence": 0.0,
            "toilet_review_count": 0,
            "sample_reviews": [],
        }
        values = db_utils.toilet_db_values(toilet)
        assert values[12] == "[]"


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
