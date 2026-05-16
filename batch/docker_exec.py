"""
batch/docker_exec.py
Dockerを使ったスクレイプ実行のユーティリティ
to_docker_path と scrape_query を提供
"""
import os
import subprocess
import tempfile

from utils import logger

DOCKER_IMAGE = os.environ.get("SCRAPER_IMAGE", "gosom/google-maps-scraper")
SCRAPER_DEPTH = os.environ.get("SCRAPER_DEPTH", "2")
SCRAPER_LANG = os.environ.get("SCRAPER_LANG", "ja")
EXIT_ON_INACTIVITY = os.environ.get("EXIT_ON_INACTIVITY", "5m")


def to_docker_path(win_path: str) -> str:
    p = os.path.normpath(win_path)
    if len(p) >= 2 and p[1] == ':':
        drive = p[0].lower()
        rest = p[2:].replace('\\', '/')
        return f'/{drive}{rest}'
    return p.replace('\\', '/')


def scrape_query(query: str, output_path: str, cwd: str = ".") -> bool:
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.txt') as tmp:
        tmp_query = tmp.name
        tmp.write(query)

    try:
        query_docker = to_docker_path(tmp_query)
        output_dir = os.path.dirname(output_path)
        output_name = os.path.basename(output_path)
        output_dir_docker = to_docker_path(output_dir)

        cmd = [
            "docker", "run", "--rm",
            "-v", f"{query_docker}:/query.txt:ro",
            "-v", f"{output_dir_docker}:/output",
            DOCKER_IMAGE,
            "-depth", SCRAPER_DEPTH,
            "-input", "/query.txt",
            "-results", f"/output/{output_name}",
            "-json",
            "-lang", SCRAPER_LANG,
            "-exit-on-inactivity", EXIT_ON_INACTIVITY,
        ]

        logger.info(f"Running: {query}")
        try:
            result = subprocess.run(cmd, cwd=cwd, timeout=600)
        except subprocess.TimeoutExpired:
            logger.error("Query exceeded 10 minutes")
            return False
        except FileNotFoundError:
            logger.error("Docker executable not found. Is Docker Desktop running?")
            return False
        except OSError as e:
            logger.error(f"{type(e).__name__}: {e}")
            return False

        if result.returncode != 0:
            logger.error(f"FAILED (exit code {result.returncode})")
            return False
    finally:
        if os.path.exists(tmp_query):
            try:
                os.remove(tmp_query)
            except PermissionError as exc:
                logger.warning(f"Could not remove temporary query file {tmp_query}: {exc}")

    if not os.path.exists(output_path):
        logger.error("Output file not created")
        return False

    with open(output_path, encoding="utf-8") as f:
        lines = f.readlines()
    if not lines:
        logger.warning("No results found for this query")
        return False

    logger.info(f"OK ({len(lines)} results)")
    return True
