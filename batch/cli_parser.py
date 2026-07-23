"""
batch/cli_parser.py
scrape_runner.py の CLI 引数解析とクエリファイルからの都市・県自動検出
"""

import argparse
import logging
import os
import re
import sys

logger = logging.getLogger(__name__)

FILTER_CITY = os.environ.get("CITY", "")
FILTER_PREF = os.environ.get("PREFECTURE", "")


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def parse_args() -> dict:
    """Parse known arguments while preserving the pipeline's tolerant CLI behavior."""
    parser = argparse.ArgumentParser(description="Run resumable toilet-map scraping")
    parser.add_argument("--city", default=FILTER_CITY)
    parser.add_argument("--prefecture", default=FILTER_PREF)
    parser.add_argument("--progress-file")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-queries")
    namespace, unknown = parser.parse_known_args(sys.argv[1:])
    if unknown:
        logger.warning("Ignoring unknown CLI arguments: %s", " ".join(unknown))

    raw_max_queries = namespace.max_queries
    if raw_max_queries is not None:
        try:
            namespace.max_queries = _positive_int(raw_max_queries)
        except argparse.ArgumentTypeError:
            logger.warning("Invalid --max-queries value: %s", raw_max_queries)
            namespace.max_queries = None
    return vars(namespace)


def detect_city_from_queries(queries_path: str) -> tuple[str, str]:
    city = ""
    pref = ""
    city_counts: dict[str, int] = {}

    try:
        with open(queries_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("# city:"):
                    city = line.split(":", 1)[1].strip()
                elif line.startswith("# prefecture:"):
                    pref = line.split(":", 1)[1].strip()
                elif line and not line.startswith("#"):
                    seen_in_line: set[str] = set()
                    match = re.search(r"\bin\s+(\S+[市区町村])", line)
                    if match:
                        candidate = match.group(1)
                        city_counts[candidate] = city_counts.get(candidate, 0) + 1
                        seen_in_line.add(candidate)
                    for match in re.finditer(r"(\S*[市区町村])", line):
                        candidate = match.group(1)
                        if len(candidate) >= 2 and candidate not in seen_in_line:
                            seen_in_line.add(candidate)
                            city_counts[candidate] = city_counts.get(candidate, 0) + 1
    except OSError as exc:
        logger.warning("Failed to read query file %s: %s", queries_path, exc)
        return city, pref

    if not city and city_counts:
        city = max(city_counts, key=lambda key: city_counts[key])

    return city, pref
