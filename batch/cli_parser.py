"""
batch/cli_parser.py
scrape_runner.py の CLI 引数解析とクエリファイルからの都市・県自動検出
"""
import sys
import os
import re
from typing import Optional
from utils import logger

FILTER_CITY = os.environ.get("CITY", "")
FILTER_PREF = os.environ.get("PREFECTURE", "")


def parse_args() -> dict:
    args = {
        "city": FILTER_CITY,
        "prefecture": FILTER_PREF,
        "progress_file": None,
        "dry_run": False,
        "max_queries": None,
    }
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--city" and i + 1 < len(sys.argv):
            args["city"] = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--prefecture" and i + 1 < len(sys.argv):
            args["prefecture"] = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--progress-file" and i + 1 < len(sys.argv):
            args["progress_file"] = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--dry-run":
            args["dry_run"] = True
            i += 1
        elif sys.argv[i] == "--max-queries" and i + 1 < len(sys.argv):
            try:
                args["max_queries"] = int(sys.argv[i + 1])
            except ValueError:
                logger.warning(f"Invalid --max-queries value: {sys.argv[i+1]}")
            i += 2
        else:
            i += 1
    return args


def detect_city_from_queries(queries_path: str) -> tuple[str, str]:
    city = ""
    pref = ""
    city_counts = {}

    try:
        with open(queries_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("# city:"):
                    city = line.split(":", 1)[1].strip()
                elif line.startswith("# prefecture:"):
                    pref = line.split(":", 1)[1].strip()
                elif line and not line.startswith("#"):
                    m = re.search(r'\bin\s+(\S+[市区町村])', line)
                    if m:
                        c = m.group(1)
                        city_counts[c] = city_counts.get(c, 0) + 1
                    for m in re.finditer(r'(\S*[市区町村])', line):
                        c = m.group(1)
                        if len(c) >= 2:
                            city_counts[c] = city_counts.get(c, 0) + 1
    except OSError as exc:
        logger.warning(f"Failed to read query file: {queries_path} ({exc})")

    if not city and city_counts:
        city = max(city_counts, key=city_counts.get)

    return city, pref
