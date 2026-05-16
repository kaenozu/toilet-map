"""
tests/test_batch_verification.py
データ検証・品質ゲート関連の回帰テスト（test_batch_regressions.py から分割）
"""
import sqlite3

import db_utils
import gap_analyzer
import pytest
import sync_db
import verify_data


class TestQualityMetricsUtilities:
    def test_rate_returns_zero_for_zero_total(self):
        from quality_metrics import _rate
        assert _rate(5, 0) == 0.0

    def test_rate_calculates_correctly(self):
        from quality_metrics import _rate
        assert _rate(3, 10) == 0.3

    def test_rate_zero_count(self):
        from quality_metrics import _rate
        assert _rate(0, 10) == 0.0

    def test_normalize_count_map_converts_int_values(self):
        from quality_metrics import _normalize_count_map
        result = _normalize_count_map({"a": 5, "b": 3})
        assert result == {"a": 5, "b": 3}

    def test_normalize_count_map_skips_non_int(self):
        from quality_metrics import _normalize_count_map
        result = _normalize_count_map({"a": "invalid", "b": 3})
        assert result == {"b": 3}

    def test_normalize_count_map_handles_counter(self):
        from collections import Counter

        from quality_metrics import _normalize_count_map
        result = _normalize_count_map(Counter({"a": 5, "b": 3}))
        assert result == {"a": 5, "b": 3}

    def test_normalize_count_map_empty(self):
        from quality_metrics import _normalize_count_map
        assert _normalize_count_map({}) == {}

    def test_normalize_count_map_none_value_skipped(self):
        from quality_metrics import _normalize_count_map
        result = _normalize_count_map({"a": None, "b": 3})
        assert result == {"b": 3}

    def test_normalize_count_map_float_value_converted(self):
        from quality_metrics import _normalize_count_map
        result = _normalize_count_map({"a": 5.7, "b": 3})
        assert result == {"a": 5, "b": 3}


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
                "is_public_toilet, toilet_score, confidence, toilet_review_count, prefecture, sample_reviews_json, top_keywords) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
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


class TestVerifyDataLoad:
    def test_loads_gz(self, tmp_path, monkeypatch):
        import gzip
        import json
        path = tmp_path / "toilets.json.gz"
        data = {"metadata": {"total": 1}, "toilets": [{"title": "A"}]}
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump(data, f)

        monkeypatch.setattr(verify_data, "DATA_PATHS", [str(path)])
        result = verify_data.load_data()
        assert result["metadata"]["total"] == 1

    def test_loads_json(self, tmp_path, monkeypatch):
        import json
        path = tmp_path / "toilets.json"
        data = {"metadata": {"total": 2}, "toilets": []}
        path.write_text(json.dumps(data), encoding="utf-8")

        monkeypatch.setattr(verify_data, "DATA_PATHS", [str(path)])
        result = verify_data.load_data()
        assert result["metadata"]["total"] == 2

    def test_raises_on_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(verify_data, "DATA_PATHS", [str(tmp_path / "nope.json.gz")])
        with pytest.raises(FileNotFoundError):
            verify_data.load_data()


class TestGetExpectedPrefectures:
    def test_from_queries_dir(self, tmp_path, monkeypatch):
        queries_d = tmp_path / "queries.d"
        for pref in ["東京都", "大阪府"]:
            d = queries_d / pref
            d.mkdir(parents=True)
            (d / "batch_001.txt").write_text("q1\n", encoding="utf-8")
        monkeypatch.setattr(verify_data, "QUERIES_D", str(queries_d))
        result = verify_data.get_expected_prefectures()
        assert result == ["大阪府", "東京都"]

    def test_falls_back_to_kanto_when_no_queries_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(verify_data, "QUERIES_D", str(tmp_path / "nonexistent"))
        assert verify_data.get_expected_prefectures() == verify_data.KANTO_PREFECTURES

    def test_skips_non_batch_dirs(self, tmp_path, monkeypatch):
        queries_d = tmp_path / "queries.d"
        d = queries_d / "東京都"
        d.mkdir(parents=True)
        (d / "batch_001.txt").write_text("q1\n", encoding="utf-8")
        empty_dir = queries_d / "大阪府"
        empty_dir.mkdir()
        monkeypatch.setattr(verify_data, "QUERIES_D", str(queries_d))
        result = verify_data.get_expected_prefectures()
        assert result == ["東京都"]


