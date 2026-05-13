"""
tests/test_batch_scrape_pipeline.py
スクレイピングパイプライン関連の回帰テスト（test_batch_regressions.py から分割）
"""
import json
from pathlib import Path

import pytest

import process_data as pd_module
from generate_queries import build_queries, write_batches
from city_bounds import filter_raw_data
import auto_expand
from progress_tracker import load_queries
import scrape_runner
import pipeline
import nationwide_runner
import kanto_phase1
import utils as batch_utils


class TestLongitudeNormalization:
    def test_process_place_uses_longitude(self):
        place = {
            "title": "テスト施設",
            "category": "コンビニ",
            "address": "東京都渋谷区",
            "latitude": 35.68,
            "longitude": 139.69,
            "phone": "03-1234-5678",
            "review_rating": 4.0,
            "review_count": 50,
            "link": "https://maps.google.com/",
        }

        result = pd_module.process_place(place)

        assert result is not None
        assert result["lng"] == pytest.approx(139.69)
        assert result["prefecture"] == "東京都"

    def test_filter_raw_data_uses_longitude(self, tmp_path):
        input_path = tmp_path / "raw.jsonl"
        output_path = tmp_path / "filtered.jsonl"
        entry = {
            "title": "テスト",
            "address": "東京都渋谷区",
            "latitude": 35.68,
            "longitude": 139.69,
        }
        input_path.write_text(json.dumps(entry, ensure_ascii=False) + "\n", encoding="utf-8")

        total, kept = filter_raw_data(
            str(input_path),
            str(output_path),
            "渋谷区",
            bounds={"south": 35.0, "north": 36.0, "west": 139.0, "east": 140.0},
        )

        assert total == 1
        assert kept == 1
        assert output_path.read_text(encoding="utf-8").strip() == json.dumps(entry, ensure_ascii=False)

    def test_filter_raw_data_accepts_longtitude(self, tmp_path):
        input_path = tmp_path / "raw.jsonl"
        output_path = tmp_path / "filtered.jsonl"
        entry = {
            "title": "テスト",
            "address": "東京都渋谷区",
            "latitude": 35.68,
            "longtitude": 139.69,
        }
        input_path.write_text(json.dumps(entry, ensure_ascii=False) + "\n", encoding="utf-8")

        total, kept = filter_raw_data(
            str(input_path),
            str(output_path),
            "渋谷区",
            bounds={"south": 35.0, "north": 36.0, "west": 139.0, "east": 140.0},
        )

        assert total == 1
        assert kept == 1

    def test_filter_raw_data_uses_bounds_when_city_is_empty(self, tmp_path):
        input_path = tmp_path / "raw.jsonl"
        output_path = tmp_path / "filtered.jsonl"
        inside = {
            "title": "A",
            "address": "東京都渋谷区",
            "latitude": 35.68,
            "longitude": 139.69,
        }
        outside = {
            "title": "B",
            "address": "大阪府大阪市",
            "latitude": 34.69,
            "longitude": 135.50,
        }
        input_path.write_text(
            json.dumps(inside, ensure_ascii=False) + "\n" + json.dumps(outside, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        total, kept = filter_raw_data(
            str(input_path),
            str(output_path),
            "",
            bounds={"south": 35.0, "north": 36.0, "west": 139.0, "east": 140.0},
        )

        assert total == 2
        assert kept == 1
        assert output_path.read_text(encoding="utf-8").strip() == json.dumps(inside, ensure_ascii=False)


class TestQueryLoading:
    def test_load_queries_strips_indented_comments(self, tmp_path):
        query_file = tmp_path / "queries.txt"
        query_file.write_text("  # comment\nquery1\n    # comment2\n\nquery2\n", encoding="utf-8")

        assert load_queries(str(query_file)) == ["query1", "query2"]


class TestScrapeRunnerFiltering:
    def test_prepare_input_data_refuses_unfiltered_fallback(self, monkeypatch):
        monkeypatch.setattr(scrape_runner, "merge_part_files", lambda *args, **kwargs: None)
        monkeypatch.setattr(scrape_runner, "count_lines", lambda *args, **kwargs: 3)
        monkeypatch.setattr(
            scrape_runner,
            "apply_city_filter",
            lambda city, pref, raw_output: ("filtered.json", 3, 0),
        )

        with pytest.raises(RuntimeError, match="No entries matched city filter"):
            scrape_runner._prepare_input_data("高崎市", "群馬県")


class TestExpansionStatusFile:
    def test_update_expansion_status_merges_runs(self, tmp_path, monkeypatch):
        monkeypatch.setattr(batch_utils, "EXPANSION_STATUS_PATH", str(tmp_path / "status.json"))
        monkeypatch.setattr(batch_utils, "EXPANSION_STATUS_LOCK_PATH", str(tmp_path / "status.lock"))

        batch_utils.update_expansion_status(
            "run-a",
            {
                "prefecture": "東京都",
                "city": "千代田区",
                "status": "running",
                "progress": {"completed_queries": 1, "total_queries": 10, "success_count": 1, "failed_count": 0},
            },
        )
        batch_utils.update_expansion_status(
            "run-b",
            {
                "prefecture": "埼玉県",
                "city": "さいたま市",
                "status": "running",
                "progress": {"completed_queries": 2, "total_queries": 12, "success_count": 2, "failed_count": 0},
            },
        )

        data = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
        assert {run["run_id"] for run in data["runs"]} == {"run-a", "run-b"}
        assert any(run["city"] == "千代田区" for run in data["runs"])


class TestNationwideRunner:
    def test_run_prefecture_processes_all_batches(self, tmp_path, monkeypatch):
        base_dir = tmp_path / "batch"
        pref_dir = base_dir / "queries.d" / "東京都"
        pref_dir.mkdir(parents=True)
        (pref_dir / "batch_001.txt").write_text("q1\n", encoding="utf-8")
        (pref_dir / "batch_002.txt").write_text("q2\n", encoding="utf-8")

        monkeypatch.setattr(nationwide_runner, "SCRIPT_DIR", str(base_dir))

        calls = []

        class Result:
            returncode = 0

        def fake_run(cmd, env=None, check=None, cwd=None):
            calls.append((cmd, env, cwd))
            return Result()

        monkeypatch.setattr(nationwide_runner.subprocess, "run", fake_run)

        nationwide_runner.run_prefecture("東京都")

        assert [env["QUERIES"] for _, env, _ in calls] == [
            str(pref_dir / "batch_001.txt"),
            str(pref_dir / "batch_002.txt"),
        ]
        assert all(env["PROGRESS_FILE"].endswith(stem) for (_, env, _), stem in zip(calls, ["batch_001", "batch_002"]))
        assert all(env["SYNC_EVERY_SUCCESS"] == "10" for _, env, _ in calls)


class TestKantoPhase1:
    def test_run_scrape_sets_incremental_sync(self, tmp_path, monkeypatch):
        base_dir = tmp_path / "batch"
        base_dir.mkdir()
        queries = base_dir / "queries.txt"
        queries.write_text("q1\n", encoding="utf-8")

        monkeypatch.setattr(kanto_phase1, "SCRIPT_DIR", str(base_dir))

        captured = {}

        class Result:
            returncode = 0

        def fake_run(cmd, env=None, cwd=None, timeout=None):
            captured.update(env or {})
            return Result()

        monkeypatch.setattr(kanto_phase1.subprocess, "run", fake_run)

        kanto_phase1.run_scrape("東京都", "千代田区", "queries.txt")

        assert captured["SYNC_EVERY_SUCCESS"] == "10"


class TestCliParser:
    def test_parse_args_defaults(self, monkeypatch):
        import cli_parser
        monkeypatch.setattr(cli_parser.sys, "argv", ["scrape_runner.py"])
        result = cli_parser.parse_args()
        assert result["city"] == ""
        assert result["prefecture"] == ""
        assert result["dry_run"] is False
        assert result["max_queries"] is None
        assert result["progress_file"] is None

    def test_parse_args_city_and_prefecture(self, monkeypatch):
        import cli_parser
        monkeypatch.setattr(cli_parser.sys, "argv", ["scrape_runner.py", "--city", "渋谷区", "--prefecture", "東京都"])
        result = cli_parser.parse_args()
        assert result["city"] == "渋谷区"
        assert result["prefecture"] == "東京都"

    def test_parse_args_dry_run(self, monkeypatch):
        import cli_parser
        monkeypatch.setattr(cli_parser.sys, "argv", ["scrape_runner.py", "--dry-run"])
        result = cli_parser.parse_args()
        assert result["dry_run"] is True

    def test_parse_args_max_queries(self, monkeypatch):
        import cli_parser
        monkeypatch.setattr(cli_parser.sys, "argv", ["scrape_runner.py", "--max-queries", "10"])
        result = cli_parser.parse_args()
        assert result["max_queries"] == 10

    def test_parse_args_progress_file(self, monkeypatch):
        import cli_parser
        monkeypatch.setattr(cli_parser.sys, "argv", ["scrape_runner.py", "--progress-file", "progress.log"])
        result = cli_parser.parse_args()
        assert result["progress_file"] == "progress.log"

    def test_parse_args_invalid_max_queries_returns_none(self, monkeypatch):
        import cli_parser
        monkeypatch.setattr(cli_parser.sys, "argv", ["scrape_runner.py", "--max-queries", "not_a_number"])
        result = cli_parser.parse_args()
        assert result["max_queries"] is None

    def test_detect_city_from_queries_reads_header(self, tmp_path):
        import cli_parser
        query_file = tmp_path / "queries.txt"
        query_file.write_text("# city: 千代田区\n# prefecture: 東京都\nq1\nq2\n", encoding="utf-8")
        city, pref = cli_parser.detect_city_from_queries(str(query_file))
        assert city == "千代田区"
        assert pref == "東京都"

    def test_detect_city_from_queries_falls_back_to_most_common(self, tmp_path):
        import cli_parser
        query_file = tmp_path / "queries.txt"
        query_file.write_text("q1 in 渋谷区\nq2 in 渋谷区\nq3 in 新宿区\n", encoding="utf-8")
        city, pref = cli_parser.detect_city_from_queries(str(query_file))
        assert city == "渋谷区"
        assert pref == ""

    def test_detect_city_from_queries_handles_missing_file(self, tmp_path):
        import cli_parser
        city, pref = cli_parser.detect_city_from_queries(str(tmp_path / "nonexistent.txt"))
        assert city == ""
        assert pref == ""


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
        eq._ACTIVE_TARGET_CITY = "渋谷区"
        eq._ACTIVE_TARGET_PREF = "東京都"
        path = tmp_path / "batch_target.txt"
        path.write_text("# city: 渋谷区\n# prefecture: 東京都\nq1\n", encoding="utf-8")
        bucket = eq._classify_query_file(path)
        assert bucket == "city"
        eq._ACTIVE_TARGET_CITY = ""
        eq._ACTIVE_TARGET_PREF = ""

    def test_classify_query_file_identifies_pref(self, tmp_path):
        import expansion_query as eq
        eq._ACTIVE_TARGET_CITY = "渋谷区"
        eq._ACTIVE_TARGET_PREF = "東京都"
        path = tmp_path / "batch_pref.txt"
        path.write_text("# prefecture: 東京都\nq1\nq2\n", encoding="utf-8")
        bucket = eq._classify_query_file(path)
        assert bucket == "pref"
        eq._ACTIVE_TARGET_CITY = ""
        eq._ACTIVE_TARGET_PREF = ""

    def test_merge_query_files_combines_city_and_pref(self, tmp_path):
        import expansion_query as eq
        eq._ACTIVE_TARGET_CITY = "渋谷区"
        eq._ACTIVE_TARGET_PREF = "東京都"
        eq._ACTIVE_CITY_BUDGET = 2
        eq._ACTIVE_PREF_BUDGET = 2

        city_file = tmp_path / "city.txt"
        city_file.write_text("# city: 渋谷区\ncity_q1\ncity_q2\ncity_q3\n", encoding="utf-8")
        pref_file = tmp_path / "pref.txt"
        pref_file.write_text("# prefecture: 東京都\npref_q1\npref_q2\n", encoding="utf-8")

        result = eq.merge_query_files([str(city_file), str(pref_file)])
        assert result
        content = Path(result).read_text(encoding="utf-8")
        assert "city_q1" in content
        assert "city_q2" in content
        assert "city_q3" not in content  # budget exceeded
        assert "pref_q1" in content
        assert "pref_q2" in content
        Path(result).unlink()
        eq._ACTIVE_TARGET_CITY = ""
        eq._ACTIVE_TARGET_PREF = ""
        eq._ACTIVE_CITY_BUDGET = 0
        eq._ACTIVE_PREF_BUDGET = 0

    def test_merge_query_files_deduplicates(self, tmp_path):
        import expansion_query as eq
        eq._ACTIVE_TARGET_CITY = "渋谷区"
        eq._ACTIVE_TARGET_PREF = "東京都"
        eq._ACTIVE_CITY_BUDGET = 10
        eq._ACTIVE_PREF_BUDGET = 10

        city_file = tmp_path / "city.txt"
        city_file.write_text("# city: 渋谷区\ndup_q1\ndup_q2\n", encoding="utf-8")
        pref_file = tmp_path / "pref.txt"
        pref_file.write_text("# prefecture: 東京都\ndup_q1\ndup_q2\n", encoding="utf-8")

        result = eq.merge_query_files([str(city_file), str(pref_file)])
        content = Path(result).read_text(encoding="utf-8")
        assert content.count("dup_q1") == 1
        assert content.count("dup_q2") == 1
        Path(result).unlink()
        eq._ACTIVE_TARGET_CITY = ""
        eq._ACTIVE_TARGET_PREF = ""
        eq._ACTIVE_CITY_BUDGET = 0
        eq._ACTIVE_PREF_BUDGET = 0

    def test_merge_query_files_returns_empty_for_no_input(self):
        import expansion_query as eq
        eq._ACTIVE_TARGET_CITY = "渋谷区"
        eq._ACTIVE_TARGET_PREF = "東京都"
        # Force no active budget so no queries are matched
        eq._ACTIVE_CITY_BUDGET = 0
        eq._ACTIVE_PREF_BUDGET = 0
        result = eq.merge_query_files([])
        assert result == ""
        eq._ACTIVE_TARGET_CITY = ""
        eq._ACTIVE_TARGET_PREF = ""
        eq._ACTIVE_CITY_BUDGET = 0
        eq._ACTIVE_PREF_BUDGET = 0


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

        with pytest.raises(RuntimeError):
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
