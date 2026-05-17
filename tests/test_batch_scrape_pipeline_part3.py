"""
tests/test_batch_scrape_pipeline.py
スクレイピングパイプライン関連の回帰テスト（test_batch_regressions.py から分割）
"""
from pathlib import Path


class TestSlugify:
    def test_special_chars_become_underscore(self):
        import expansion_query as eq
        assert eq._slugify("東京・渋谷") == "東京_渋谷"

    def test_alphanumeric_passed_through(self):
        import expansion_query as eq
        assert eq._slugify("abc123") == "abc123"

    def test_empty_returns_all(self):
        import expansion_query as eq
        assert eq._slugify("") == "all"



class TestLoadQueryLines:
    def test_os_error_returns_empty(self, tmp_path):
        import expansion_query as eq
        result = eq._load_query_lines(tmp_path / "nonexistent.txt")
        assert result == []

    def test_skips_comments_and_empty(self, tmp_path):
        import expansion_query as eq
        p = tmp_path / "queries.txt"
        p.write_text("# comment\n\nq1\nq2\n", encoding="utf-8")
        result = eq._load_query_lines(p)
        assert result == ["q1", "q2"]



class TestFileMentionsCity:
    def test_empty_city_returns_false(self, tmp_path):
        import expansion_query as eq
        p = tmp_path / "q.txt"
        p.write_text("東京 トイレ\n", encoding="utf-8")
        assert eq._file_mentions_city(p, "") is False



class TestNextBatchIndex:
    def test_parses_batch_indices(self, tmp_path):
        import expansion_query as eq
        (tmp_path / "batch_003.txt").write_text("", encoding="utf-8")
        (tmp_path / "batch_001.txt").write_text("", encoding="utf-8")
        (tmp_path / "batch_005.txt").write_text("", encoding="utf-8")
        assert eq._next_batch_index(tmp_path) == 6

    def test_no_files_returns_one(self, tmp_path):
        import expansion_query as eq
        assert eq._next_batch_index(tmp_path) == 1

    def test_skips_invalid_filenames(self, tmp_path):
        import expansion_query as eq
        (tmp_path / "batch_abc.txt").write_text("", encoding="utf-8")
        (tmp_path / "batch_002.txt").write_text("", encoding="utf-8")
        assert eq._next_batch_index(tmp_path) == 3



class TestFindBatchFiles:
    def test_returns_empty_when_dir_missing(self, tmp_path, monkeypatch):
        import expansion_query as eq
        monkeypatch.setattr(eq, "QUERIES_DIR", str(tmp_path / "nonexistent"))
        assert eq.find_batch_files("東京都") == []



class TestEnsureQueryFiles:
    def test_creates_target_file(self, tmp_path, monkeypatch):
        import expansion_query as eq
        eq.reset_context()
        monkeypatch.setattr(eq, "QUERIES_DIR", str(tmp_path))
        eq.set_active_context("東京都", "渋谷区")
        monkeypatch.setattr(eq, "build_queries", lambda labels, templates: ["q1"])
        eq.ensure_query_files("東京都")
        target = tmp_path / "東京都" / "batch_001_target.txt"
        assert target.exists()
        content = target.read_text(encoding="utf-8")
        assert "渋谷区" in content

    def test_no_active_city_returns_early(self, tmp_path, monkeypatch):
        import expansion_query as eq
        eq.reset_context()
        monkeypatch.setattr(eq, "QUERIES_DIR", str(tmp_path))
        eq.ensure_query_files("東京都")
        pref_dir = tmp_path / "東京都"
        assert pref_dir.exists()
        assert not any(pref_dir.iterdir())

    def test_skip_pref_queries_when_already_exists(self, tmp_path, monkeypatch):
        import expansion_query as eq
        eq.reset_context()
        monkeypatch.setattr(eq, "QUERIES_DIR", str(tmp_path))
        eq.set_active_context("東京都", "渋谷区")
        monkeypatch.setattr(eq, "build_queries", lambda labels, templates: ["q1"])
        pref_dir = tmp_path / "東京都"
        pref_dir.mkdir(parents=True, exist_ok=True)
        (pref_dir / "batch_001.txt").write_text(
            "# prefecture: 東京都\nq_prev\n", encoding="utf-8"
        )
        calls = []
        monkeypatch.setattr(eq, "write_batches", lambda *a, **kw: calls.append(1))
        eq.ensure_query_files("東京都")
        assert len(calls) == 0  # write_batches should NOT be called



class TestMergeQueryFilesBudget:
    def test_budget_exceeded_stops_adding(self, tmp_path, monkeypatch):
        import expansion_query as eq
        eq.reset_context()
        eq.set_active_context("東京都", "渋谷区", city_budget=1, pref_budget=1)
        city_file = tmp_path / "city.txt"
        city_file.write_text("# city: 渋谷区\nq1\nq2\nq3\n", encoding="utf-8")
        result = eq.merge_query_files([str(city_file)])
        assert result != ""
        # Should have at most the budgeted lines
        lines = Path(result).read_text(encoding="utf-8").strip().split("\n")
        content_lines = [ln for ln in lines if not ln.startswith("#")]
        assert len(content_lines) == 1  # only 1 city query due to budget=1

    def test_skips_nonexistent_files(self, tmp_path):
        import expansion_query as eq
        result = eq.merge_query_files([str(tmp_path / "nope.txt")])
        assert result == ""

