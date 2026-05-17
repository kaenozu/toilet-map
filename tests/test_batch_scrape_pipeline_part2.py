"""
tests/test_batch_scrape_pipeline.py
スクレイピングパイプライン関連の回帰テスト（test_batch_regressions.py から分割）
"""
from pathlib import Path

import auto_expand
import pipeline
import pytest
import scrape_runner
from generate_queries import build_queries, write_batches


class TestExpansionQueryModule:
    def test_read_query_header_parses_city_and_pref(self, tmp_path):
        import expansion_query as eq
        path = tmp_path / "batch_001.txt"
        path.write_text("# city: 渋谷区\n# prefecture: 東京都\nq1\n", encoding="utf-8")
        city, pref = eq._read_query_header(path)
        assert city == "渋谷区"
        assert pref == "東京都"

    def test_read_query_header_returns_empty_for_no_header(self, tmp_path):
        import expansion_query as eq
        path = tmp_path / "batch_001.txt"
        path.write_text("q1\nq2\n", encoding="utf-8")
        city, pref = eq._read_query_header(path)
        assert city == ""
        assert pref == ""

    def test_read_query_header_handles_missing_file(self, tmp_path):
        import expansion_query as eq
        path = tmp_path / "nonexistent.txt"
        result = eq._read_query_header(path)
        assert result == ("", "")

    def test_classify_query_file_identifies_city(self, tmp_path):
        import expansion_query as eq
        eq.reset_context()
        eq.set_active_context("東京都", "渋谷区")
        path = tmp_path / "batch_target.txt"
        path.write_text("# city: 渋谷区\n# prefecture: 東京都\nq1\n", encoding="utf-8")
        bucket = eq._classify_query_file(path)
        assert bucket == "city"
        eq.reset_context()

    def test_classify_query_file_identifies_pref(self, tmp_path):
        import expansion_query as eq
        eq.reset_context()
        eq.set_active_context("東京都", "渋谷区")
        path = tmp_path / "batch_pref.txt"
        path.write_text("# prefecture: 東京都\nq1\nq2\n", encoding="utf-8")
        bucket = eq._classify_query_file(path)
        assert bucket == "pref"
        eq.reset_context()

    def test_no_active_city_returns_pref_when_no_header_city(self, tmp_path):
        import expansion_query as eq
        eq.reset_context()
        path = tmp_path / "batch_no_city.txt"
        path.write_text("# prefecture: 東京都\nq1\n", encoding="utf-8")
        bucket = eq._classify_query_file(path)
        assert bucket == "pref"
        eq.reset_context()

    def test_returns_city_when_header_matches(self, tmp_path):
        import expansion_query as eq
        eq.reset_context()
        path = tmp_path / "batch_has_city.txt"
        path.write_text("# city: 渋谷区\nq1\n", encoding="utf-8")
        bucket = eq._classify_query_file(path)
        assert bucket == "city"
        eq.reset_context()

    def test_classify_rejects_wrong_city(self, tmp_path):
        import expansion_query as eq
        eq.reset_context()
        eq.set_active_context("東京都", "渋谷区")
        path = tmp_path / "batch_wrong.txt"
        path.write_text("# city: 新宿区\nq1\n", encoding="utf-8")
        bucket = eq._classify_query_file(path)
        assert bucket == ""
        eq.reset_context()

    def test_classify_rejects_wrong_pref(self, tmp_path):
        import expansion_query as eq
        eq.reset_context()
        eq.set_active_context("大阪府", "大阪市")
        path = tmp_path / "batch_wrong_pref.txt"
        path.write_text("# prefecture: 東京都\nq1\n", encoding="utf-8")
        bucket = eq._classify_query_file(path)
        assert bucket == ""
        eq.reset_context()

    def test_merge_query_files_combines_city_and_pref(self, tmp_path):
        import expansion_query as eq
        eq.reset_context()
        eq.set_active_context("東京都", "渋谷区", city_budget=2, pref_budget=2)

        city_file = tmp_path / "city.txt"
        city_file.write_text("# city: 渋谷区\ncity_q1\ncity_q2\ncity_q3\n", encoding="utf-8")
        pref_file = tmp_path / "pref.txt"
        pref_file.write_text("# prefecture: 東京都\npref_q1\npref_q2\n", encoding="utf-8")

        result = eq.merge_query_files([str(city_file), str(pref_file)])
        assert result
        content = Path(result).read_text(encoding="utf-8")
        assert "city_q1" in content
        assert "city_q2" in content
        assert "city_q3" not in content
        assert "pref_q1" in content
        assert "pref_q2" in content
        Path(result).unlink()
        eq.reset_context()

    def test_merge_query_files_deduplicates(self, tmp_path):
        import expansion_query as eq
        eq.reset_context()
        eq.set_active_context("東京都", "渋谷区", city_budget=10, pref_budget=10)

        city_file = tmp_path / "city.txt"
        city_file.write_text("# city: 渋谷区\ndup_q1\ndup_q2\n", encoding="utf-8")
        pref_file = tmp_path / "pref.txt"
        pref_file.write_text("# prefecture: 東京都\ndup_q1\ndup_q2\n", encoding="utf-8")

        result = eq.merge_query_files([str(city_file), str(pref_file)])
        content = Path(result).read_text(encoding="utf-8")
        assert content.count("dup_q1") == 1
        assert content.count("dup_q2") == 1
        Path(result).unlink()
        eq.reset_context()

    def test_merge_query_files_returns_empty_for_no_input(self):
        import expansion_query as eq
        eq.reset_context()
        eq.set_active_context("東京都", "渋谷区", city_budget=0, pref_budget=0)
        result = eq.merge_query_files([])
        assert result == ""
        eq.reset_context()

    def test_merge_query_files_skips_unmatched_bucket(self, tmp_path):
        import expansion_query as eq
        eq.reset_context()
        eq.set_active_context("東京都", "渋谷区")
        no_city = tmp_path / "no_city.txt"
        no_city.write_text("q_without_header\n", encoding="utf-8")
        result = eq.merge_query_files([str(no_city)])
        # no header = pref (when target_city is set but header has no city)
        assert result != ""
        Path(result).unlink()
        eq.reset_context()


