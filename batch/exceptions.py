"""
batch/exceptions.py
Custom exception classes for batch processing
"""


class ScrapeError(Exception):
    """Raised when scraping fails."""


class DataError(Exception):
    """Raised when data processing fails."""


class ConfigError(Exception):
    """Raised when configuration is invalid."""
