"""
batch/logging_config.py
Centralized logging configuration with JSON output option.
Related: app.py, batch/process_data.py, batch/to_sqlite.py
"""
import json
import logging
import sys
from datetime import UTC, datetime


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


def configure_logging(json_output: bool = False) -> None:
    """Configure root logger. Set json_output=True for JSON format."""
    root = logging.getLogger()
    # Avoid duplicate handlers on Streamlit re-runs
    if root.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
    root.addHandler(handler)
    root.setLevel(logging.INFO)
