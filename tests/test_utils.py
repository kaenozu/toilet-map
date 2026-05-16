"""
tests/test_utils.py
batch/utils.py のユニットテスト
"""
import gzip
import json
import os
import sys
from unittest.mock import MagicMock

import pytest
import utils as batch_utils


class TestLoadJsonl:
    def test_path_not_exists_returns_empty_list(self, tmp_path):
        result = batch_utils.load_jsonl(str(tmp_path / "nonexistent.jsonl"))
        assert result == []

    def test_loads_valid_jsonl(self, tmp_path):
        path = tmp_path / "data.jsonl"
        path.write_text(
            '{"a": 1}\n{"a": 2}\n{"a": 3}\n',
            encoding="utf-8"
        )
        result = batch_utils.load_jsonl(str(path))
        assert result == [{"a": 1}, {"a": 2}, {"a": 3}]

    def test_skips_empty_lines(self, tmp_path):
        path = tmp_path / "data.jsonl"
        path.write_text('{"a": 1}\n\n{"a": 2}\n\n', encoding="utf-8")
        result = batch_utils.load_jsonl(str(path))
        assert result == [{"a": 1}, {"a": 2}]

    def test_skips_invalid_json_lines(self, tmp_path, caplog):
        path = tmp_path / "data.jsonl"
        path.write_text(
            '{"a": 1}\ninvalid json\n{"a": 2}\n',
            encoding="utf-8"
        )
        result = batch_utils.load_jsonl(str(path))
        assert result == [{"a": 1}, {"a": 2}]
        assert "Failed to decode JSON line" in caplog.text


class TestSaveJson:
    def test_saves_without_compress(self, tmp_path):
        path = str(tmp_path / "out.json")
        data = {"key": "value", "num": 42}
        batch_utils.save_json(path, data, indent=2)
        loaded = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
        assert loaded == data

    def test_saves_with_compress(self, tmp_path):
        path = str(tmp_path / "out.json")
        data = {"key": "value"}
        batch_utils.save_json(path, data, compress=True)
        gz_path = tmp_path / "out.json.gz"
        assert gz_path.exists()
        with gzip.open(gz_path, "rt", encoding="utf-8") as f:
            assert json.load(f) == data

    def test_saves_with_compress_and_already_gz(self, tmp_path):
        path = str(tmp_path / "out.json.gz")
        data = {"key": "value"}
        batch_utils.save_json(path, data, compress=True)
        with gzip.open(tmp_path / "out.json.gz", "rt") as f:
            assert json.loads(f.read()) == data


class TestCountLines:
    def test_file_not_exists_returns_zero(self, tmp_path):
        assert batch_utils.count_lines(str(tmp_path / "nonexistent.txt")) == 0

    def test_counts_non_empty_non_comment_lines(self, tmp_path):
        path = tmp_path / "queries.txt"
        path.write_text(
            "# comment line\nquery1\n\nquery2\n# another comment\nquery3\n",
            encoding="utf-8"
        )
        assert batch_utils.count_lines(str(path)) == 3


class TestEnsureDir:
    def test_creates_directory(self, tmp_path):
        d = str(tmp_path / "new" / "dir")
        batch_utils.ensure_dir(d)
        assert os.path.isdir(d)

    def test_existing_directory_does_not_raise(self, tmp_path):
        d = str(tmp_path / "existing")
        os.makedirs(d, exist_ok=True)
        batch_utils.ensure_dir(d)
        assert os.path.isdir(d)


class TestReadJsonFile:
    def test_file_not_exists_returns_default(self, tmp_path):
        result = batch_utils.read_json_file(str(tmp_path / "nonexistent.json"), [])
        assert result == []

    def test_reads_valid_json(self, tmp_path):
        path = tmp_path / "data.json"
        path.write_text('{"a": 1}', encoding="utf-8")
        assert batch_utils.read_json_file(str(path), {}) == {"a": 1}

    def test_invalid_json_returns_default(self, tmp_path, caplog):
        path = tmp_path / "bad.json"
        path.write_text("not-json", encoding="utf-8")
        result = batch_utils.read_json_file(str(path), {"default": True})
        assert result == {"default": True}
        assert "Failed to read JSON file" in caplog.text


