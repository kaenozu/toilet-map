"""
tests/test_batch_verification.py
データ検証・品質ゲート関連の回帰テスト（test_batch_regressions.py から分割）
"""

import verify_data


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

