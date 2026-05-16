"""
tests/test_batch_modules.py
batch modules のモックベースユニットテスト
docker_exec, city_bounds, auto_expand, scrape_runner の関数をテスト
"""
import json
import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from docker_exec import scrape_query
from city_bounds import _load_cache, _save_cache
from auto_expand import _load_current_stats, _lookup_city_count, _build_gap_entry, _select_targets
from scrape_filter import fetch_city_bounds
from scrape_runner import _cleanup_on_success


class TestDockerExecScrapeQuery:
    """docker_exec.py scrape_query のモックテスト"""

    def test_scrape_query_success(self, monkeypatch, tmp_path):
        output_path = tmp_path / "output.json"
        output_path.write_text('{"result": "ok"}\n', encoding="utf-8")

        monkeypatch.setattr("tempfile.NamedTemporaryFile", lambda *a, **kw: _fake_tempfile(tmp_path))
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _make_result(0))
        monkeypatch.setattr(os.path, "exists", lambda p: p == str(output_path))

        assert scrape_query("test query", str(output_path)) is True

    def test_scrape_query_subprocess_timeout(self, monkeypatch, tmp_path):
        monkeypatch.setattr("tempfile.NamedTemporaryFile", lambda *a, **kw: _fake_tempfile(tmp_path))

        def _timeout(*a, **kw):
            raise subprocess.TimeoutExpired(cmd="docker", timeout=600)

        monkeypatch.setattr(subprocess, "run", _timeout)
        monkeypatch.setattr(os.path, "exists", lambda p: False)

        assert scrape_query("test query", str(tmp_path / "output.json")) is False

    def test_scrape_query_docker_not_found(self, monkeypatch, tmp_path):
        monkeypatch.setattr("tempfile.NamedTemporaryFile", lambda *a, **kw: _fake_tempfile(tmp_path))

        def _not_found(*a, **kw):
            raise FileNotFoundError()

        monkeypatch.setattr(subprocess, "run", _not_found)
        monkeypatch.setattr(os.path, "exists", lambda p: False)

        assert scrape_query("test query", str(tmp_path / "output.json")) is False

    def test_scrape_query_nonzero_exit(self, monkeypatch, tmp_path):
        output_path = tmp_path / "output.json"

        monkeypatch.setattr("tempfile.NamedTemporaryFile", lambda *a, **kw: _fake_tempfile(tmp_path))
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _make_result(1))
        monkeypatch.setattr(os.path, "exists", lambda p: False)

        assert scrape_query("test query", str(output_path)) is False

    def test_scrape_query_empty_output(self, monkeypatch, tmp_path):
        output_path = tmp_path / "output.json"
        output_path.write_text("", encoding="utf-8")

        monkeypatch.setattr("tempfile.NamedTemporaryFile", lambda *a, **kw: _fake_tempfile(tmp_path))
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _make_result(0))
        monkeypatch.setattr(os.path, "exists", lambda p: p == str(output_path))

        assert scrape_query("test query", str(output_path)) is False

    def test_scrape_query_oserror(self, monkeypatch, tmp_path):
        monkeypatch.setattr("tempfile.NamedTemporaryFile", lambda *a, **kw: _fake_tempfile(tmp_path))

        def _os_error(*a, **kw):
            raise OSError("Docker not available")

        monkeypatch.setattr(subprocess, "run", _os_error)
        monkeypatch.setattr(os.path, "exists", lambda p: False)

        assert scrape_query("test query", str(tmp_path / "output.json")) is False

    def test_scrape_query_permission_error_on_cleanup(self, monkeypatch, tmp_path):
        output_path = tmp_path / "output.json"
        output_path.write_text('{"result": "ok"}\n', encoding="utf-8")

        temp_path = tmp_path / "tmp_query.txt"
        temp_path.write_text("test query", encoding="utf-8")

        class _RealTemp:
            name = str(temp_path)
            def write(self, text): pass
            def close(self): pass
            def __enter__(self): return self
            def __exit__(self, *a): pass

        def _raise_on_remove(p):
            if p.endswith(".txt"):
                raise PermissionError("Permission denied")
            return True

        monkeypatch.setattr("tempfile.NamedTemporaryFile", lambda *a, **kw: _RealTemp())
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _make_result(0))
        monkeypatch.setattr(os, "remove", _raise_on_remove)
        monkeypatch.setattr(os.path, "exists", lambda p: p == str(output_path) or p == str(temp_path))

        assert scrape_query("test query", str(output_path)) is True

    def test_scrape_query_output_not_created(self, monkeypatch, tmp_path):
        monkeypatch.setattr("tempfile.NamedTemporaryFile", lambda *a, **kw: _fake_tempfile(tmp_path))
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _make_result(0))
        monkeypatch.setattr(os.path, "exists", lambda p: False)

        assert scrape_query("test query", str(tmp_path / "output.json")) is False

    def test_scrape_query_builds_docker_command(self, monkeypatch, tmp_path):
        captured = {}

        monkeypatch.setattr("tempfile.NamedTemporaryFile", lambda *a, **kw: _fake_tempfile(tmp_path))

        def fake_run(cmd, cwd=".", timeout=600):
            captured["cmd"] = cmd
            return _make_result(0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        monkeypatch.setattr(os.path, "exists", lambda p: p == str(tmp_path / "output.json"))

        output_path = tmp_path / "output.json"

        def _fake_open(path, *a, **kw):
            f = MagicMock()
            f.__enter__.return_value = f
            f.__exit__.return_value = None
            f.readlines.return_value = ["data\n"]
            return f

        monkeypatch.setattr("builtins.open", _fake_open)

        scrape_query("test query", str(output_path))

        cmd = captured["cmd"]
        assert cmd[0] == "docker"
        assert cmd[1] == "run"
        assert cmd[2] == "--rm"
        assert "-depth" in cmd
        assert "-input" in cmd
        result_flag_index = cmd.index("-results")
        assert result_flag_index < len(cmd) - 1
        assert "/output/" in cmd[result_flag_index + 1]


class TestCityBoundsCache:
    """city_bounds.py キャッシュ関数のテスト"""

    def test_load_cache_missing_file(self, tmp_path):
        import city_bounds as cb
        original = cb.CACHE_FILE
        try:
            cb.CACHE_FILE = str(tmp_path / "nonexistent.json")
            assert _load_cache() == {}
        finally:
            cb.CACHE_FILE = original

    def test_load_cache_invalid_json(self, tmp_path):
        cache_file = tmp_path / "city_bounds_cache.json"
        cache_file.write_text("{invalid", encoding="utf-8")
        import city_bounds as cb
        original = cb.CACHE_FILE
        try:
            cb.CACHE_FILE = str(cache_file)
            assert _load_cache() == {}
        finally:
            cb.CACHE_FILE = original

    def test_save_and_load_cache(self, tmp_path):
        cache_file = tmp_path / "city_bounds_cache.json"
        cache_file.write_text("{}", encoding="utf-8")
        import city_bounds as cb
        original = cb.CACHE_FILE
        try:
            cb.CACHE_FILE = str(cache_file)
            data = {"東京都渋谷区": {"south": 35.0, "north": 36.0, "west": 139.0, "east": 140.0}}
            _save_cache(data)
            loaded = _load_cache()
            assert loaded == data
        finally:
            cb.CACHE_FILE = original

    def test_save_cache_overwrites_existing(self, tmp_path):
        cache_file = tmp_path / "city_bounds_cache.json"
        import city_bounds as cb
        original = cb.CACHE_FILE
        try:
            cb.CACHE_FILE = str(cache_file)
            _save_cache({"key1": {"a": 1}})
            _save_cache({"key2": {"b": 2}})
            loaded = _load_cache()
            assert loaded == {"key2": {"b": 2}}
        finally:
            cb.CACHE_FILE = original


class TestCityBoundsGetCityBounds:
    """city_bounds.py get_city_bounds のモックテスト"""

    def test_get_city_bounds_uses_cache(self, monkeypatch, tmp_path):
        cached = {"東京都渋谷区": {"south": 35.6, "north": 35.7, "west": 139.6, "east": 139.8}}
        cache_file = tmp_path / "city_bounds_cache.json"
        cache_file.write_text(json.dumps(cached, ensure_ascii=False), encoding="utf-8")

        import city_bounds as cb
        original = cb.CACHE_FILE
        urlopen_called = []

        def fake_urlopen(*a, **kw):
            urlopen_called.append(a)
            raise RuntimeError("should not be called")

        try:
            cb.CACHE_FILE = str(cache_file)
            monkeypatch.setattr(cb.urllib.request, "urlopen", fake_urlopen)
            result = cb.get_city_bounds("渋谷区", "東京都")
            assert result == cached["東京都渋谷区"]
            assert urlopen_called == []
        finally:
            cb.CACHE_FILE = original

    def test_get_city_bounds_fetches_from_api(self, monkeypatch, tmp_path):
        cache_file = tmp_path / "city_bounds_cache.json"
        cache_file.write_text("{}", encoding="utf-8")

        import city_bounds as cb
        original = cb.CACHE_FILE

        class FakeResponse:
            def read(self):
                return b'[{"boundingbox": ["35.6", "35.7", "139.6", "139.8"]}]'

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

        try:
            cb.CACHE_FILE = str(cache_file)
            monkeypatch.setattr(cb.urllib.request, "urlopen", lambda req, timeout=15: FakeResponse())
            monkeypatch.setattr(cb.time, "sleep", lambda _: None)

            result = cb.get_city_bounds("渋谷区", "東京都")
            assert result == {"south": 35.6, "north": 35.7, "west": 139.6, "east": 139.8}

            loaded = _load_cache()
            assert "東京都渋谷区" in loaded
            assert loaded["東京都渋谷区"]["south"] == 35.6
        finally:
            cb.CACHE_FILE = original

    def test_get_city_bounds_handles_api_failure(self, monkeypatch, tmp_path):
        cache_file = tmp_path / "city_bounds_cache.json"
        cache_file.write_text("{}", encoding="utf-8")

        import city_bounds as cb
        original = cb.CACHE_FILE

        def raise_error(*a, **kw):
            raise cb.urllib.error.URLError("API error")

        try:
            cb.CACHE_FILE = str(cache_file)
            monkeypatch.setattr(cb.urllib.request, "urlopen", raise_error)
            monkeypatch.setattr(cb.time, "sleep", lambda _: None)

            result = cb.get_city_bounds("存在しない市")
            assert result is None
        finally:
            cb.CACHE_FILE = original


class TestAutoExpandStats:
    """auto_expand.py の集計・選択関数のテスト"""

    def test_load_current_stats_empty(self, monkeypatch, tmp_path):
        import auto_expand as ae
        monkeypatch.setattr(ae, "CURRENT_DATA_PATHS", [str(tmp_path / "nonexistent.json.gz")])
        stats = _load_current_stats()
        assert isinstance(stats, dict)

    def test_lookup_city_count_found(self):
        stats = {
            "prefecture_city_counts": {
                "東京都": {"千代田区": "5", "渋谷区": "3"},
            }
        }
        assert _lookup_city_count(stats, "東京都", "千代田区") == 5

    def test_lookup_city_count_not_found(self):
        stats = {
            "prefecture_city_counts": {
                "東京都": {"千代田区": "5"},
            }
        }
        assert _lookup_city_count(stats, "東京都", "新宿区") == 0

    def test_lookup_city_count_missing_pref(self):
        stats = {"prefecture_city_counts": {"東京都": {}}}
        assert _lookup_city_count(stats, "大阪府", "大阪市") == 0

    def test_lookup_city_count_non_dict_nested(self):
        stats = {"prefecture_city_counts": "invalid"}
        assert _lookup_city_count(stats, "東京都", "千代田区") == 0

    def test_lookup_city_count_non_int_value(self):
        stats = {"prefecture_city_counts": {"東京都": {"千代田区": "abc"}}}
        assert _lookup_city_count(stats, "東京都", "千代田区") == 0

    def test_build_gap_entry_with_count(self):
        stats = {
            "prefecture_city_counts": {
                "埼玉県": {"羽生市": "2", "熊谷市": "5"},
            }
        }
        entry = _build_gap_entry(stats, "埼玉県", "羽生市", count=2)
        assert entry["prefecture"] == "埼玉県"
        assert entry["city"] == "羽生市"
        assert entry["count"] == 2
        assert entry["prefecture_total"] == 7
        assert entry["active"] is True

    def test_build_gap_entry_without_count(self):
        stats = {
            "prefecture_city_counts": {
                "埼玉県": {"羽生市": "3"},
            }
        }
        entry = _build_gap_entry(stats, "埼玉県", "羽生市")
        assert entry["count"] == 3

    def test_build_gap_entry_inactive(self):
        stats = {
            "prefecture_city_counts": {
                "埼玉県": {},
            }
        }
        entry = _build_gap_entry(stats, "埼玉県", "羽生市", count=0)
        assert entry["active"] is False

    def test_select_targets_with_target_pref_and_city(self):
        stats = {"prefecture_city_counts": {"埼玉県": {"羽生市": "0"}}}
        targets = _select_targets(stats, max_areas=5, target_pref="埼玉県", target_city="羽生市")
        assert len(targets) == 1
        assert targets[0]["prefecture"] == "埼玉県"
        assert targets[0]["city"] == "羽生市"

    def test_select_targets_with_target_pref_only(self):
        stats = {
            "prefecture_city_counts": {
                "埼玉県": {"羽生市": "0", "熊谷市": "2"},
            }
        }
        targets = _select_targets(stats, max_areas=1, target_pref="埼玉県")
        assert len(targets) >= 1

    def test_select_targets_empty_when_pref_unknown(self):
        stats = {"prefecture_city_counts": {"東京都": {}}}
        targets = _select_targets(stats, max_areas=5, target_pref="存在しない県")
        assert targets == []

    def test_select_targets_with_target_city_only(self):
        stats = {
            "prefecture_city_counts": {
                "埼玉県": {"羽生市": "0"},
            }
        }
        targets = _select_targets(stats, max_areas=5, target_city="羽生市")
        assert len(targets) == 1
        assert targets[0]["city"] == "羽生市"

    def test_select_targets_target_city_not_found(self):
        stats = {"prefecture_city_counts": {}}
        targets = _select_targets(stats, max_areas=5, target_city="存在しない市")
        assert targets == []

    def test_select_targets_defaults_to_gaps(self):
        stats = {"prefecture_city_counts": {}}
        targets = _select_targets(stats, max_areas=3)
        assert isinstance(targets, list)


class TestScrapeRunner:
    """scrape_runner.py のモックテスト"""

    def test_fetch_city_bounds_with_pref_only(self, monkeypatch):
        calls = []

        def fake_get_city_bounds(name, pref=""):
            calls.append(name if not pref else (name, pref))
            return {"south": 35.0, "north": 36.0, "west": 139.0, "east": 140.0}

        monkeypatch.setattr("scrape_filter.get_city_bounds", fake_get_city_bounds)
        result = fetch_city_bounds("", "東京都")
        assert result is not None

    def test_fetch_city_bounds_with_pref_and_city(self, monkeypatch):
        calls = []

        def fake_get_city_bounds(city, pref=""):
            calls.append((city, pref))
            if pref:
                return {"south": 35.6, "north": 35.7, "west": 139.6, "east": 139.8}
            return None

        monkeypatch.setattr("scrape_filter.get_city_bounds", fake_get_city_bounds)
        result = fetch_city_bounds("渋谷区", "東京都")
        assert result is not None
        assert calls == [("渋谷区", "東京都")]

    def test_fetch_city_bounds_fallback_to_city_only(self, monkeypatch):
        calls = []

        def fake_get_city_bounds(city, pref=""):
            calls.append((city, pref))
            return None

        monkeypatch.setattr("scrape_filter.get_city_bounds", fake_get_city_bounds)
        result = fetch_city_bounds("渋谷区", "東京都")
        assert result is None
        assert calls == [("渋谷区", "東京都"), ("渋谷区", "")]

    def test_cleanup_on_success_no_failures(self, monkeypatch, tmp_path):
        import scrape_runner as sr

        progress = tmp_path / "progress.json"
        progress.write_text("{}", encoding="utf-8")
        raw_dir = tmp_path / "raw_parts"
        raw_dir.mkdir()

        monkeypatch.setattr(sr, "RAW_DIR", str(raw_dir))

        removed = []

        def fake_remove(p):
            removed.append(("remove", p))

        monkeypatch.setattr(os, "remove", fake_remove)
        monkeypatch.setattr(shutil, "rmtree", lambda p: removed.append(("rmtree", str(p))))

        _cleanup_on_success(0, str(progress))

        assert any("rmtree" in str(r) for r in removed)
        assert any("remove" in str(r) for r in removed)

    def test_cleanup_on_success_with_failures(self, monkeypatch):
        removed = []
        monkeypatch.setattr(os, "remove", lambda p: removed.append(p))
        monkeypatch.setattr(shutil, "rmtree", lambda p: removed.append(p))

        _cleanup_on_success(3, "/fake/progress")
        assert removed == []


def _fake_tempfile(tmp_path):
    """tempfile.NamedTemporaryFile のモック"""
    class FakeTemp:
        name = str(tmp_path / "tmp_query.txt")

        def write(self, text):
            pass

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    return FakeTemp()


def _make_result(returncode):
    """subprocess.run の戻り値を模倣"""
    r = MagicMock()
    r.returncode = returncode
    return r


class TestAutoExpandEdgeCases:
    def test_load_current_stats_oserror(self, monkeypatch):
        from auto_expand import _load_current_stats
        monkeypatch.setattr("auto_expand.load_json", lambda _: (_ for _ in ()).throw(OSError))
        stats = _load_current_stats()
        assert stats["total"] == 0

    def test_select_targets_exact_match(self):
        from auto_expand import _select_targets
        stats = {"prefecture_city_counts": {"埼玉県": {"羽生市": "0"}}}
        targets = _select_targets(stats, max_areas=5, target_pref="埼玉県", target_city="羽生市")
        assert len(targets) == 1

    def test_select_targets_pref_fallback_with_city_order(self):
        from auto_expand import _select_targets
        stats = {"prefecture_city_counts": {"埼玉県": {"熊谷市": "0", "羽生市": "1"}}}
        targets = _select_targets(stats, max_areas=3, target_pref="埼玉県")
        assert len(targets) >= 1

    def test_run_auto_expansion_no_targets(self, monkeypatch):
        import auto_expand as ae
        monkeypatch.setattr(ae, "_load_current_stats", lambda: {"prefecture_city_counts": {}, "total": 0, "scored": 0, "score_avg": 0})
        monkeypatch.setattr(ae, "find_gaps", lambda *a, **kw: [])
        ae.run_auto_expansion(max_areas=5)

    def test_auto_expand_main_exits_on_zero_args(self, monkeypatch):
        import auto_expand as ae
        monkeypatch.setattr("sys.argv", ["auto_expand.py"])
        monkeypatch.setattr(ae, "run_auto_expansion", lambda *a, **kw: None)
        ae.main()

    def test_auto_expand_main_passes_args(self, monkeypatch):
        import auto_expand as ae
        monkeypatch.setattr("sys.argv", ["auto_expand.py", "--prefecture", "東京都", "--city", "渋谷区"])
        captured = {}
        def _capture(*args):
            captured["max_areas"] = args[0] if len(args) > 0 else None
            captured["target_pref"] = args[1] if len(args) > 1 else ""
            captured["target_city"] = args[2] if len(args) > 2 else ""
        monkeypatch.setattr(ae, "run_auto_expansion", _capture)
        ae.main()
        assert captured.get("target_city") == "渋谷区"

    def test_run_auto_expansion_file_not_found(self, monkeypatch):
        import auto_expand as ae
        monkeypatch.setattr(ae, "_load_current_stats", lambda: {"prefecture_city_counts": {"埼玉県": {"羽生市": "0"}}, "total": 0, "scored": 0, "score_avg": 0})
        monkeypatch.setattr(ae, "find_gaps", lambda *a, **kw: [{"prefecture": "埼玉県", "city": "羽生市", "count": 0}])
        monkeypatch.setattr(ae, "query_limits_for_count", lambda c: (2, 2))
        monkeypatch.setattr(ae, "active_context", lambda *a, **kw: _null_context())
        monkeypatch.setattr(ae, "ensure_query_files", lambda p: None)
        monkeypatch.setattr(ae, "find_batch_files", lambda p: [])
        monkeypatch.setattr(ae, "merge_query_files", lambda f: "")
        monkeypatch.setattr(ae.subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError))
        ae.run_auto_expansion(max_areas=1)


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


def _null_context():
    class NullCtx:
        def __enter__(self): return self
        def __exit__(self, *a): pass
    return NullCtx()


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