class TestCountQueriesForPref:
    def test_counts_non_comment_lines(self, tmp_path, monkeypatch):
        pref_dir = tmp_path / "queries.d" / "東京都"
        pref_dir.mkdir(parents=True)
        (pref_dir / "batch_001.txt").write_text("# comment\nq1\nq2\n", encoding="utf-8")
        (pref_dir / "batch_002.txt").write_text("q3\n", encoding="utf-8")
        monkeypatch.setattr(verify_data, "QUERIES_D", str(tmp_path / "queries.d"))
        assert verify_data.count_queries_for_pref("東京都") == 3

    def test_returns_zero_for_missing_pref(self, tmp_path, monkeypatch):
        monkeypatch.setattr(verify_data, "QUERIES_D", str(tmp_path / "queries.d"))
        assert verify_data.count_queries_for_pref("存在しない県") == 0


class TestVerifyDataMain:
    def test_returns_zero_on_success(self, monkeypatch):
        data = {"metadata": {"total": 1, "scored": 1, "public_toilets": 0, "last_updated": "2026-01-01"},
                "toilets": [{"title": "A", "address": "東京都", "prefecture": "東京都",
                             "toilet_score": 80.0, "confidence": 0.8,
                             "is_public_toilet": True, "lat": 35.0, "lng": 139.0}]}
        monkeypatch.setattr(verify_data, "load_data", lambda: data)
        monkeypatch.setattr(verify_data, "get_expected_prefectures", lambda: ["東京都"])
        monkeypatch.setattr(verify_data, "collect_sqlite_metrics", lambda path: None)

        monkeypatch.setattr(verify_data, "_format_duplicate_key", lambda k: str(k))

        result = verify_data.main()
        assert result == 0

    def test_returns_one_on_errors(self, monkeypatch):
        data = {"metadata": {"total": 0, "scored": 0, "public_toilets": 0, "last_updated": ""},
                "toilets": []}
        monkeypatch.setattr(verify_data, "load_data", lambda: data)
        monkeypatch.setattr(verify_data, "get_expected_prefectures", lambda: ["東京都"])

        monkeypatch.setattr(verify_data, "collect_quality_metrics",
                            lambda toilets: {"total": 0, "missing_score": 0, "missing_prefecture": 0,
                                             "missing_address": 0, "duplicates": [],
                                             "prefecture_counts": {}})
        monkeypatch.setattr(verify_data, "evaluate_quality_gate",
                            lambda metrics, expected: (["Error: missing prefecture"], []))
        monkeypatch.setattr(verify_data, "collect_sqlite_metrics", lambda path: None)

        result = verify_data.main()
        assert result == 1

    def test_prints_summary(self, monkeypatch, capsys):
        data = {"metadata": {"total": 2, "scored": 2, "public_toilets": 1,
                             "last_updated": "2026-05-13 12:00:00"},
                "toilets": [{"title": "A", "address": "東京都", "prefecture": "東京都",
                             "toilet_score": 80.0, "confidence": 0.8,
                             "is_public_toilet": True, "lat": 35.0, "lng": 139.0,
                             "link": "https://maps.google.com/a"},
                            {"title": "B", "address": "神奈川県", "prefecture": "神奈川県",
                             "toilet_score": 60.0, "confidence": 0.5,
                             "is_public_toilet": False, "lat": 35.1, "lng": 139.1,
                             "link": "https://maps.google.com/b"}]}
        monkeypatch.setattr(verify_data, "load_data", lambda: data)
        monkeypatch.setattr(verify_data, "get_expected_prefectures", lambda: ["東京都", "神奈川県"])
        monkeypatch.setattr(verify_data, "count_queries_for_pref", lambda pref: 10)
        monkeypatch.setattr(verify_data, "collect_sqlite_metrics", lambda path: None)

        verify_data.main()
        captured = capsys.readouterr()
        assert "Total toilets    : 2" in captured.out
        assert "With reviews     : 2" in captured.out
        assert "Public toilets   : 1" in captured.out
        assert "東京都" in captured.out
        assert "神奈川県" in captured.out


