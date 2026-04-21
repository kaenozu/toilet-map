"""
tests/test_batch.py
batch module smoke tests
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


class TestGenerateQueries:
    """generate_queries.py smoke test"""

    def test_import_module(self):
        from batch import generate_queries
        assert hasattr(generate_queries, "BATCH_SIZE")
        assert generate_queries.BATCH_SIZE == 12

    def test_query_templates(self):
        from batch import generate_queries
        assert len(generate_queries.QUERY_TEMPLATES) > 0


class TestCityBounds:
    """city_bounds.py smoke test"""

    def test_import_module(self):
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
    """scrape_runner.py smoke test"""

    def test_import_module(self):
        from batch import scrape_runner
        assert hasattr(scrape_runner, "SCRAPER_DEPTH")
        assert hasattr(scrape_runner, "MAX_RETRIES")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])