"""
tests/test_batch_verification.py
データ検証・品質ゲート関連の回帰テスト（test_batch_regressions.py から分割）
"""
import json
import sqlite3

import pytest

import db_utils
import gap_analyzer
import auto_expand
import verify_data
import sync_db


class TestVerificationAlignment:
    def test_sqlite_metric_mismatch_becomes_error(self):
        meta = {"total": 10, "scored": 8, "public_toilets": 3}
        sqlite_metrics = {"total": 9, "scored": 8, "public_toilets": 3, "metadata": {}}

        errors, warnings = verify_data.compare_sqlite_metrics(meta, sqlite_metrics)

        assert any("SQLite total mismatch" in error for error in errors)
        assert any("SQLite db_synced_at missing" in warning for warning in warnings)

    def test_sync_json_to_sqlite_forces_full_refresh(self, monkeypatch):
        calls = []

        def fake_json_to_sqlite(json_path, incremental=False):
            calls.append((json_path, incremental))

        monkeypatch.setattr(sync_db, "_json_to_sqlite", fake_json_to_sqlite)

        sync_db.sync_json_to_sqlite("input.json")

        assert calls == [("input.json", False)]


class TestVerificationGate:
    def test_count_queries_for_pref_aggregates_all_batches(self, tmp_path, monkeypatch):
        pref_dir = tmp_path / "queries.d" / "三重県"
        pref_dir.mkdir(parents=True)
        (pref_dir / "batch_000_target.txt").write_text("q1\nq2\n", encoding="utf-8")
        (pref_dir / "batch_001.txt").write_text("# comment\nq3\n", encoding="utf-8")

        monkeypatch.setattr(verify_data, "QUERIES_D", str(tmp_path / "queries.d"))

        assert verify_data.get_expected_prefectures() == ["三重県"]
        assert verify_data.count_queries_for_pref("三重県") == 3

    def test_find_gaps_prioritizes_active_prefectures(self):
        stats = {
            "北海道": {"札幌市": 0, "函館市": 0},
            "東京都": {"千代田区": 1, "新宿区": 0},
        }

        gaps = gap_analyzer.find_gaps(stats)

        assert gaps[0]["prefecture"] == "東京都"
        assert gaps[0]["city"] == "新宿区"

    def test_collect_quality_metrics_counts_missing_and_duplicates(self):
        toilets = [
            {"title": "A", "address": "東京都千代田区", "prefecture": "東京都", "toilet_score": 80, "link": "https://maps.google.com/a"},
            {"title": "A", "address": "東京都千代田区", "prefecture": "東京都", "toilet_score": 75, "link": "https://maps.google.com/b"},
            {"title": "B", "address": "", "prefecture": "", "toilet_score": None, "link": "https://maps.google.com/c"},
        ]

        metrics = verify_data.collect_quality_metrics(toilets)

        assert metrics["total"] == 3
        assert metrics["missing_score"] == 1
        assert metrics["missing_prefecture"] == 1
        assert metrics["missing_address"] == 1
        assert len(metrics["duplicates"]) == 1
        assert metrics["prefecture_counts"]["東京都"] == 2

    def test_collect_quality_metrics_prefers_place_ids(self):
        toilets = [
            {
                "title": "A",
                "address": "東京都千代田区",
                "prefecture": "東京都",
                "toilet_score": 80,
                "place_id": "ChIJA",
                "data_id": "0x111",
                "link": "https://maps.google.com/a",
            },
            {
                "title": "B",
                "address": "別の住所",
                "prefecture": "東京都",
                "toilet_score": 75,
                "place_id": "ChIJA",
                "data_id": "0x111",
                "link": "https://maps.google.com/b",
            },
        ]

        metrics = verify_data.collect_quality_metrics(toilets)

        assert len(metrics["duplicates"]) == 1
        assert metrics["duplicates"][0]["key"] == ("place_id", "ChIJA")

    def test_collect_quality_metrics_detects_coordinate_duplicates(self):
        toilets = [
            {
                "title": "A",
                "address": "東京都千代田区",
                "prefecture": "東京都",
                "lat": 35.0,
                "lng": 139.0,
                "toilet_score": 80,
                "link": "https://maps.google.com/a",
            },
            {
                "title": "B",
                "address": "東京都千代田区",
                "prefecture": "東京都",
                "lat": 35.0,
                "lng": 139.0,
                "toilet_score": 75,
                "link": "https://maps.google.com/b",
            },
        ]

        metrics = verify_data.collect_quality_metrics(toilets)

        assert len(metrics["duplicates"]) == 1
        assert metrics["duplicates"][0]["key"][0] == "coordinates"

    def test_collect_sqlite_metrics_reads_summary(self, tmp_path):
        db_path = tmp_path / "toilets.db"
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
                "is_public_toilet, toilet_score, confidence, toilet_review_count, prefecture, sample_reviews_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            )
            conn.execute(insert_sql, row)
            conn.execute("INSERT INTO metadata (key, value) VALUES (?, ?)", ("area_name", "テスト"))
            conn.commit()
        finally:
            conn.close()

        summary = verify_data.collect_sqlite_metrics(str(db_path))

        assert summary is not None
        assert summary["total"] == 1
        assert summary["scored"] == 1
        assert summary["public_toilets"] == 1
        assert summary["prefecture_counts"]["東京都"] == 1
        assert summary["metadata"]["area_name"] == "テスト"

    def test_compare_sqlite_metrics_detects_prefecture_mismatch(self):
        meta = {
            "total": 2,
            "scored": 2,
            "public_toilets": 1,
            "prefecture_counts": {"東京都": 2},
        }
        sqlite_metrics = {
            "total": 2,
            "scored": 2,
            "public_toilets": 1,
            "metadata": {"db_synced_at": "2026-05-11 00:00:00"},
            "prefecture_counts": {"東京都": 1},
        }

        errors, warnings = verify_data.compare_sqlite_metrics(meta, sqlite_metrics)

        assert any("prefecture count mismatch" in message for message in errors)
        assert warnings == []

    def test_evaluate_quality_gate_fails_on_large_missing_rate(self):
        metrics = {
            "total": 10,
            "missing_score": 3,
            "missing_prefecture": 0,
            "missing_address": 0,
            "duplicates": [],
            "prefecture_counts": {"東京都": 10},
        }

        errors, warnings = verify_data.evaluate_quality_gate(metrics, expected_prefectures=["東京都"])

        assert errors
        assert any("Missing score rate" in message for message in errors)
        assert warnings == []

    def test_evaluate_quality_gate_warns_on_missing_prefecture_coverage(self):
        metrics = {
            "total": 5,
            "missing_score": 0,
            "missing_prefecture": 0,
            "missing_address": 0,
            "duplicates": [],
            "prefecture_counts": {"東京都": 5},
        }

        errors, warnings = verify_data.evaluate_quality_gate(metrics, expected_prefectures=["東京都", "神奈川県"])

        assert errors == []
        assert any("No records found for 神奈川県" in message for message in warnings)
