"""
tests/test_expansion_query.py
Tests for batch/expansion_query.py query file management

関連: batch/expansion_query.py, batch/auto_expand.py, batch/kanto_phase1.py
"""
from pathlib import Path

from expansion_query import (
    SCOPED_CITY_TEMPLATES,
    SCOPED_PREFECTURE_TEMPLATES,
    _file_mentions_city,
    _load_query_lines,
    _next_batch_index,
    _read_query_header,
    _slugify,
    active_context,
    find_batch_files,
    merge_query_files,
    query_limits_for_count,
    reset_context,
    set_active_context,
)


class TestContextManagement:
    def test_reset_clears_all_fields(self):
        reset_context()
        set_active_context("東京都", "渋谷区", 10, 5)
        reset_context()
        prev = set_active_context("埼玉県", "さいたま市")
        assert prev == ("", "", 0, 0)

    def test_set_active_context_returns_previous(self):
        reset_context()
        set_active_context("東京都", "千代田区", 5, 3)
        prev = set_active_context("埼玉県", "さいたま市", 8, 4)
        assert prev == ("東京都", "千代田区", 5, 3)

    def test_active_context_restores_previous(self):
        reset_context()
        set_active_context("東京都", "千代田区", 5, 3)
        with active_context("埼玉県", "さいたま市", 8, 4):
            pass
        from expansion_query import _ctx
        assert _ctx.target_pref == "東京都"
        assert _ctx.target_city == "千代田区"

    def test_active_context_restores_even_on_error(self):
        reset_context()
        set_active_context("東京都", "千代田区")
        try:
            with active_context("埼玉県", "さいたま市"):
                raise ValueError("something went wrong")
        except ValueError:
            pass
        from expansion_query import _ctx
        assert _ctx.target_pref == "東京都"


class TestQueryLimitsForCount:
    def test_zero_returns_max_budget(self):
        assert query_limits_for_count(0) == (8, 4)

    def test_less_than_four_returns_medium_budget(self):
        assert query_limits_for_count(2) == (12, 4)

    def test_less_than_six_returns_large_budget(self):
        assert query_limits_for_count(4) == (16, 6)

    def test_six_or_more_returns_full_templates(self):
        expected = (len(SCOPED_CITY_TEMPLATES), len(SCOPED_PREFECTURE_TEMPLATES))
        assert query_limits_for_count(6) == expected
        assert query_limits_for_count(100) == expected


class TestSlugify:
    def test_special_chars_become_underscore(self):
        assert _slugify("東京・渋谷") == "東京_渋谷"

    def test_alphanumeric_preserved(self):
        assert _slugify("abc123") == "abc123"

    def test_hyphen_and_underscore_preserved(self):
        assert _slugify("test-area_name") == "test-area_name"

    def test_empty_returns_all(self):
        assert _slugify("") == "all"

    def test_only_special_chars_returns_all(self):
        assert _slugify("...!!!") == "all"


class TestLoadQueryLines:
    def test_nonexistent_file_returns_empty(self, tmp_path):
        assert _load_query_lines(tmp_path / "nonexistent.txt") == []

    def test_skips_comments_and_empty_lines(self, tmp_path):
        p = tmp_path / "queries.txt"
        p.write_text("# comment\n\nq1\nq2\n  # indented comment\n\n", encoding="utf-8")
        assert _load_query_lines(p) == ["q1", "q2"]


class TestReadQueryHeader:
    def test_parses_city_and_pref(self, tmp_path):
        path = tmp_path / "batch_001.txt"
        path.write_text("# city: 渋谷区\n# prefecture: 東京都\nq1\n", encoding="utf-8")
        assert _read_query_header(path) == ("渋谷区", "東京都")

    def test_no_header_returns_empty(self, tmp_path):
        path = tmp_path / "batch_001.txt"
        path.write_text("q1\nq2\n", encoding="utf-8")
        assert _read_query_header(path) == ("", "")

    def test_missing_file_returns_empty(self, tmp_path):
        assert _read_query_header(tmp_path / "nonexistent.txt") == ("", "")

    def test_partial_header(self, tmp_path):
        path = tmp_path / "batch_001.txt"
        path.write_text("# city: 渋谷区\nq1\n", encoding="utf-8")
        city, pref = _read_query_header(path)
        assert city == "渋谷区"
        assert pref == ""


