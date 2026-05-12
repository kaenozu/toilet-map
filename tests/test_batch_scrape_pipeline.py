"""
tests/test_batch_scrape_pipeline.py
スクレイピングパイプライン関連の回帰テスト（test_batch_regressions.py から分割）
"""
import json
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
