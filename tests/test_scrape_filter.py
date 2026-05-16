"""
tests/test_scrape_filter.py
Tests for batch/scrape_filter.py city filtering logic

関連: batch/scrape_filter.py, batch/city_bounds.py, batch/scrape_runner.py
"""
from pathlib import Path

import pytest
import scrape_filter
from exceptions import DataError
from scrape_filter import apply_city_filter, fetch_city_bounds, prepare_input_data


class TestFetchCityBounds:
    def test_pref_only_calls_get_city_bounds_with_pref(self, monkeypatch):
        calls = []

        def fake_get_city_bounds(name, pref=""):
            calls.append((name, pref))
            return {"south": 35.0}

        monkeypatch.setattr(scrape_filter, "get_city_bounds", fake_get_city_bounds)
        result = fetch_city_bounds("", "東京都")
        assert result == {"south": 35.0}
        assert calls == [("東京都", "")]

    def test_pref_and_city_uses_city_with_pref_first(self, monkeypatch):
        calls = []

        def fake_get_city_bounds(name, pref=""):
            calls.append((name, pref))
            if pref:
                return {"south": 35.6}
            return None

        monkeypatch.setattr(scrape_filter, "get_city_bounds", fake_get_city_bounds)
        result = fetch_city_bounds("渋谷区", "東京都")
        assert result == {"south": 35.6}
        assert calls == [("渋谷区", "東京都")]

    def test_falls_back_to_city_only(self, monkeypatch):
        calls = []

        def fake_get_city_bounds(name, pref=""):
            calls.append((name, pref))
            return None

        monkeypatch.setattr(scrape_filter, "get_city_bounds", fake_get_city_bounds)
        result = fetch_city_bounds("渋谷区", "東京都")
        assert result is None
        assert calls == [("渋谷区", "東京都"), ("渋谷区", "")]


class TestApplyCityFilter:
    def test_filters_and_returns_path_and_counts(self, tmp_path, monkeypatch):
        raw_output = tmp_path / "raw.json"
        raw_output.write_text("", encoding="utf-8")

        monkeypatch.setattr(scrape_filter, "fetch_city_bounds", lambda c, p: {"south": 35.0})
        monkeypatch.setattr(scrape_filter, "filter_raw_data",
                            lambda i, o, c, b: (10, 3))

        filtered_path, total_raw, kept = apply_city_filter(
            "渋谷区", "東京都", str(raw_output), str(tmp_path), "queries.txt"
        )
        assert "_filtered" in filtered_path
        assert total_raw == 10
        assert kept == 3

    def test_no_bounds_returns_zero(self, tmp_path, monkeypatch):
        raw_output = tmp_path / "raw.json"
        raw_output.write_text("", encoding="utf-8")

        monkeypatch.setattr(scrape_filter, "fetch_city_bounds", lambda c, p: None)
        monkeypatch.setattr(scrape_filter, "filter_raw_data",
                            lambda i, o, c, b: (10, 0))

        filtered_path, total_raw, kept = apply_city_filter(
            "渋谷区", "東京都", str(raw_output), str(tmp_path), "queries.txt"
        )
        assert kept == 0


class TestPrepareInputData:
    def test_no_city_no_pref_returns_raw_unchanged(self, tmp_path):
        raw_output = str(tmp_path / "raw.json")
        result = prepare_input_data("", "", raw_output, str(tmp_path), "")
        assert result == raw_output

    def test_raises_when_no_entries_kept(self, monkeypatch, tmp_path):
        raw_output = str(tmp_path / "raw.json")
        Path(raw_output).write_text("", encoding="utf-8")
        monkeypatch.setattr(scrape_filter, "count_lines", lambda _: 10)
        monkeypatch.setattr(scrape_filter, "merge_part_files", lambda *a: None)
        monkeypatch.setattr(scrape_filter, "fetch_city_bounds", lambda c, p: None)
        monkeypatch.setattr(scrape_filter, "filter_raw_data", lambda i, o, c, b: (10, 0))

        with pytest.raises(DataError, match="No entries matched city filter"):
            prepare_input_data("渋谷区", "東京都", raw_output, str(tmp_path), str(tmp_path / "queries.txt"))

    def test_returns_filtered_path_on_success(self, monkeypatch, tmp_path):
        raw_output = str(tmp_path / "raw.json")
        monkeypatch.setattr(scrape_filter, "count_lines", lambda _: 10)
        monkeypatch.setattr(scrape_filter, "merge_part_files", lambda *a: None)
        monkeypatch.setattr(scrape_filter, "fetch_city_bounds", lambda c, p: {})
        monkeypatch.setattr(scrape_filter, "filter_raw_data", lambda i, o, c, b: (10, 5))

        result = prepare_input_data("渋谷区", "東京都", raw_output, str(tmp_path), str(tmp_path / "queries.txt"))
        assert "_filtered" in result
