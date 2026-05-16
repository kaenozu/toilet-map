"""
tests/test_batch_db_operations.py
データベース操作関連の回帰テスト（test_batch_regressions.py から分割）
"""
import json
import sqlite3

import db_utils
import merge_to_db
import process_data as pd_module
import pytest
import to_sqlite


class TestSqliteReset:
    def test_full_conversion_can_run_twice(self, tmp_path, monkeypatch):
        db_path = tmp_path / "toilets.db"
        json_path = tmp_path / "toilets.json"
        payload = {
            "metadata": {"area_name": "テスト"},
            "toilets": [
                {
                    "title": "A",
                    "category": "公衆トイレ",
                    "address": "東京都渋谷区",
                    "lat": 35.68,
                    "lng": 139.69,
                    "rating": 4.0,
                    "review_count": 10,
                    "is_public_toilet": True,
                    "toilet_score": 80,
                    "confidence": 0.8,
                    "toilet_review_count": 2,
                    "prefecture": "東京都",
                    "sample_reviews": [],
                }
            ],
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        monkeypatch.setattr(to_sqlite, "DB_PATH", str(db_path))

        to_sqlite.json_to_sqlite(str(json_path), incremental=False)
        to_sqlite.json_to_sqlite(str(json_path), incremental=False)

        conn = sqlite3.connect(db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
            assert count == 1
        finally:
            conn.close()

    def test_full_conversion_collapses_duplicate_rows(self, tmp_path, monkeypatch):
        db_path = tmp_path / "toilets.db"
        json_path = tmp_path / "toilets.json"
        row = {
            "title": "A",
            "category": "公衆トイレ",
            "address": "東京都渋谷区",
            "lat": 35.68,
            "lng": 139.69,
            "rating": 4.0,
            "review_count": 10,
            "is_public_toilet": True,
            "toilet_score": 80,
            "confidence": 0.8,
            "toilet_review_count": 2,
            "prefecture": "東京都",
            "sample_reviews": [],
        }
        payload = {"metadata": {"area_name": "テスト"}, "toilets": [row, {**row, "category": "更新"}]}
        json_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        monkeypatch.setattr(to_sqlite, "DB_PATH", str(db_path))

        to_sqlite.json_to_sqlite(str(json_path), incremental=False)

        conn = sqlite3.connect(db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
            category = conn.execute("SELECT category FROM toilets WHERE title = 'A'").fetchone()[0]
            assert count == 1
            assert category == "更新"
        finally:
            conn.close()

    def test_full_conversion_merges_same_coordinates(self, tmp_path, monkeypatch):
        db_path = tmp_path / "toilets.db"
        json_path = tmp_path / "toilets.json"
        payload = {
            "metadata": {"area_name": "テスト"},
            "toilets": [
                {
                    "title": "A",
                    "category": "公衆トイレ",
                    "address": "東京都渋谷区",
                    "lat": 35.68,
                    "lng": 139.69,
                    "rating": 4.0,
                    "review_count": 10,
                    "is_public_toilet": True,
                    "toilet_score": 80,
                    "confidence": 0.8,
                    "toilet_review_count": 2,
                    "prefecture": "東京都",
                    "sample_reviews": [],
                    "top_keywords": [],
                },
                {
                    "title": "B",
                    "category": "公衆トイレ",
                    "address": "東京都渋谷区",
                    "lat": 35.68,
                    "lng": 139.69,
                    "rating": 4.2,
                    "review_count": 12,
                    "is_public_toilet": True,
                    "toilet_score": 78,
                    "confidence": 0.7,
                    "toilet_review_count": 1,
                    "prefecture": "東京都",
                    "sample_reviews": [],
                    "top_keywords": [],
                },
            ],
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        monkeypatch.setattr(to_sqlite, "DB_PATH", str(db_path))

        to_sqlite.json_to_sqlite(str(json_path), incremental=False)

        conn = sqlite3.connect(db_path)
        try:
            total = conn.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
        finally:
            conn.close()

        assert total == 1

    def test_json_to_sqlite_rejects_invalid_schema(self, tmp_path, monkeypatch):
        db_path = tmp_path / "toilets.db"
        json_path = tmp_path / "toilets.json"
        payload = {
            "metadata": {"area_name": "テスト"},
            "toilets": [
                {
                    "title": "A",
                    "category": "公衆トイレ",
                    "address": "東京都渋谷区",
                    "lat": "invalid",
                    "lng": 139.69,
                    "rating": 4.0,
                    "review_count": 10,
                    "is_public_toilet": True,
                    "toilet_score": 80,
                    "confidence": 0.8,
                    "toilet_review_count": 2,
                    "prefecture": "東京都",
                    "sample_reviews": [],
                    "top_keywords": [],
                }
            ],
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        monkeypatch.setattr(to_sqlite, "DB_PATH", str(db_path))

        with pytest.raises(ValueError, match="invalid lat"):
            to_sqlite.json_to_sqlite(str(json_path), incremental=False)

    def test_incremental_conversion_updates_existing_row(self, tmp_path, monkeypatch):
        db_path = tmp_path / "toilets.db"
        json_path = tmp_path / "toilets.json"
        original = {
            "title": "A",
            "category": "公衆トイレ",
            "address": "東京都渋谷区",
            "lat": 35.68,
            "lng": 139.69,
            "rating": 4.0,
            "review_count": 10,
            "is_public_toilet": True,
            "toilet_score": 80,
            "confidence": 0.8,
            "toilet_review_count": 2,
            "prefecture": "東京都",
            "sample_reviews": [],
        }
        updated = {**original, "category": "更新", "toilet_score": 90, "confidence": 1.0}

        monkeypatch.setattr(to_sqlite, "DB_PATH", str(db_path))

        json_path.write_text(
            json.dumps({"metadata": {"area_name": "テスト"}, "toilets": [original]}, ensure_ascii=False),
            encoding="utf-8",
        )
        to_sqlite.json_to_sqlite(str(json_path), incremental=False)

        json_path.write_text(
            json.dumps({"metadata": {"area_name": "テスト2"}, "toilets": [updated]}, ensure_ascii=False),
            encoding="utf-8",
        )
        to_sqlite.json_to_sqlite(str(json_path), incremental=True)

        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                "SELECT COUNT(*), category, toilet_score FROM toilets WHERE title = 'A' AND lat = ? AND lng = ?",
                (35.68, 139.69),
            ).fetchone()
            meta = conn.execute("SELECT value FROM metadata WHERE key = 'area_name'").fetchone()[0]
            assert row[0] == 1
            assert row[1] == "更新"
            assert row[2] == 90
            assert meta == "テスト2"
        finally:
            conn.close()

    def test_full_conversion_preserves_last_updated_and_sets_sync_time(self, tmp_path, monkeypatch):
        db_path = tmp_path / "toilets.db"
        json_path = tmp_path / "toilets.json"
        payload = {
            "metadata": {
                "area_name": "テスト",
                "last_updated": "2026-05-10 21:27:30",
            },
            "toilets": [
                {
                    "title": "A",
                    "category": "公衆トイレ",
                    "address": "東京都渋谷区",
                    "lat": 35.68,
                    "lng": 139.69,
                    "rating": 4.0,
                    "review_count": 10,
                    "is_public_toilet": True,
                    "toilet_score": 80,
                    "confidence": 0.8,
                    "toilet_review_count": 2,
                    "prefecture": "東京都",
                    "sample_reviews": [],
                }
            ],
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        monkeypatch.setattr(to_sqlite, "DB_PATH", str(db_path))

        to_sqlite.json_to_sqlite(str(json_path), incremental=False)

        conn = sqlite3.connect(db_path)
        try:
            metadata = dict(conn.execute("SELECT key, value FROM metadata").fetchall())
            assert metadata["last_updated"] == "2026-05-10 21:27:30"
            assert metadata["db_synced_at"]
        finally:
            conn.close()


class TestMergeToDb:
    def test_merge_dedupes_existing_rows(self, tmp_path):
        db_path = tmp_path / "toilets.db"
        json_path = tmp_path / "input.json"
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(db_utils.TOILET_TABLE_SCHEMA)
            conn.execute(db_utils.METADATA_TABLE_SCHEMA)
            row = db_utils.toilet_db_values(
                {
                    "title": "A",
                    "category": "公衆トイレ",
                    "address": "東京都渋谷区",
                    "lat": 35.68,
                    "lng": 139.69,
                    "rating": 4.0,
                    "review_count": 10,
                    "is_public_toilet": True,
                    "toilet_score": 80,
                    "confidence": 0.8,
                    "toilet_review_count": 2,
                    "prefecture": "東京都",
                    "sample_reviews": [],
                }
            )
            insert_sql = (
                "INSERT INTO toilets (title, category, address, lat, lng, rating, review_count, "
                "is_public_toilet, toilet_score, confidence, toilet_review_count, prefecture, sample_reviews_json, top_keywords) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            )
            conn.execute(insert_sql, row)
            conn.execute(insert_sql, row)
            conn.commit()
        finally:
            conn.close()

        json_path.write_text(json.dumps({"metadata": {}, "toilets": []}, ensure_ascii=False), encoding="utf-8")

        merge_to_db.merge(str(json_path), db_path=str(db_path))

        conn = sqlite3.connect(db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
            unique_indexes = conn.execute("PRAGMA index_list('toilets')").fetchall()
            assert count == 1
            assert any(row[2] for row in unique_indexes)
        finally:
            conn.close()


class TestIncrementalLoad:
    def test_load_existing_finds_gz_output(self, tmp_path):
        base = tmp_path / "toilets.json"
        payload = {
            "metadata": {"area_name": "テスト"},
            "toilets": [{"title": "A", "lat": 35.0, "lng": 139.0, "confidence": 1, "is_public_toilet": False}],
        }
        with open(str(base) + ".gz", "wb") as f:
            import gzip
            with gzip.GzipFile(fileobj=f, mode="wb") as gz:
                gz.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

        loaded = pd_module.load_existing(str(base))

        assert loaded["metadata"]["area_name"] == "テスト"
        assert loaded["toilets"][0]["title"] == "A"


class TestCoerceFloat:
    def test_non_finite_raises(self):
        with pytest.raises(ValueError, match="invalid lat"):
            to_sqlite._coerce_float(float("inf"), "lat", 0)

    def test_valid(self):
        assert to_sqlite._coerce_float(35.68, "lat", 0) == 35.68


class TestCoerceInt:
    def test_bool_raises(self):
        with pytest.raises(ValueError, match="invalid review_count"):
            to_sqlite._coerce_int(True, "review_count", 0)

    def test_none_raises(self):
        with pytest.raises(ValueError, match="invalid review_count"):
            to_sqlite._coerce_int(None, "review_count", 0)

    def test_valid(self):
        assert to_sqlite._coerce_int(42, "review_count", 0) == 42


class TestValidateToiletRecord:
    def test_non_dict_raises(self):
        with pytest.raises(ValueError, match="must be an object"):
            to_sqlite._validate_toilet_record("not a dict", 0)

    def test_missing_fields_raises(self):
        with pytest.raises(ValueError, match="missing required fields"):
            to_sqlite._validate_toilet_record({}, 0)

    def test_confidence_out_of_range_raises(self):
        with pytest.raises(ValueError, match="invalid confidence"):
            to_sqlite._validate_toilet_record({
                "title": "A", "category": "公園", "address": "東京",
                "lat": 35.0, "lng": 139.0, "rating": 3.0, "review_count": 1,
                "is_public_toilet": False, "toilet_score": 50.0, "confidence": 1.5,
                "toilet_review_count": 0, "prefecture": "東京都",
                "sample_reviews": [], "top_keywords": [],
            }, 0)

    def test_score_out_of_range_raises(self):
        with pytest.raises(ValueError, match="invalid toilet_score"):
            to_sqlite._validate_toilet_record({
                "title": "A", "category": "公園", "address": "東京",
                "lat": 35.0, "lng": 139.0, "rating": 3.0, "review_count": 1,
                "is_public_toilet": False, "toilet_score": 150.0, "confidence": 0.5,
                "toilet_review_count": 0, "prefecture": "東京都",
                "sample_reviews": [], "top_keywords": [],
            }, 0)

    def test_negative_count_raises(self):
        with pytest.raises(ValueError, match="invalid count fields"):
            to_sqlite._validate_toilet_record({
                "title": "A", "category": "公園", "address": "東京",
                "lat": 35.0, "lng": 139.0, "rating": 3.0, "review_count": -1,
                "is_public_toilet": False, "toilet_score": 50.0, "confidence": 0.5,
                "toilet_review_count": 0, "prefecture": "東京都",
                "sample_reviews": [], "top_keywords": [],
            }, 0)

    def test_invalid_sample_reviews_raises(self):
        with pytest.raises(ValueError, match="invalid sample_reviews"):
            to_sqlite._validate_toilet_record({
                "title": "A", "category": "公園", "address": "東京",
                "lat": 35.0, "lng": 139.0, "rating": 3.0, "review_count": 1,
                "is_public_toilet": False, "toilet_score": 50.0, "confidence": 0.5,
                "toilet_review_count": 0, "prefecture": "東京都",
                "sample_reviews": "not a list", "top_keywords": [],
            }, 0)

    def test_invalid_top_keywords_raises(self):
        with pytest.raises(ValueError, match="invalid top_keywords"):
            to_sqlite._validate_toilet_record({
                "title": "A", "category": "公園", "address": "東京",
                "lat": 35.0, "lng": 139.0, "rating": 3.0, "review_count": 1,
                "is_public_toilet": False, "toilet_score": 50.0, "confidence": 0.5,
                "toilet_review_count": 0, "prefecture": "東京都",
                "sample_reviews": [], "top_keywords": "not a list",
            }, 0)

    def test_valid_record_passes(self):
        result = to_sqlite._validate_toilet_record({
            "title": "A", "category": "公園", "address": "東京",
            "lat": 35.0, "lng": 139.0, "rating": 3.0, "review_count": 1,
            "is_public_toilet": False, "toilet_score": 50.0, "confidence": 0.5,
            "toilet_review_count": 0, "prefecture": "東京都",
            "sample_reviews": [], "top_keywords": [],
        }, 0)
        assert result["title"] == "A"


class TestJsonToSqliteBackup:
    def test_non_incremental_backs_up_existing_db(self, tmp_path, monkeypatch):
        db_path = tmp_path / "toilets.db"
        json_path = tmp_path / "toilets.json"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE IF NOT EXISTS toilets (id INTEGER)")
        conn.close()
        payload = {"metadata": {}, "toilets": []}
        json_path.write_text(json.dumps(payload), encoding="utf-8")

        monkeypatch.setattr(to_sqlite, "DB_PATH", str(db_path))
        to_sqlite.json_to_sqlite(str(json_path), incremental=False)

        assert (tmp_path / "toilets.db.bak").exists()


class TestDbUtilsGetSchema:
    def test_returns_list_of_strings(self):
        schema = db_utils.get_schema_sql()
        assert len(schema) == 4
        assert all(isinstance(s, str) for s in schema)


class TestFixNullPrefectures:
    def test_fixes_from_address(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        try:
            conn.execute(db_utils.TOILET_TABLE_SCHEMA)
            conn.execute(
                "INSERT INTO toilets (title, category, address, lat, lng, rating, review_count, "
                "is_public_toilet, toilet_score, confidence, toilet_review_count, prefecture, sample_reviews_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("A", "公園", "東京都渋谷区", 35.0, 139.0, 3.0, 1, 0, 50.0, 0.5, 0, "", "[]"),
            )
            conn.commit()
            fixed = db_utils.fix_null_prefectures(conn)
            assert fixed == 1
            pref = conn.execute("SELECT prefecture FROM toilets WHERE id = 1").fetchone()[0]
            assert pref == "東京都"
        finally:
            conn.close()



