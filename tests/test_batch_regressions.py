"""
tests/test_batch_regressions.py
batch 系の回帰テスト
"""
import json
import sqlite3

import pytest

import process_data as pd_module
from generate_queries import write_batches
from city_bounds import filter_raw_data
from normalize_coordinates import normalize_file
from scrape_runner import load_queries
import to_sqlite


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
