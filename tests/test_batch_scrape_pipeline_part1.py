"""
tests/test_batch_scrape_pipeline.py
スクレイピングパイプライン関連の回帰テスト（test_batch_regressions.py から分割）
"""
import json
from pathlib import Path

import kanto_phase1
import nationwide_runner
import process_data as pd_module
import pytest
import utils as batch_utils
from city_bounds import filter_raw_data
from progress_tracker import load_queries


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
        import scrape_filter
        monkeypatch.setattr(scrape_filter, "merge_part_files", lambda *args, **kwargs: None)
        monkeypatch.setattr(scrape_filter, "count_lines", lambda *args, **kwargs: 3)
        monkeypatch.setattr(
            scrape_filter,
            "apply_city_filter",
            lambda city, pref, raw_output, raw_dir, queries_file: ("filtered.json", 3, 0),
        )

        with pytest.raises((RuntimeError, scrape_filter.DataError), match="No entries matched city filter"):
            scrape_filter.prepare_input_data("高崎市", "群馬県", "raw.json", "raw_dir", "queries.txt")



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
        assert all(env["PROGRESS_FILE"].endswith(stem) for (_, env, _), stem in zip(calls, ["batch_001", "batch_002"], strict=False))
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

        kanto_phase1.run_scrape("東京都", "千代田区", Path("queries.txt"))

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

    def test_parse_args_invalid_max_queries_warns(self, monkeypatch, caplog):
        import cli_parser
        monkeypatch.setattr(cli_parser.sys, "argv", ["scrape_runner.py", "--max-queries", "not_a_number"])
        cli_parser.parse_args()
        assert "Invalid --max-queries value: not_a_number" in caplog.text

    def test_parse_args_unknown_arg_skipped(self, monkeypatch):
        import cli_parser
        monkeypatch.setattr(cli_parser.sys, "argv", ["scrape_runner.py", "--unknown-flag"])
        result = cli_parser.parse_args()
        assert result["city"] == ""

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

    def test_detect_city_oserror_logs_warning(self, tmp_path, caplog):
        import cli_parser
        cli_parser.detect_city_from_queries(str(tmp_path / "nonexistent.txt"))
        assert "Failed to read query file" in caplog.text

    def test_detect_city_seen_in_line_dedup(self, tmp_path):
        import cli_parser
        query_file = tmp_path / "queries.txt"
        query_file.write_text("渋谷区 トイレ\n", encoding="utf-8")
        city, pref = cli_parser.detect_city_from_queries(str(query_file))
        assert city == "渋谷区"



