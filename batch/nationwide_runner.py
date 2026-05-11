"""
batch/nationwide_runner.py
全国47都道府県のクエリバッチを順にスクレイピングする
"""
import os
import sys
import subprocess
import importlib
from pathlib import Path

from utils import file_lock

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
QUERY_LOCK_PATH = os.path.join(SCRIPT_DIR, ".queries.lock")


def _load_prefectures() -> list[str]:
    try:
        return importlib.import_module("scoring_config").PREFECTURES
    except ModuleNotFoundError:
        return importlib.import_module("batch.scoring_config").PREFECTURES


def _load_generate_queries_main():
    try:
        return importlib.import_module("generate_queries").main
    except ModuleNotFoundError:
        return importlib.import_module("batch.generate_queries").main


PREFECTURES = _load_prefectures()
generate_queries_main = _load_generate_queries_main()


def collect_query_files(prefecture: str) -> list[Path]:
    pref_dir = Path(SCRIPT_DIR) / "queries.d" / prefecture
    return sorted(pref_dir.glob("batch_*.txt"))


def run_prefecture(pref: str):
    query_files = collect_query_files(pref)
    if not query_files:
        return

    for query_file in query_files:
        env = os.environ.copy()
        env["QUERIES"] = str(query_file)
        env["PROGRESS_FILE"] = os.path.join(SCRIPT_DIR, f".progress_{pref}_{query_file.stem}")
        env["SYNC_EVERY_SUCCESS"] = os.environ.get("SYNC_EVERY_SUCCESS", "10")

        cmd = [sys.executable, os.path.join(SCRIPT_DIR, "scrape_runner.py"), "--prefecture", pref]
        try:
            subprocess.run(cmd, env=env, check=True, cwd=SCRIPT_DIR)
        except subprocess.CalledProcessError as e:
            from utils import logger
            logger.error(f"[{pref}] {query_file.name} FAILED with exit code {e.returncode}")
            raise
        except FileNotFoundError:
            from utils import logger
            logger.error("[ERROR] Python executable not found")
            raise


def main():
    with file_lock(QUERY_LOCK_PATH):
        generate_queries_main()
    for pref in PREFECTURES:
        run_prefecture(pref)


if __name__ == "__main__":
    main()
