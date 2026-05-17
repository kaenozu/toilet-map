"""
tests/test_batch_db_operations.py
データベース操作関連の回帰テスト（test_batch_regressions.py から分割）
"""
import json
import sqlite3

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