class TestFileMentionsCity:
    def test_empty_city_returns_false(self, tmp_path):
        p = tmp_path / "q.txt"
        p.write_text("東京 トイレ\n", encoding="utf-8")
        assert _file_mentions_city(p, "") is False

    def test_city_in_lines_returns_true(self, tmp_path):
        p = tmp_path / "q.txt"
        p.write_text("新宿区 トイレ\n渋谷区 公園\n", encoding="utf-8")
        assert _file_mentions_city(p, "新宿区") is True

    def test_city_not_in_lines_returns_false(self, tmp_path):
        p = tmp_path / "q.txt"
        p.write_text("千代田区 トイレ\n", encoding="utf-8")
        assert _file_mentions_city(p, "新宿区") is False


class TestNextBatchIndex:
    def test_no_files_returns_one(self, tmp_path):
        assert _next_batch_index(tmp_path) == 1

    def test_empty_dir_returns_one(self, tmp_path):
        assert _next_batch_index(tmp_path) == 1

    def test_parses_indices_correctly(self, tmp_path):
        (tmp_path / "batch_003.txt").write_text("", encoding="utf-8")
        (tmp_path / "batch_001.txt").write_text("", encoding="utf-8")
        (tmp_path / "batch_005.txt").write_text("", encoding="utf-8")
        assert _next_batch_index(tmp_path) == 6

    def test_skips_invalid_filenames(self, tmp_path):
        (tmp_path / "batch_abc.txt").write_text("", encoding="utf-8")
        (tmp_path / "batch_002.txt").write_text("", encoding="utf-8")
        assert _next_batch_index(tmp_path) == 3


class TestFindBatchFiles:
    def test_returns_empty_when_dir_missing(self, tmp_path, monkeypatch):
        import expansion_query as eq
        monkeypatch.setattr(eq, "QUERIES_DIR", str(tmp_path / "nonexistent"))
        assert find_batch_files("東京都") == []

    def test_returns_sorted_files(self, tmp_path, monkeypatch):
        import expansion_query as eq
        monkeypatch.setattr(eq, "QUERIES_DIR", str(tmp_path))
        pref_dir = tmp_path / "test_pref"
        pref_dir.mkdir(parents=True)
        (pref_dir / "batch_002.txt").write_text("q2\n", encoding="utf-8")
        (pref_dir / "batch_001.txt").write_text("q1\n", encoding="utf-8")
        monkeypatch.setattr(eq, "QUERIES_DIR", str(tmp_path))
        # find_batch_files uses QUERIES_DIR internally to build pref path
        result = find_batch_files("test_pref")
        assert len(result) == 2
        assert result[0].name == "batch_001.txt"


class TestMergeQueryFiles:
    def test_empty_file_list_returns_empty(self):
        reset_context()
        set_active_context("東京都", "渋谷区", city_budget=0, pref_budget=0)
        assert merge_query_files([]) == ""
        reset_context()

    def test_skips_nonexistent_files(self, tmp_path):
        reset_context()
        set_active_context("東京都", "渋谷区", city_budget=0, pref_budget=0)
        result = merge_query_files([str(tmp_path / "nope.txt")])
        assert result == ""
        reset_context()

    def test_respects_budget(self, tmp_path):
        reset_context()
        set_active_context("東京都", "渋谷区", city_budget=2, pref_budget=2)
        city_file = tmp_path / "city.txt"
        city_file.write_text("# city: 渋谷区\nq1\nq2\nq3\nq4\n", encoding="utf-8")
        pref_file = tmp_path / "pref.txt"
        pref_file.write_text("# prefecture: 東京都\np1\np2\np3\n", encoding="utf-8")

        result = merge_query_files([str(city_file), str(pref_file)])
        assert result
        content = Path(result).read_text(encoding="utf-8")
        city_lines = [ln for ln in content.splitlines() if ln in ("q1", "q2", "q3", "q4")]
        pref_lines = [ln for ln in content.splitlines() if ln in ("p1", "p2", "p3")]
        assert len(city_lines) == 2
        assert len(pref_lines) == 2
        Path(result).unlink()
        reset_context()

    def test_deduplicates_across_buckets(self, tmp_path):
        reset_context()
        set_active_context("東京都", "渋谷区", city_budget=10, pref_budget=10)
        city_file = tmp_path / "city.txt"
        city_file.write_text("# city: 渋谷区\ndup_q1\n", encoding="utf-8")
        pref_file = tmp_path / "pref.txt"
        pref_file.write_text("# prefecture: 東京都\ndup_q1\n", encoding="utf-8")
        result = merge_query_files([str(city_file), str(pref_file)])
        content = Path(result).read_text(encoding="utf-8")
        assert content.count("dup_q1") == 1
        Path(result).unlink()
        reset_context()
