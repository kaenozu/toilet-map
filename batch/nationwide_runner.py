"""
batch/nationwide_runner.py
全国47都道府県の主要都市を自動スクレイピングする
"""
import os
import sys
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(__file__))
from scoring_config import PREFECTURES


def run_prefecture(pref: str):
    query_file = os.path.join(SCRIPT_DIR, "queries.d", pref, "batch_001.txt")
    if not os.path.exists(query_file):
        return

    env = os.environ.copy()
    env["QUERIES"] = query_file
    env["PROGRESS_FILE"] = os.path.join(SCRIPT_DIR, f".progress_{pref}")

    cmd = [sys.executable, os.path.join(SCRIPT_DIR, "scrape_runner.py"), "--prefecture", pref]
    try:
        subprocess.run(cmd, env=env, check=True, cwd=SCRIPT_DIR)
    except subprocess.CalledProcessError as e:
        from utils import logger
        logger.error(f"[{pref}] FAILED with exit code {e.returncode}")
        raise
    except FileNotFoundError:
        from utils import logger
        logger.error("[ERROR] Python executable not found")
        raise


def main():
    for pref in PREFECTURES:
        run_prefecture(pref)


if __name__ == "__main__":
    main()
