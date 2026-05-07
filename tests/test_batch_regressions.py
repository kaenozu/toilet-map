"""
tests/test_batch_regressions.py
batch 系の回帰テスト
"""
import json
import sqlite3

import pytest

import db_utils
import process_data as pd_module
from generate_queries import write_batches
from city_bounds import filter_raw_data
from normalize_coordinates import normalize_file
from scrape_runner import load_queries
import scrape_runner
import nationwide_runner
import merge_to_db
import to_sqlite
import verify_data


class TestLongitudeNormalization:
    def test_process_place_uses_longitude(self):
        place = {
            "title": "テスト施設",
            "category": "カフェ",
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

    def test_normalize_file_rewrites_longtitude(self, tmp_path):
        raw_path = tmp_path / "raw.jsonl"
        raw_path.write_text(
            json.dumps({"title": "A", "latitude": 35.0, "longtitude": 139.0}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        replaced = normalize_file(raw_path)

        assert replaced == 1
        data = json.loads(raw_path.read_text(encoding="utf-8").strip())
        assert "longtitude" not in data
        assert data["longitude"] == 139.0


class TestQueryLoading:
    def test_load_queries_strips_indented_comments(self, tmp_path):
        query_file = tmp_path / "queries.txt"
        query_file.write_text("  # comment\nquery1\n    # comment2\n\nquery2\n", encoding="utf-8")

        assert load_queries(str(query_file)) == ["query1", "query2"]


class TestSqliteReset:
    def test_full_conversion_can_run_twice(self, tmp_path, monkeypatch):
        db_path = tmp_path / "toilets.db"
        json_path = tmp_path / "toilets.json"
        payload = {
            "metadata": {"area_name": "テスト"},
            "toilets": [
                {
                    "title": "A",
                    "category": "公衆トイレ",
                    "address": "東京都渋谷区",
                    "lat": 35.68,
                    "lng": 139.69,
                    "rating": 4.0,
                    "review_count": 10,
                    "is_public_toilet": True,
                    "toilet_score": 80,
                    "confidence": 0.8,
                    "toilet_review_count": 2,
                    "prefecture": "東京都",
                    "sample_reviews": [],
                }
            ],
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        monkeypatch.setattr(to_sqlite, "DB_PATH", str(db_path))

        to_sqlite.json_to_sqlite(str(json_path), incremental=False)
        to_sqlite.json_to_sqlite(str(json_path), incremental=False)

        conn = sqlite3.connect(db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
            assert count == 1
        finally:
            conn.close()

    def test_full_conversion_collapses_duplicate_rows(self, tmp_path, monkeypatch):
        db_path = tmp_path / "toilets.db"
        json_path = tmp_path / "toilets.json"
        row = {
            "title": "A",
            "category": "公衆トイレ",
            "address": "東京都渋谷区",
            "lat": 35.68,
            "lng": 139.69,
            "rating": 4.0,
            "review_count": 10,
            "is_public_toilet": True,
            "toilet_score": 80,
            "confidence": 0.8,
            "toilet_review_count": 2,
            "prefecture": "東京都",
            "sample_reviews": [],
        }
        payload = {"metadata": {"area_name": "テスト"}, "toilets": [row, {**row, "category": "更新"}]}
        json_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        monkeypatch.setattr(to_sqlite, "DB_PATH", str(db_path))

        to_sqlite.json_to_sqlite(str(json_path), incremental=False)

        conn = sqlite3.connect(db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
            category = conn.execute("SELECT category FROM toilets WHERE title = 'A'").fetchone()[0]
            assert count == 1
            assert category == "更新"
        finally:
            conn.close()

    def test_incremental_conversion_updates_existing_row(self, tmp_path, monkeypatch):
        db_path = tmp_path / "toilets.db"
        json_path = tmp_path / "toilets.json"
        original = {
            "title": "A",
            "category": "公衆トイレ",
            "address": "東京都渋谷区",
            "lat": 35.68,
            "lng": 139.69,
            "rating": 4.0,
            "review_count": 10,
            "is_public_toilet": True,
            "toilet_score": 80,
            "confidence": 0.8,
            "toilet_review_count": 2,
            "prefecture": "東京都",
            "sample_reviews": [],
        }
        updated = {**original, "category": "更新", "toilet_score": 90, "confidence": 1.0}

        monkeypatch.setattr(to_sqlite, "DB_PATH", str(db_path))

        json_path.write_text(
            json.dumps({"metadata": {"area_name": "テスト"}, "toilets": [original]}, ensure_ascii=False),
            encoding="utf-8",
        )
        to_sqlite.json_to_sqlite(str(json_path), incremental=False)

        json_path.write_text(
            json.dumps({"metadata": {"area_name": "テスト2"}, "toilets": [updated]}, ensure_ascii=False),
            encoding="utf-8",
        )
        to_sqlite.json_to_sqlite(str(json_path), incremental=True)

        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                "SELECT COUNT(*), category, toilet_score FROM toilets WHERE title = 'A' AND lat = ? AND lng = ?",
                (35.68, 139.69),
            ).fetchone()
            meta = conn.execute("SELECT value FROM metadata WHERE key = 'area_name'").fetchone()[0]
            assert row[0] == 1
            assert row[1] == "更新"
            assert row[2] == 90
            assert meta == "テスト2"
        finally:
            conn.close()


class TestMergeToDb:
    def test_merge_dedupes_existing_rows(self, tmp_path):
        db_path = tmp_path / "toilets.db"
        json_path = tmp_path / "input.json"
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(db_utils.TOILET_TABLE_SCHEMA)
            conn.execute(db_utils.METADATA_TABLE_SCHEMA)
            row = db_utils.toilet_db_values(
                {
                    "title": "A",
                    "category": "公衆トイレ",
                    "address": "東京都渋谷区",
                    "lat": 35.68,
                    "lng": 139.69,
                    "rating": 4.0,
                    "review_count": 10,
                    "is_public_toilet": True,
                    "toilet_score": 80,
                    "confidence": 0.8,
                    "toilet_review_count": 2,
                    "prefecture": "東京都",
                    "sample_reviews": [],
                }
            )
            insert_sql = (
                "INSERT INTO toilets (title, category, address, lat, lng, rating, review_count, "
                "is_public_toilet, toilet_score, confidence, toilet_review_count, prefecture, sample_reviews_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            )
            conn.execute(insert_sql, row)
            conn.execute(insert_sql, row)
            conn.commit()
        finally:
            conn.close()

        json_path.write_text(json.dumps({"metadata": {}, "toilets": []}, ensure_ascii=False), encoding="utf-8")

        merge_to_db.merge(str(json_path), db_path=str(db_path))

        conn = sqlite3.connect(db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
            unique_indexes = conn.execute("PRAGMA index_list('toilets')").fetchall()
            assert count == 1
            assert any(row[2] for row in unique_indexes)
        finally:
            conn.close()


class TestIncrementalLoad:
    def test_load_existing_finds_gz_output(self, tmp_path):
        base = tmp_path / "toilets.json"
        payload = {
            "metadata": {"area_name": "テスト"},
            "toilets": [{"title": "A", "lat": 35.0, "lng": 139.0, "confidence": 1, "is_public_toilet": False}],
        }
        with open(str(base) + ".gz", "wb") as f:
            import gzip
            with gzip.GzipFile(fileobj=f, mode="wb") as gz:
                gz.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

        loaded = pd_module.load_existing(str(base))

        assert loaded["metadata"]["area_name"] == "テスト"
        assert loaded["toilets"][0]["title"] == "A"


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


class TestPostProcessPipeline:
    def test_run_postprocess_pipeline_converts_sqlite_incrementally(self, monkeypatch):
        calls = []

        class Result:
            returncode = 0

        def fake_run(cmd):
            calls.append(cmd)
            return Result()

        monkeypatch.setattr(scrape_runner.subprocess, "run", fake_run)

        scrape_runner.run_postprocess_pipeline("input.json", "output.json.gz")

        assert len(calls) == 2
        assert calls[0][-1] == "--incremental"
        assert calls[1][1].endswith("to_sqlite.py")
        assert calls[1][-1] == "--incremental"

    def test_run_postprocess_pipeline_raises_when_sqlite_conversion_fails(self, monkeypatch):
        class Result:
            def __init__(self, returncode):
                self.returncode = returncode

        calls = iter([Result(0), Result(1)])
        monkeypatch.setattr(scrape_runner.subprocess, "run", lambda cmd: next(calls))

        with pytest.raises(RuntimeError):
            scrape_runner.run_postprocess_pipeline("input.json", "output.json.gz")


class TestVerificationGate:
    def test_collect_quality_metrics_counts_missing_and_duplicates(self):
        toilets = [
            {"title": "A", "address": "東京都千代田区", "prefecture": "東京都", "toilet_score": 80, "link": "https://maps.google.com/a"},
            {"title": "A", "address": "東京都千代田区", "prefecture": "東京都", "toilet_score": 75, "link": "https://maps.google.com/b"},
            {"title": "B", "address": "", "prefecture": "", "toilet_score": None, "link": "https://maps.google.com/c"},
        ]

        metrics = verify_data.collect_quality_metrics(toilets)

        assert metrics["total"] == 3
        assert metrics["missing_score"] == 1
        assert metrics["missing_prefecture"] == 1
        assert metrics["missing_address"] == 1
        assert len(metrics["duplicates"]) == 1
        assert metrics["prefecture_counts"]["東京都"] == 2

    def test_evaluate_quality_gate_fails_on_large_missing_rate(self):
        metrics = {
            "total": 10,
            "missing_score": 3,
            "missing_prefecture": 0,
            "missing_address": 0,
            "duplicates": [],
            "prefecture_counts": {"東京都": 10},
        }

        errors, warnings = verify_data.evaluate_quality_gate(metrics, expected_prefectures=["東京都"])

        assert errors
        assert any("Missing score rate" in message for message in errors)
        assert warnings == []

    def test_evaluate_quality_gate_warns_on_missing_prefecture_coverage(self):
        metrics = {
            "total": 5,
            "missing_score": 0,
            "missing_prefecture": 0,
            "missing_address": 0,
            "duplicates": [],
            "prefecture_counts": {"東京都": 5},
        }

        errors, warnings = verify_data.evaluate_quality_gate(metrics, expected_prefectures=["東京都", "神奈川県"])

        assert errors == []
        assert any("No records found for 神奈川県" in message for message in warnings)
