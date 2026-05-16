"""
tests/test_kanto_phase1.py
Tests for batch/kanto_phase1.py phase 1 scraper

関連: batch/kanto_phase1.py, batch/expansion_query.py, batch/scrape_runner.py
"""
import os
import subprocess

import kanto_phase1


class TestPhaseProgress:
    def test_load_phase_progress_returns_empty_when_no_file(self, tmp_path):
        kanto_phase1.PHASE_PROGRESS = str(tmp_path / "nonexistent")
        assert kanto_phase1.load_phase_progress() == set()

    def test_save_and_load_phase_progress(self, tmp_path):
        progress_file = tmp_path / ".kanto_progress"
        kanto_phase1.PHASE_PROGRESS = str(progress_file)
        kanto_phase1.save_phase_progress({"東京都", "埼玉県"})
        loaded = kanto_phase1.load_phase_progress()
        assert loaded == {"東京都", "埼玉県"}

    def test_load_phase_progress_skips_empty_lines(self, tmp_path):
        progress_file = tmp_path / ".kanto_progress"
        progress_file.write_text("東京都\n\n埼玉県\n\n", encoding="utf-8")
        kanto_phase1.PHASE_PROGRESS = str(progress_file)
        loaded = kanto_phase1.load_phase_progress()
        assert loaded == {"東京都", "埼玉県"}

    def test_save_phase_progress_sorts_prefectures(self, tmp_path):
        progress_file = tmp_path / ".kanto_progress"
        kanto_phase1.PHASE_PROGRESS = str(progress_file)
        kanto_phase1.save_phase_progress({"埼玉県", "東京都", "神奈川県"})
        lines = progress_file.read_text(encoding="utf-8").strip().splitlines()
        assert lines == sorted(["埼玉県", "東京都", "神奈川県"])


class TestResolveQueryPath:
    def test_returns_first_batch_file(self, tmp_path, monkeypatch):
        import expansion_query
        base_dir = tmp_path / "batch"
        pref_dir = base_dir / "queries.d" / "東京都"
        pref_dir.mkdir(parents=True)
        (pref_dir / "batch_003.txt").write_text("q1\n", encoding="utf-8")
        (pref_dir / "batch_001.txt").write_text("q2\n", encoding="utf-8")

        monkeypatch.setattr(expansion_query, "QUERIES_DIR", str(base_dir / "queries.d"))
        monkeypatch.setattr(kanto_phase1, "SCRIPT_DIR", str(base_dir))
        result = kanto_phase1._resolve_query_path("東京都")
        assert result.name == "batch_001.txt"

    def test_fallback_when_no_batch_files(self, tmp_path, monkeypatch):
        import expansion_query
        base_dir = tmp_path / "batch"
        base_dir.mkdir()
        monkeypatch.setattr(expansion_query, "QUERIES_DIR", str(base_dir / "queries.d"))
        monkeypatch.setattr(kanto_phase1, "SCRIPT_DIR", str(base_dir))
        result = kanto_phase1._resolve_query_path("未知の県")
        assert str(result) == os.path.join(str(base_dir), "queries.d", "未知の県", "batch_001.txt")


class TestRunScrape:
    def _setup(self, tmp_path, monkeypatch):
        base_dir = tmp_path / "batch"
        base_dir.mkdir()
        queries_path = base_dir / "queries.txt"
        queries_path.write_text("q1\nq2\n", encoding="utf-8")
        monkeypatch.setattr(kanto_phase1, "SCRIPT_DIR", str(base_dir))
        return base_dir, queries_path

    def test_skip_when_progress_complete(self, tmp_path, monkeypatch):
        base_dir, queries_path = self._setup(tmp_path, monkeypatch)
        prog_file = base_dir / ".progress_test_pref_phase1"
        prog_file.write_text("2\n", encoding="utf-8")
        result = kanto_phase1.run_scrape("test_pref", "test_city", queries_path)
        assert result is True

    def test_returns_false_on_timeout(self, tmp_path, monkeypatch):
        base_dir, queries_path = self._setup(tmp_path, monkeypatch)

        def fake_run(cmd, env=None, cwd=None, timeout=None):
            raise subprocess.TimeoutExpired(cmd="", timeout=3600)

        monkeypatch.setattr(kanto_phase1.subprocess, "run", fake_run)
        result = kanto_phase1.run_scrape("test_pref", "test_city", queries_path)
        assert result is False

    def test_returns_false_on_file_not_found(self, tmp_path, monkeypatch):
        base_dir, queries_path = self._setup(tmp_path, monkeypatch)

        def fake_run(cmd, env=None, cwd=None, timeout=None):
            raise FileNotFoundError()

        monkeypatch.setattr(kanto_phase1.subprocess, "run", fake_run)
        result = kanto_phase1.run_scrape("test_pref", "test_city", queries_path)
        assert result is False

    def test_returns_false_on_oserror(self, tmp_path, monkeypatch):
        base_dir, queries_path = self._setup(tmp_path, monkeypatch)

        def fake_run(cmd, env=None, cwd=None, timeout=None):
            raise OSError("Docker not available")

        monkeypatch.setattr(kanto_phase1.subprocess, "run", fake_run)
        result = kanto_phase1.run_scrape("test_pref", "test_city", queries_path)
        assert result is False

    def test_returns_false_on_nonzero_exit(self, tmp_path, monkeypatch):
        base_dir, queries_path = self._setup(tmp_path, monkeypatch)

        class Result:
            returncode = 1

        def fake_run(cmd, env=None, cwd=None, timeout=None):
            return Result()

        monkeypatch.setattr(kanto_phase1.subprocess, "run", fake_run)
        result = kanto_phase1.run_scrape("test_pref", "test_city", queries_path)
        assert result is False

    def test_success_returns_true(self, tmp_path, monkeypatch):
        base_dir, queries_path = self._setup(tmp_path, monkeypatch)

        class Result:
            returncode = 0

        def fake_run(cmd, env=None, cwd=None, timeout=None):
            return Result()

        monkeypatch.setattr(kanto_phase1.subprocess, "run", fake_run)
        result = kanto_phase1.run_scrape("test_pref", "test_city", queries_path)
        assert result is True
