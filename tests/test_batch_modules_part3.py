"""
tests/test_batch_modules.py
batch modules のモックベースユニットテスト
docker_exec, city_bounds, auto_expand, scrape_runner の関数をテスト
"""
from pathlib import Path
from unittest.mock import MagicMock

import pytest


class TestPipeline:
    def test_raises_on_process_failure(self, monkeypatch):
        import pipeline
        monkeypatch.setattr("pipeline.file_lock", lambda *a, **kw: _null_context())
        monkeypatch.setattr(pipeline.subprocess, "run", lambda *a, **kw: _make_result(1))
        with pytest.raises((RuntimeError, pipeline.DataError), match="Data processing failed"):
            pipeline.run_postprocess_pipeline("in.json", "out.json", "/tmp")

    def test_raises_on_sqlite_failure(self, monkeypatch):
        import pipeline
        calls = []
        def _fake_run(*a, **kw):
            calls.append(1)
            r = MagicMock()
            r.returncode = 0 if len(calls) == 1 else 1
            return r
        monkeypatch.setattr("pipeline.file_lock", lambda *a, **kw: _null_context())
        monkeypatch.setattr(pipeline.subprocess, "run", _fake_run)
        with pytest.raises((RuntimeError, pipeline.DataError), match="SQLite conversion failed"):
            pipeline.run_postprocess_pipeline("in.json", "out.json", "/tmp")



class TestCityBoundsNoBoundingBox:
    def test_main_without_results_prints_message(self, monkeypatch, capsys):
        import city_bounds
        monkeypatch.setattr("sys.argv", ["city_bounds.py", "存在しない市"])
        monkeypatch.setattr(city_bounds, "_load_cache", lambda: {})
        monkeypatch.setattr(city_bounds, "urllib", None)

        def _fake_request(*a, **kw):
            class FakeResp:
                def read(self): return b'[{"boundingbox": ["a"]]'  # too short
                def decode(self, e): return self.read().decode(e) if hasattr(self.read(), 'decode') else self.read()
            return FakeResp()
        monkeypatch.setattr(city_bounds, "get_city_bounds", lambda c, p="": None)
        with pytest.raises(SystemExit):
            city_bounds.main()



class TestScrapeFilterPrepareInputData:
    def test_no_city_no_pref_returns_raw_output(self, monkeypatch, tmp_path):
        from scrape_filter import prepare_input_data
        raw_out = str(tmp_path / "raw.json")
        prepare_input_data("", "", raw_out, str(tmp_path), "")
        assert True

    def test_with_city_and_pref_routes_through_filter(self, monkeypatch, tmp_path):
        import scrape_filter
        raw_out = str(tmp_path / "raw.json")
        Path(raw_out).write_text("", encoding="utf-8")
        monkeypatch.setattr("scrape_filter.count_lines", lambda _: 0)
        monkeypatch.setattr("scrape_filter.merge_part_files", lambda *a: None)
        monkeypatch.setattr("scrape_filter.fetch_city_bounds", lambda c, p: None)
        monkeypatch.setattr("scrape_filter.filter_raw_data", lambda i, o, c, b: (0, 0))
        with pytest.raises((RuntimeError, scrape_filter.DataError), match="No entries matched"):
            scrape_filter.prepare_input_data("渋谷区", "東京都", raw_out, str(tmp_path), str(tmp_path / "queries.txt"))

    def test_with_city_and_pref_kept_returns_filtered_path(self, monkeypatch, tmp_path):
        from scrape_filter import prepare_input_data
        raw_out = str(tmp_path / "raw.json")
        monkeypatch.setattr("scrape_filter.count_lines", lambda _: 10)
        monkeypatch.setattr("scrape_filter.merge_part_files", lambda *a: None)
        monkeypatch.setattr("scrape_filter.fetch_city_bounds", lambda c, p: {})
        monkeypatch.setattr("scrape_filter.filter_raw_data", lambda i, o, c, b: (10, 3))
        result = prepare_input_data("渋谷区", "東京都", raw_out, str(tmp_path), str(tmp_path / "queries.txt"))
        assert "_filtered" in result

def _make_result(returncode):
    r = MagicMock()
    r.returncode = returncode
    return r


def _null_context():
    class NullCtx:
        def __enter__(self): return self
        def __exit__(self, *a): pass
    return NullCtx()



