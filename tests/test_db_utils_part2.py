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
        assert len(values) == 15


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
        assert len(values) == 15
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



