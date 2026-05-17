"""
batch/logging_config.py
Centralized logging configuration with JSON output option and log rotation.
Related: app.py, batch/process_data.py, batch/to_sqlite.py
"""
import json
import logging
import sys
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    def format(self, record: logging.LogRecord) -> str:
        obj = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            obj["exception"] = str(record.exc_info[1])
        return json.dumps(obj, ensure_ascii=False)


def add_file_handler(logger: logging.Logger = None) -> None:
    """Add a RotatingFileHandler to the specified logger or root logger."""
    logger = logger or logging.getLogger()
    handler = RotatingFileHandler(
        LOG_DIR / "toilet-map.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    logger.addHandler(handler)


def configure_logging(json_output: bool = False) -> None:
    """Configure root logger. Set json_output=True for JSON format."""
    root = logging.getLogger()
    # Avoid duplicate handlers on Streamlit re-runs
    if root.handlers:
        return
    add_file_handler()
    handler = logging.StreamHandler(sys.stdout)
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
    root.addHandler(handler)
    root.setLevel(logging.INFO)
