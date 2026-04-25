"""
tests/test_batch.py
batch モジュールの smoke tests
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


class TestGenerateQueries:
    def test_import(self):
        from batch import generate_queries
        assert hasattr(generate_queries, "BATCH_SIZE")
        assert generate_queries.BATCH_SIZE == 12
    def test_templates(self):
        from batch import generate_queries
        assert len(generate_queries.QUERY_TEMPLATES) > 0
    def test_load_prefectures(self):
        from batch import generate_queries
        data = generate_queries.load_prefectures()
        assert len(data) == 47
        assert "東京都" in data


class TestScoringConfig:
    def test_import(self):
        from batch import scoring_config
        assert scoring_config.SCORE_CLAMP_MIN == -5.0
        assert scoring_config.SCORE_CLAMP_MAX == 5.0
        assert len(scoring_config.POSITIVE_KEYWORDS) > 0
        assert len(scoring_config.NEGATIVE_KEYWORDS) > 0
        assert len(scoring_config.NEGATION_WORDS) > 0
    def test_prefectures(self):
        from batch import scoring_config
        assert "東京都" in scoring_config.PREFECTURES
        assert "沖縄県" in scoring_config.PREFECTURES
        assert len(scoring_config.PREFECTURES) == 47


class TestCityBounds:
    def test_import(self):
        from batch import city_bounds
        assert hasattr(city_bounds, "get_city_bounds")
        assert hasattr(city_bounds, "is_in_bounds")
    def test_is_in_bounds(self):
        from batch import city_bounds
        bounds = {"south": 35.0, "north": 36.0, "west": 135.0, "east": 136.0}
        assert city_bounds.is_in_bounds(35.5, 135.5, bounds) is True
        assert city_bounds.is_in_bounds(34.9, 135.5, bounds) is False
        assert city_bounds.is_in_bounds(35.5, 134.9, bounds) is False


class TestScrapeRunner:
    def test_import(self):
        from batch import scrape_runner
        assert hasattr(scrape_runner, "SCRAPER_DEPTH")
        assert hasattr(scrape_runner, "MAX_RETRIES")


class TestPrefectureCitiesJson:
    def test_json_valid(self):
        import json
        path = os.path.join(os.path.dirname(__file__), "..", "batch", "prefecture_cities.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) == 47
        assert "東京都" in data
        assert "北海道" in data
        assert "沖縄県" in data
        for cities in data.values():
            assert isinstance(cities, list)
            assert len(cities) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])