class TestFormatDuplicateKey:
    def test_empty_key(self):
        from quality_metrics import _format_duplicate_key
        assert _format_duplicate_key(()) == ""

    def test_place_id(self):
        from quality_metrics import _format_duplicate_key
        result = _format_duplicate_key(("place_id", "ChIJ"))
        assert result == "place_id=ChIJ"

    def test_data_id(self):
        from quality_metrics import _format_duplicate_key
        result = _format_duplicate_key(("data_id", "0x123"))
        assert result == "data_id=0x123"

    def test_coordinates(self):
        from quality_metrics import _format_duplicate_key
        result = _format_duplicate_key(("coordinates", "35.0", "139.0"))
        assert result == "coordinates=35.0,139.0"

    def test_title_address(self):
        from quality_metrics import _format_duplicate_key
        result = _format_duplicate_key(("title_address", "Test", "東京都渋谷区"))
        assert "Test" in result
        assert "東京都" in result

    def test_fallback(self):
        from quality_metrics import _format_duplicate_key
        result = _format_duplicate_key(("unknown", "a", "b"))
        assert "a" in result


class TestCompareSqliteMetricsDetailed:
    def test_all_three_mismatches(self):
        from quality_metrics import compare_sqlite_metrics
        meta = {"total": 10, "scored": 8, "public_toilets": 3}
        sqlite_metrics = {"total": 9, "scored": 7, "public_toilets": 2, "metadata": {}}
        errors, warnings = compare_sqlite_metrics(meta, sqlite_metrics)
        assert len(errors) == 3

    def test_metadata_mismatch_generates_warnings(self):
        from quality_metrics import compare_sqlite_metrics
        meta = {"total": 5, "scored": 5, "public_toilets": 1,
                "last_updated": "2026-01-01", "prefecture_counts": {}}
        sqlite_metrics = {"total": 5, "scored": 5, "public_toilets": 1,
                          "metadata": {"last_updated": "2025-01-01", "db_synced_at": "2026-01-01"},
                          "prefecture_counts": {}}
        errors, warnings = compare_sqlite_metrics(meta, sqlite_metrics)
        assert any("last_updated mismatch" in w for w in warnings)

    def test_missing_db_synced_at_warning(self):
        from quality_metrics import compare_sqlite_metrics
        meta = {"total": 5, "scored": 5, "public_toilets": 1,
                "last_updated": "2026-01-01", "prefecture_counts": {}}
        sqlite_metrics = {"total": 5, "scored": 5, "public_toilets": 1,
                          "metadata": {}, "prefecture_counts": {}}
        errors, warnings = compare_sqlite_metrics(meta, sqlite_metrics)
        assert any("db_synced_at missing" in w for w in warnings)

    def test_unexpected_prefecture_in_sqlite(self):
        from quality_metrics import compare_sqlite_metrics
        meta = {"total": 5, "scored": 5, "public_toilets": 1,
                "prefecture_counts": {"東京都": 5}}
        sqlite_metrics = {"total": 5, "scored": 5, "public_toilets": 1,
                          "metadata": {"db_synced_at": "now"},
                          "prefecture_counts": {"東京都": 5, "大阪府": 0}}
        errors, warnings = compare_sqlite_metrics(meta, sqlite_metrics)
        assert any("unexpected prefecture" in e for e in errors)

    def test_missing_prefecture_in_sqlite(self):
        from quality_metrics import compare_sqlite_metrics
        meta = {"total": 5, "scored": 5, "public_toilets": 1,
                "prefecture_counts": {"東京都": 5, "大阪府": 3}}
        sqlite_metrics = {"total": 5, "scored": 5, "public_toilets": 1,
                          "metadata": {"db_synced_at": "now"},
                          "prefecture_counts": {"東京都": 5}}
        errors, warnings = compare_sqlite_metrics(meta, sqlite_metrics)
        assert any("missing prefecture" in e for e in errors)


