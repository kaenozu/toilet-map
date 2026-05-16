"""
tests/test_exceptions.py
Tests for custom exception classes in batch/exceptions.py

関連: batch/exceptions.py, batch/pipeline.py, batch/scrape_filter.py
"""

import pytest
from exceptions import ConfigError, DataError, ScrapeError


class TestScrapeError:
    def test_can_be_raised_and_caught(self):
        with pytest.raises(ScrapeError):
            raise ScrapeError("test")

    def test_inherits_from_exception(self):
        assert issubclass(ScrapeError, Exception)

    def test_message_preserved(self):
        try:
            raise ScrapeError("scraping failed")
        except ScrapeError as e:
            assert str(e) == "scraping failed"


class TestDataError:
    def test_can_be_raised_and_caught(self):
        with pytest.raises(DataError):
            raise DataError("test")

    def test_inherits_from_exception(self):
        assert issubclass(DataError, Exception)

    def test_message_preserved(self):
        try:
            raise DataError("data processing failed")
        except DataError as e:
            assert str(e) == "data processing failed"


class TestConfigError:
    def test_can_be_raised_and_caught(self):
        with pytest.raises(ConfigError):
            raise ConfigError("test")

    def test_inherits_from_exception(self):
        assert issubclass(ConfigError, Exception)

    def test_message_preserved(self):
        try:
            raise ConfigError("invalid config")
        except ConfigError as e:
            assert str(e) == "invalid config"