class TestWriteJsonAtomic:
    def test_writes_json_atomically(self, tmp_path):
        path = str(tmp_path / "atomic.json")
        data = {"key": "value"}
        batch_utils.write_json_atomic(path, data)
        assert json.loads((tmp_path / "atomic.json").read_text(encoding="utf-8")) == data

    def test_creates_parent_directory(self, tmp_path):
        path = str(tmp_path / "sub" / "nested" / "atomic.json")
        batch_utils.write_json_atomic(path, {"a": 1})
        assert json.loads((tmp_path / "sub" / "nested" / "atomic.json").read_text(encoding="utf-8")) == {"a": 1}

    def test_cleanup_oserror_logs_warning(self, tmp_path, caplog, monkeypatch):
        path = str(tmp_path / "atomic.json")
        monkeypatch.setattr(os, "replace", MagicMock(side_effect=OSError("replace failed")))
        monkeypatch.setattr(os, "remove", MagicMock(side_effect=OSError("remove failed")))

        with pytest.raises(OSError):
            batch_utils.write_json_atomic(path, {"data": 1})
        assert "Could not remove temporary file" in caplog.text


class TestUpdateExpansionStatus:
    def test_remove_run(self, tmp_path, monkeypatch):
        monkeypatch.setattr(batch_utils, "EXPANSION_STATUS_PATH", str(tmp_path / "status.json"))
        monkeypatch.setattr(batch_utils, "EXPANSION_STATUS_LOCK_PATH", str(tmp_path / "status.lock"))
        batch_utils.update_expansion_status("run-a", {"status": "running"})
        batch_utils.update_expansion_status("run-a", remove=True)
        data = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
        assert len(data["runs"]) == 0

    def test_stale_entry_is_cleaned(self, tmp_path, monkeypatch):
        monkeypatch.setattr(batch_utils, "EXPANSION_STATUS_PATH", str(tmp_path / "status.json"))
        monkeypatch.setattr(batch_utils, "EXPANSION_STATUS_LOCK_PATH", str(tmp_path / "status.lock"))
        monkeypatch.setattr(batch_utils, "EXPANSION_STATUS_RETENTION_SEC", -1)
        batch_utils.update_expansion_status("run-a", {"status": "completed"})
        batch_utils.update_expansion_status("run-b", {"status": "running"})
        data = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
        run_ids = {r["run_id"] for r in data["runs"]}
        assert "run-b" in run_ids


class TestExtractPrefecture:
    def test_empty_address_returns_empty(self):
        assert batch_utils.extract_prefecture("") == ""
        assert batch_utils.extract_prefecture(None) == ""

    def test_direct_prefecture_match(self):
        assert batch_utils.extract_prefecture("東京都渋谷区") == "東京都"
        assert batch_utils.extract_prefecture("大阪府大阪市") == "大阪府"

    def test_alias_match(self):
        assert batch_utils.extract_prefecture("東京渋谷区") == "東京都"
        assert batch_utils.extract_prefecture("大阪市北区") == "大阪府"

    def test_hokkaido_fallback(self):
        assert batch_utils.extract_prefecture("北海道札幌市") == "北海道"
        assert batch_utils.extract_prefecture("札幌市北海道") == "北海道"

    def test_no_match_returns_empty(self):
        assert batch_utils.extract_prefecture("海外住所") == ""

    def test_normalize_removes_spaces_and_symbols(self):
        assert batch_utils.extract_prefecture("東 京 都 渋谷区") == "東京都"
        assert batch_utils.extract_prefecture("大阪・府大阪市") == "大阪府"

    def test_no_match_after_alias_falls_through(self):
        assert batch_utils.extract_prefecture("完全に未知の住所") == ""


class TestRuntimeError:
    def test_file_lock_runtime_error(self, monkeypatch):
        monkeypatch.setattr("utils.msvcrt", None)
        monkeypatch.setattr("utils.fcntl", None)
        with pytest.raises(RuntimeError, match="File locking is not supported"), batch_utils.file_lock("/tmp/nonexistent/test.lock"):
            pass


class TestFileLock:
    @pytest.mark.skipif(sys.platform == "win32", reason="fcntl not available on Windows")
    def test_file_lock_timeout(self, tmp_path):
        lock_path = str(tmp_path / "test.lock")
        import fcntl as fcntl_mod
        original_flock = fcntl_mod.flock

        def _block_flock(*a, **kw):
            raise OSError("Resource temporarily unavailable")

        fcntl_mod.flock = _block_flock
        try:
            with pytest.raises(TimeoutError), batch_utils.file_lock(lock_path, timeout=0.1, poll_interval=0.05):
                pass
        finally:
            fcntl_mod.flock = original_flock


class TestScoreConfigImport:
    """`utils.py` の `from scoring_config import PREFECTURES` が正しく
     import できていることを確認するためのスモークテスト"""

    def test_prefectures_list_is_loaded(self):
        assert len(batch_utils.PREFECTURES) > 0
        assert "東京都" in batch_utils.PREFECTURES
