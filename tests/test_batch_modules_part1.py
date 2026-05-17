"""
tests/test_batch_modules.py
batch modules のモックベースユニットテスト
docker_exec, city_bounds, auto_expand, scrape_runner の関数をテスト
"""
import json
import os
import subprocess
from unittest.mock import MagicMock

from city_bounds import _load_cache, _save_cache
from docker_exec import scrape_query


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