class TestCollectSqliteMetricsEdgeCases:
    def test_nonexistent_path(self):
        from quality_metrics import collect_sqlite_metrics
        assert collect_sqlite_metrics("/nonexistent/path.db") is None

    def test_operational_error_returns_none(self, tmp_path):
        from quality_metrics import collect_sqlite_metrics
        path = tmp_path / "empty.db"
        path.write_text("not a database", encoding="utf-8")
        result = collect_sqlite_metrics(str(path))
        assert result is None


class TestGapAnalyzerLoadPrefectureCatalog:
    def test_file_not_exists(self, monkeypatch):
        from gap_analyzer import _load_prefecture_catalog
        _load_prefecture_catalog.cache_clear()
        monkeypatch.setattr("gap_analyzer.PREFECTURE_CITIES_PATH", "/nonexistent/path.json")
        assert _load_prefecture_catalog() == {}

    def test_invalid_json(self, tmp_path, monkeypatch):
        from gap_analyzer import _load_prefecture_catalog
        _load_prefecture_catalog.cache_clear()
        path = tmp_path / "cities.json"
        path.write_text("not json", encoding="utf-8")
        monkeypatch.setattr("gap_analyzer.PREFECTURE_CITIES_PATH", str(path))
        assert _load_prefecture_catalog() == {}

    def test_lru_cache_reads_file_once(self, tmp_path, monkeypatch):
        from gap_analyzer import _load_prefecture_catalog
        _load_prefecture_catalog.cache_clear()
        path = tmp_path / "cities.json"
        path.write_text('{"東京都": ["千代田区"]}', encoding="utf-8")
        monkeypatch.setattr("gap_analyzer.PREFECTURE_CITIES_PATH", str(path))
        read_count = [0]
        original_open = __builtins__["open"]

        def tracking_open(*args, **kw):
            if "cities.json" in str(args[0]):
                read_count[0] += 1
            return original_open(*args, **kw)

        monkeypatch.setattr("builtins.open", tracking_open)
        _load_prefecture_catalog()
        _load_prefecture_catalog()
        assert read_count[0] == 1


class TestExtractCityEdgeCases:
    def test_empty_address(self):
        from gap_analyzer import _extract_city
        assert _extract_city("") == ""
        assert _extract_city(None) == ""

    def test_catalog_fallback_when_no_regex_match(self, monkeypatch):
        from gap_analyzer import _extract_city
        catalog = {"東京都": ["千代田区", "新宿区"]}
        monkeypatch.setattr("gap_analyzer._load_prefecture_catalog", lambda: catalog)
        result = _extract_city("東京都港", "東京都")
        assert result == ""


class TestGetStatsEdgeCases:
    def test_invalid_score_logs_warning(self, caplog):
        from gap_analyzer import get_stats
        toilets = [
            {"address": "東京都千代田区", "prefecture": "東京都", "toilet_score": "invalid"},
        ]
        stats = get_stats(toilets)
        assert stats["scored"] == 0
        assert stats["total"] == 1


class TestNormalizeCityCounts:
    def test_non_int_value_continues(self):
        from gap_analyzer import _normalize_city_counts
        result = _normalize_city_counts({"渋谷区": "abc", "新宿区": "3"})
        assert result == {"新宿区": 3}


class TestExtractCityCatalogFallback:
    def test_all_cities_when_no_prefecture(self, tmp_path, monkeypatch):
        from gap_analyzer import _extract_city, _load_prefecture_catalog
        _load_prefecture_catalog.cache_clear()
        path = tmp_path / "cities.json"
        path.write_text('{"東京都": ["新宿"]}', encoding="utf-8")
        monkeypatch.setattr("gap_analyzer.PREFECTURE_CITIES_PATH", str(path))
        result = _extract_city("abc新宿")
        assert result == "新宿"


class TestFindGapsEdgeCases:
    def test_include_catalog_expands_empty_cities(self, monkeypatch):
        from gap_analyzer import find_gaps
        monkeypatch.setattr("gap_analyzer._load_prefecture_catalog",
                            lambda: {"東京都": ["千代田区", "新宿区"]})
        stats = {"total": 0, "prefecture_city_counts": {"東京都": {"千代田区": 0}}}
        gaps = find_gaps(stats, threshold=5, include_catalog=True)
        prefectures_in_gaps = {g["city"] for g in gaps}
        assert "新宿区" in prefectures_in_gaps


