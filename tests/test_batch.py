"""
tests/test_batch.py
batch モジュールの smoke tests
"""
import os


class TestGenerateQueries:
    def test_import(self):
        from batch import generate_queries
        assert hasattr(generate_queries, "BATCH_SIZE")


class TestCityBounds:
    def test_import(self):
        from batch import city_bounds
        assert hasattr(city_bounds, "get_city_bounds")


class TestScrapeRunner:
    def test_import(self):
        from batch import scrape_runner
        assert hasattr(scrape_runner, "run_batch")


class TestPrefectureCitiesJson:
    def test_exists(self):
        path = "batch/prefecture_cities.json"
        assert os.path.exists(path)

    def test_json_valid(self):
        import json
        path = "batch/prefecture_cities.json"
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict)
        assert "東京都" in data
        assert "渋谷区" in data["東京都"]


class TestKantoPhase1:
    def test_import(self):
        from batch import kanto_phase1
        assert hasattr(kanto_phase1, "TARGETS")