class TestQueryGeneration:
    def test_write_batches_does_not_overwrite_previous_city(self, tmp_path):
        output_dir = tmp_path / "queries"

        first = write_batches(["q1", "q2"], str(output_dir), city="A", prefecture="P", start_index=1)
        second = write_batches(["q3", "q4"], str(output_dir), city="B", prefecture="P", start_index=first + 1)

        assert first == 1
        assert second == 1
        assert (output_dir / "batch_001.txt").exists()
        assert (output_dir / "batch_002.txt").exists()
        assert "q1" in (output_dir / "batch_001.txt").read_text(encoding="utf-8")
        assert "q3" in (output_dir / "batch_002.txt").read_text(encoding="utf-8")

    def test_build_queries_deduplicates_repeated_inputs(self):
        queries = build_queries(["大阪市", "大阪市"], ["トイレ in {city}"])

        assert queries == ["トイレ in 大阪市"]



class TestPostProcessPipeline:
    def test_run_postprocess_pipeline_converts_sqlite_incrementally(self, monkeypatch):
        calls = []

        class Result:
            returncode = 0

        def fake_run(cmd):
            calls.append(cmd)
            return Result()

        monkeypatch.setattr(pipeline.subprocess, "run", fake_run)

        pipeline.run_postprocess_pipeline("input.json", "output.json.gz", ".")

        assert len(calls) == 2
        assert calls[0][-1] == "--incremental"
        assert calls[1][1].endswith("to_sqlite.py")
        assert calls[1][-1] == "--incremental"

    def test_run_postprocess_pipeline_raises_when_sqlite_conversion_fails(self, monkeypatch):
        class Result:
            def __init__(self, returncode):
                self.returncode = returncode

        calls = iter([Result(0), Result(1)])
        monkeypatch.setattr(pipeline.subprocess, "run", lambda cmd: next(calls))

        with pytest.raises((RuntimeError, pipeline.DataError)):
            pipeline.run_postprocess_pipeline("input.json", "output.json.gz", ".")

    def test_maybe_sync_after_success_triggers_on_interval(self, monkeypatch):
        calls = []

        monkeypatch.setattr(scrape_runner, "SYNC_EVERY_SUCCESS", 2)
        monkeypatch.setattr(scrape_runner, "_sync_canonical_data", lambda city, pref: calls.append((city, pref)))

        scrape_runner._maybe_sync_after_success("名古屋市", "愛知県", 1)
        scrape_runner._maybe_sync_after_success("名古屋市", "愛知県", 2)

        assert calls == [("名古屋市", "愛知県")]

    def test_auto_expand_enables_incremental_sync(self, monkeypatch, tmp_path):
        temp_query = tmp_path / "queries.txt"
        temp_query.write_text("q1\n", encoding="utf-8")

        monkeypatch.setattr(auto_expand, "ensure_query_files", lambda pref: None)
        monkeypatch.setattr(auto_expand, "find_batch_files", lambda pref: [temp_query])
        monkeypatch.setattr(auto_expand, "merge_query_files", lambda files: str(temp_query))

        captured_env = {}

        def fake_run(cmd, check=None, cwd=None, env=None):
            captured_env.update(env or {})
            class Result:
                returncode = 0
            return Result()

        monkeypatch.setattr(auto_expand.subprocess, "run", fake_run)

        auto_expand.run_auto_expansion(max_areas=1, target_city="名古屋市", target_pref="愛知県")

        assert captured_env["SYNC_EVERY_SUCCESS"] == "1"

    def test_auto_expand_query_budget_scales_with_gap_size(self):
        assert auto_expand.query_limits_for_count(0) == (8, 4)
        assert auto_expand.query_limits_for_count(2) == (12, 4)
        assert auto_expand.query_limits_for_count(4) == (16, 6)
        assert auto_expand.query_limits_for_count(6) == (
            len(auto_expand.CITY_QUERY_BUDGET_TEMPLATES),
            len(auto_expand.PREFECTURE_QUERY_BUDGET_TEMPLATES),
        )