class TestGetExpectedPrefecturesEdgeCases:
    def test_skips_non_directory_entries(self, tmp_path, monkeypatch):
        queries_d = tmp_path / "queries.d"
        queries_d.mkdir()
        tokyo = queries_d / "東京都"
        tokyo.mkdir()
        (tokyo / "batch_001.txt").write_text("q1\n", encoding="utf-8")
        (queries_d / "file.txt").write_text("not a dir", encoding="utf-8")
        monkeypatch.setattr(verify_data, "QUERIES_D", str(queries_d))
        result = verify_data.get_expected_prefectures()
        assert result == ["東京都"]


class TestMainKantoMode:
    def test_kanto_label_when_no_queries_dir(self, monkeypatch, capsys):
        monkeypatch.setattr(verify_data, "QUERIES_D", "/nonexistent")
        data = {"metadata": {"total": 1, "scored": 1, "public_toilets": 0,
                             "last_updated": "2026-01-01"},
                "toilets": [{"title": "A", "address": "東京都", "prefecture": "東京都",
                             "toilet_score": 80.0, "confidence": 0.8,
                             "is_public_toilet": True, "lat": 35.0, "lng": 139.0}]}
        monkeypatch.setattr(verify_data, "load_data", lambda: data)
        monkeypatch.setattr(verify_data, "collect_sqlite_metrics", lambda path: None)
        result = verify_data.main()
        assert result == 0
        captured = capsys.readouterr()
        assert "Kanto Phase 1" in captured.out

    def test_with_sqlite_metrics_and_duplicates_and_warnings(self, monkeypatch, capsys):
        data = {"metadata": {"total": 3, "scored": 2, "public_toilets": 1,
                             "last_updated": "2026-05-13", "prefecture_counts": {"東京都": 3}},
                "toilets": [
                    {"title": "A", "address": "東京都", "prefecture": "東京都",
                     "toilet_score": 80.0, "confidence": 0.8,
                     "is_public_toilet": True, "lat": 35.0, "lng": 139.0,
                     "link": "https://maps.google.com/a"},
                    {"title": "B", "address": "東京都", "prefecture": "東京都",
                     "toilet_score": 75.0, "confidence": 0.5,
                     "is_public_toilet": False, "lat": 35.0, "lng": 139.0,
                     "link": "https://maps.google.com/b"},
                    {"title": "C", "address": "", "prefecture": "", "toilet_score": None,
                     "is_public_toilet": False, "lat": 36.0, "lng": 140.0,
                     "link": "https://maps.google.com/c"},
                ]}
        monkeypatch.setattr(verify_data, "load_data", lambda: data)
        monkeypatch.setattr(verify_data, "get_expected_prefectures", lambda: ["東京都"])
        monkeypatch.setattr(verify_data, "count_queries_for_pref", lambda pref: 10)

        def fake_collect_quality(t):
            return {"total": 3, "missing_score": 1, "missing_prefecture": 1,
                    "missing_address": 1, "duplicates": [
                        {"key": ("place_id", "dup"), "link": ""},
                    ], "prefecture_counts": {"東京都": 3}}

        def fake_sqlite_metrics(path):
            return {"total": 3, "scored": 2, "public_toilets": 1,
                    "metadata": {"last_updated": "2026-05-13", "db_synced_at": "2026-05-13"},
                    "prefecture_counts": {"東京都": 3}}

        monkeypatch.setattr(verify_data, "collect_quality_metrics", fake_collect_quality)
        monkeypatch.setattr(verify_data, "collect_sqlite_metrics", fake_sqlite_metrics)
        monkeypatch.setattr(verify_data, "compare_sqlite_metrics",
                            lambda meta, sqlite: (["sqlite error"], ["sqlite warning"]))

        result = verify_data.main()
        assert result == 1
        captured = capsys.readouterr()
        assert "sqlite error" in captured.out
        assert "sqlite warning" in captured.out
        assert "duplicate" in captured.out.lower()
