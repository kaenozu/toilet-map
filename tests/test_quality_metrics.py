"""
tests/test_quality_metrics.py
Tests for batch/quality_metrics.py data quality metrics

関連: batch/quality_metrics.py, batch/verify_data.py, tests/test_batch_verification.py
"""

import sqlite3
from collections import Counter

import db_utils

from batch.quality_metrics import (
    _coerce_float,
    _coerce_int,
    _format_duplicate_key,
    _normalize_count_map,
    _rate,
    collect_quality_metrics,
    collect_sqlite_metrics,
    compare_sqlite_metrics,
    evaluate_quality_gate,
)
from batch.quality_metrics_dto import QualityMetrics, SQLiteMetrics


class TestCoerceInt:
    def test_valid_int(self):
        assert _coerce_int(42) == 42

    def test_float_converted(self):
        assert _coerce_int(3.14) == 3

    def test_string_digit(self):
        assert _coerce_int("5") == 5

    def test_none_returns_none(self):
        assert _coerce_int(None) is None

    def test_invalid_string_returns_none(self):
        assert _coerce_int("abc") is None


class TestCoerceFloat:
    def test_valid_float(self):
        assert _coerce_float(3.14) == 3.14

    def test_int_converted(self):
        assert _coerce_float(5) == 5.0

    def test_string_number(self):
        assert _coerce_float("3.14") == 3.14

    def test_none_returns_none(self):
        assert _coerce_float(None) is None

    def test_invalid_returns_none(self):
        assert _coerce_float("abc") is None


class TestRate:
    def test_zero_total_returns_zero(self):
        assert _rate(5, 0) == 0.0

    def test_calculates_correctly(self):
        assert _rate(3, 10) == 0.3

    def test_zero_count_returns_zero(self):
        assert _rate(0, 10) == 0.0

    def test_full_rate(self):
        assert _rate(10, 10) == 1.0


class TestNormalizeCountMap:
    def test_converts_int_values(self):
        assert _normalize_count_map({"a": 5, "b": 3}) == {"a": 5, "b": 3}

    def test_skips_non_int_values(self):
        assert _normalize_count_map({"a": "invalid", "b": 3}) == {"b": 3}

    def test_handles_counter(self):
        assert _normalize_count_map(Counter({"a": 5, "b": 3})) == {"a": 5, "b": 3}

    def test_empty(self):
        assert _normalize_count_map({}) == {}

    def test_none_value_skipped(self):
        assert _normalize_count_map({"a": None, "b": 3}) == {"b": 3}

    def test_float_converted(self):
        assert _normalize_count_map({"a": 5.7, "b": 3}) == {"a": 5, "b": 3}


class TestCollectQualityMetrics:
    def test_counts_total_and_missing(self):
        toilets = [
            {
                "title": "A",
                "address": "東京都千代田区",
                "prefecture": "東京都",
                "toilet_score": 80,
                "link": "https://maps.google.com/a",
            },
            {"title": "B", "address": "", "prefecture": "", "toilet_score": None, "link": "https://maps.google.com/b"},
        ]
        metrics = collect_quality_metrics(toilets)
        assert metrics.total == 2
        assert metrics.missing_score == 1
        assert metrics.missing_prefecture == 1
        assert metrics.missing_address == 1
        assert metrics.prefecture_counts["東京都"] == 1

    def test_detects_duplicates_by_place_id(self):
        toilets = [
            {"place_id": "ChIJA", "title": "A", "link": "https://maps.google.com/a"},
            {"place_id": "ChIJA", "title": "B", "link": "https://maps.google.com/b"},
        ]
        metrics = collect_quality_metrics(toilets)
        assert len(metrics.duplicates) == 1
        assert metrics.duplicates[0]["key"] == ("place_id", "ChIJA")

    def test_detects_duplicates_by_data_id(self):
        toilets = [
            {"data_id": "0x111", "title": "A", "link": "https://maps.google.com/a"},
            {"data_id": "0x111", "title": "B", "link": "https://maps.google.com/b"},
        ]
        metrics = collect_quality_metrics(toilets)
        assert len(metrics.duplicates) == 1
        assert metrics.duplicates[0]["key"] == ("data_id", "0x111")

    def test_detects_duplicates_by_coordinates(self):
        toilets = [
            {"lat": 35.0, "lng": 139.0, "title": "A", "link": "a"},
            {"lat": 35.0, "lng": 139.0, "title": "B", "link": "b"},
        ]
        metrics = collect_quality_metrics(toilets)
        assert len(metrics.duplicates) == 1
        assert metrics.duplicates[0]["key"][0] == "coordinates"

    def test_no_duplicates_returns_empty_list(self):
        toilets = [
            {"place_id": "ChIJA", "title": "A", "link": "a"},
            {"place_id": "ChIJB", "title": "B", "link": "b"},
        ]
        metrics = collect_quality_metrics(toilets)
        assert metrics.duplicates == []


