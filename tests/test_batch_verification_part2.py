"""
tests/test_batch_verification.py
データ検証・品質ゲート関連の回帰テスト（test_batch_regressions.py から分割）
"""

import pytest
import verify_data


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



