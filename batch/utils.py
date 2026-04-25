"""
batch/utils.py
Common utility functions for batch processing.
"""
import json
import os
import logging
import gzip
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def load_jsonl(path: str) -> list[dict[str, Any]]:
    """Load JSONL file into a list of dictionaries."""
    if not os.path.exists(path):
        return []
    places = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    places.append(json.loads(line))
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to decode JSON line in {path}: {e}")
    return places

def save_json(path: str, data: dict[str, Any], indent: int = 2, compress: bool = False) -> None:
    """Save dictionary to JSON file (optionally compressed with gzip)."""
    target_path = path
    if compress:
        if not target_path.endswith(".gz"):
            target_path += ".gz"
        with gzip.open(target_path, "wt", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
    else:
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
    logger.info(f"Saved: {target_path}")

def count_lines(path: str) -> int:
    """Count non-empty lines in a file (excluding comments)."""
    if not os.path.exists(path):
        return 0
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip() and not line.startswith("#"))

def ensure_dir(path: str) -> None:
    """Ensure directory exists."""
    os.makedirs(path, exist_ok=True)