class TestCollectSqliteMetrics:
    def test_nonexistent_path_returns_none(self):
        assert collect_sqlite_metrics("/nonexistent/path.db") is None

    def test_invalid_db_returns_none(self, tmp_path):
        path = tmp_path / "invalid.db"
        path.write_text("not a database", encoding="utf-8")
        assert collect_sqlite_metrics(str(path)) is None

    def test_reads_from_valid_db(self, tmp_path):
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
                    "top_keywords": [],
                    "equipment": [],
                }
            )
            insert_sql = (
                "INSERT INTO toilets (title, category, address, lat, lng, rating, review_count, "
                "is_public_toilet, toilet_score, confidence, toilet_review_count, prefecture, "
                "sample_reviews_json, top_keywords, equipment) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            )
            conn.execute(insert_sql, row)
            conn.execute("INSERT INTO metadata (key, value) VALUES (?, ?)", ("area_name", "テスト"))
            conn.commit()
        finally:
            conn.close()

        metrics = collect_sqlite_metrics(str(db_path))
        assert metrics is not None
        assert metrics.total == 1
        assert metrics.scored == 1
        assert metrics.public_toilets == 1
        assert metrics.prefecture_counts["東京都"] == 1
        assert metrics.metadata["area_name"] == "テスト"


class TestCompareSqliteMetrics:
    def test_all_match_no_errors(self):
        meta = {"total": 5, "scored": 5, "public_toilets": 1, "last_updated": "2026-01-01", "prefecture_counts": {}}
        sqlite_metrics = SQLiteMetrics(
            total=5,
            scored=5,
            public_toilets=1,
            prefecture_counts={},
            metadata={"last_updated": "2026-01-01", "db_synced_at": "now"},
        )
        result = compare_sqlite_metrics(meta, sqlite_metrics)
        assert result.errors == []
        assert result.warnings == []

    def test_detects_total_mismatch(self):
        meta = {"total": 10, "scored": 8, "public_toilets": 3}
        sqlite_metrics = SQLiteMetrics(total=9, scored=8, public_toilets=3, prefecture_counts={}, metadata={})
        result = compare_sqlite_metrics(meta, sqlite_metrics)
        assert any("SQLite total mismatch" in e for e in result.errors)

    def test_detects_prefecture_mismatch(self):
        meta = {"total": 2, "scored": 2, "public_toilets": 1, "prefecture_counts": {"東京都": 2}}
        sqlite_metrics = SQLiteMetrics(
            total=2, scored=2, public_toilets=1, prefecture_counts={"東京都": 1}, metadata={"db_synced_at": "now"}
        )
        result = compare_sqlite_metrics(meta, sqlite_metrics)
        assert any("prefecture count mismatch" in e for e in result.errors)

    def test_db_synced_at_missing_warns(self):
        meta = {"total": 5, "scored": 5, "public_toilets": 1, "last_updated": "2026-01-01", "prefecture_counts": {}}
        sqlite_metrics = SQLiteMetrics(total=5, scored=5, public_toilets=1, prefecture_counts={}, metadata={})
        result = compare_sqlite_metrics(meta, sqlite_metrics)
        assert any("db_synced_at missing" in w for w in result.warnings)


class TestEvaluateQualityGate:
    def test_passes_when_all_within_thresholds(self):
        metrics = QualityMetrics(
            total=100,
            missing_score=5,
            missing_prefecture=2,
            missing_address=3,
            duplicates=[],
            prefecture_counts={"東京都": 100},
        )
        result = evaluate_quality_gate(metrics, ["東京都"])
        assert result.errors == []
        assert result.warnings == []

    def test_fails_on_high_missing_score_rate(self):
        metrics = QualityMetrics(
            total=10,
            missing_score=3,
            missing_prefecture=0,
            missing_address=0,
            duplicates=[],
            prefecture_counts={"東京都": 10},
        )
        result = evaluate_quality_gate(metrics, ["東京都"])
        assert any("Missing score rate" in e for e in result.errors)

    def test_fails_on_high_missing_pref_rate(self):
        metrics = QualityMetrics(
            total=10,
            missing_score=0,
            missing_prefecture=2,
            missing_address=0,
            duplicates=[],
            prefecture_counts={"東京都": 10},
        )
        result = evaluate_quality_gate(metrics, ["東京都"])
        assert any("Missing prefecture rate" in e for e in result.errors)

    def test_fails_on_high_missing_address_rate(self):
        metrics = QualityMetrics(
            total=10,
            missing_score=0,
            missing_prefecture=0,
            missing_address=2,
            duplicates=[],
            prefecture_counts={"東京都": 10},
        )
        result = evaluate_quality_gate(metrics, ["東京都"])
        assert any("Missing address rate" in e for e in result.errors)

    def test_warns_on_unexpected_prefecture(self):
        metrics = QualityMetrics(
            total=5,
            missing_score=0,
            missing_prefecture=0,
            missing_address=0,
            duplicates=[],
            prefecture_counts={"東京都": 5},
        )
        result = evaluate_quality_gate(metrics, ["東京都", "神奈川県"])
        assert any("No records found for 神奈川県" in w for w in result.warnings)

    def test_empty_toilets_passes_no_gate_errors(self):
        metrics = QualityMetrics(
            total=0,
            missing_score=0,
            missing_prefecture=0,
            missing_address=0,
            duplicates=[],
            prefecture_counts={},
        )
        result = evaluate_quality_gate(metrics, ["東京都"])
        assert result.errors == []


class TestFormatDuplicateKey:
    def test_empty_key(self):
        assert _format_duplicate_key(()) == ""

    def test_place_id(self):
        assert _format_duplicate_key(("place_id", "ChIJ")) == "place_id=ChIJ"

    def test_data_id(self):
        assert _format_duplicate_key(("data_id", "0x123")) == "data_id=0x123"

    def test_coordinates(self):
        result = _format_duplicate_key(("coordinates", "35.0", "139.0"))
        assert result == "coordinates=35.0,139.0"

    def test_title_address(self):
        result = _format_duplicate_key(("title_address", "Test", "東京都渋谷区"))
        assert "Test" in result
        assert "東京都" in result

    def test_fallback(self):
        result = _format_duplicate_key(("unknown", "a", "b"))
        assert "a" in result
