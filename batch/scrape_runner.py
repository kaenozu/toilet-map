"""
scrape_runner.py
バッチスクレイプの実行エンジン（Windows batから呼び出される）

使い方:
  python scrape_runner.py                          # queries.txtを使用
  python scrape_runner.py --city 羽生市            # 市名でフィルタ
  python scrape_runner.py --city 羽生市 --prefecture 埼玉県

関連: city_bounds.py, process_data.py, generate_queries.py
"""
import subprocess
import sys
import os
import time
import shutil
import tempfile
import re
from pathlib import Path
from typing import Optional
from utils import logger, count_lines

# ============================================================
# 設定
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
QUERIES_FILE = os.path.join(SCRIPT_DIR, os.environ.get("QUERIES", "queries.txt"))
RAW_DIR = os.path.join(SCRIPT_DIR, "raw_parts")
RAW_OUTPUT = os.path.join(SCRIPT_DIR, "raw_data.json")
PROCESSED = os.path.join(SCRIPT_DIR, "..", "data", "toilets.json")
PROGRESS_FILE = os.path.join(SCRIPT_DIR, os.environ.get("PROGRESS_FILE", ".progress"))

SLEEP_BETWEEN = int(os.environ.get("SLEEP_BETWEEN", "120"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "2"))  # 0-based: 実際は MAX_RETRIES+1 回実行
RETRY_SLEEP = int(os.environ.get("RETRY_SLEEP", "300"))

FILTER_CITY = os.environ.get("CITY", "")
FILTER_PREF = os.environ.get("PREFECTURE", "")

# Docker設定 (環境変数で上書き可能)
DOCKER_IMAGE = os.environ.get("SCRAPER_IMAGE", "gosom/google-maps-scraper")
SCRAPER_DEPTH = os.environ.get("SCRAPER_DEPTH", "1")
SCRAPER_LANG = os.environ.get("SCRAPER_LANG", "ja")
EXIT_ON_INACTIVITY = os.environ.get("EXIT_ON_INACTIVITY", "5m")


# ============================================================
# I/Oユーティリティ
# ============================================================
def load_queries(path: str = QUERIES_FILE) -> list[str]:
    """クエリファイルを読み込む（空行・コメント行を除外）"""
    if not os.path.exists(path):
        return []
    queries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                queries.append(line)
    return queries


def load_progress(path: str = PROGRESS_FILE) -> set[int]:
    """進捗ファイルから完了済みインデックスを読み込む"""
    if not os.path.exists(path):
        return set()
    with open(path, "r") as f:
        return {int(line.strip()) for line in f if line.strip()}


def save_progress(done: set[int], path: str = PROGRESS_FILE) -> None:
    """進捗をファイルに書き出す"""
    with open(path, "w") as f:
        for idx in sorted(done):
            f.write(f"{idx}\n")


def merge_part_files(raw_dir: str, output_path: str, total: int) -> None:
    """partファイルを1つの出力ファイルにマージ"""
    with open(output_path, "w", encoding="utf-8") as outf:
        for i in range(1, total + 1):
            part = os.path.join(raw_dir, f"part_{i:03d}.json")
            if os.path.exists(part):
                with open(part, "r", encoding="utf-8") as pf:
                    outf.write(pf.read())


# ============================================================
# パス変換
# ============================================================
def to_docker_path(win_path: str) -> str:
    """WindowsパスをDocker認識形式に変換 (C:\\foo → /c/foo)"""
    p = os.path.normpath(win_path)
    if len(p) >= 2 and p[1] == ':':
        drive = p[0].lower()
        rest = p[2:].replace('\\', '/')
        return f'/{drive}{rest}'
    return p.replace('\\', '/')


# ============================================================
# スクレイプ実行
# ============================================================
def scrape_query(query: str, output_path: str) -> bool:
    """1クエリをスクレイプ。成功ならTrue"""
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
            result = subprocess.run(cmd, cwd=SCRIPT_DIR, timeout=600)
        except subprocess.TimeoutExpired:
            logger.error("Query exceeded 10 minutes")
            return False
        except FileNotFoundError:
            logger.error("Docker executable not found. Is Docker Desktop running?")
            return False
        except Exception as e:
            logger.error(f"{type(e).__name__}: {e}")
            return False

        if result.returncode != 0:
            logger.error(f"FAILED (exit code {result.returncode})")
            return False
    finally:
        if os.path.exists(tmp_query):
            try:
                os.remove(tmp_query)
            except PermissionError:
                pass

    if not os.path.exists(output_path):
        logger.error("Output file not created")
        return False

    with open(output_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    if not lines:
        logger.warning("No results found for this query")
        return False

    logger.info(f"OK ({len(lines)} results)")
    return True


def parse_args() -> dict:
    """CLI引数をパース"""
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
    """クエリファイルから都市名と都道府県を自動検出"""
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
    except OSError:
        pass

    if not city and city_counts:
        city = max(city_counts, key=city_counts.get)

    return city, pref


def fetch_city_bounds(city: str, pref: str) -> Optional[dict]:
    """市のバウンディングボックスを取得（キャッシュ利用）"""
    from city_bounds import get_city_bounds
    if pref:
        logger.info(f"Fetching bounding box for {pref}{city}...")
        bounds = get_city_bounds(city, pref)
        if bounds:
            return bounds
    logger.info(f"Fetching bounding box for {city}...")
    return get_city_bounds(city)


def apply_city_filter(city: str, pref: str, raw_output: str) -> tuple[str, int, int]:
    """市フィルタを適用。戻り値: (処理用ファイルパス, 総生データ数, フィルタ後数)"""
    from city_bounds import filter_raw_data

    bounds = fetch_city_bounds(city, pref)
    filtered_path = str(Path(raw_output).with_name(Path(raw_output).stem + "_filtered.json"))
    total_raw, kept = filter_raw_data(raw_output, filtered_path, city, bounds)
    return filtered_path, total_raw, kept


def run_batch():
    """バッチスクレイプ全体を実行"""
    args = parse_args()
    queries = load_queries()
    total = len(queries)

    progress_file = args.get("progress_file") or PROGRESS_FILE

    city = args["city"]
    pref = args["prefecture"]
    if not city:
        city, pref = detect_city_from_queries(QUERIES_FILE)

    if city:
        logger.info(f"City filter: {pref}{city}")
    else:
        logger.info("City filter: OFF (no --city specified, could not auto-detect)")

    logger.info(f"Queries: {total}")
    logger.info(f"Sleep between: {SLEEP_BETWEEN}s")
    logger.info(f"Est. time: ~{total * (180 + SLEEP_BETWEEN) // 60} min")

    os.makedirs(RAW_DIR, exist_ok=True)

    # 進捗読み込み
    done = load_progress(progress_file)
    if done:
        logger.info(f"Resuming: {len(done)}/{total} already done.")
        for idx in list(done):
            if not os.path.exists(os.path.join(RAW_DIR, f"part_{idx:03d}.json")):
                logger.warning(f"Missing part file for query #{idx} - will re-run")
                done.discard(idx)
        logger.info("")
    else:
        if os.path.exists(RAW_OUTPUT):
            shutil.copy2(RAW_OUTPUT, RAW_OUTPUT + ".bak")
            logger.info("Previous data backed up.")
        if os.path.exists(RAW_DIR):
            shutil.rmtree(RAW_DIR)
        os.makedirs(RAW_DIR, exist_ok=True)
        logger.info("")

    success = skipped = failed = 0

    max_q = args.get("max_queries")
    if max_q is not None:
        queries = queries[:max_q]
        total = len(queries)
        logger.info(f"[MAX-QUERIES] Limited to first {total} queries")

    if done:
        done = {idx for idx in done if 1 <= idx <= total}
        logger.info(f"Resuming: {len(done)}/{total} already done (after filter).")

    if args.get("dry_run"):
        logger.info("[DRY-RUN] Dockerスクレイプをスキップします。")
        for i in range(1, total + 1):
            if i not in done:
                done.add(i)
        save_progress(done, progress_file)
        logger.info(f"[DRY-RUN] 進捗ファイルに {len(done)}/{total} 件を記録しました。")
        return 0

    for i, query in enumerate(queries, 1):
        part_file = os.path.join(RAW_DIR, f"part_{i:03d}.json")
        if i in done and os.path.exists(part_file):
            logger.info(f"[{i}/{total}] (done) {query}")
            skipped += 1
            continue

        logger.info(f"\n{'=' * 50}")
        logger.info(f"[{i}/{total}] {query}")
        logger.info(f"{'=' * 50}")

        ok = False
        for retry in range(MAX_RETRIES + 1):
            if retry > 0:
                logger.info(f"  Retry #{retry} ... waiting {RETRY_SLEEP}s")
                time.sleep(RETRY_SLEEP)
            if scrape_query(query, part_file):
                ok = True
                break

        if ok:
            success += 1
            done.add(i)
            save_progress(done, progress_file)
        else:
            failed += 1
            logger.error(f"  !! FAILED: {query}")
            logger.info("  Rerun to resume from here.")

        if ok and i < total:
            logger.info(f"  Sleeping {SLEEP_BETWEEN}s ...")
            time.sleep(SLEEP_BETWEEN)

    logger.info(f"\n{'=' * 50}")
    logger.info(f"  Scraping done  OK: {success} / Skip: {skipped} / Fail: {failed}")
    logger.info(f"{'=' * 50}\n")

    logger.info("Merging results...")
    merge_part_files(RAW_DIR, RAW_OUTPUT, total)
    total_lines = count_lines(RAW_OUTPUT)
    logger.info(f"Total raw data: {total_lines} entries")

    # 市フィルタ
    data_for_processing = RAW_OUTPUT
    if city:
        filtered_path, total_raw, kept = apply_city_filter(city, pref, RAW_OUTPUT)
        if kept == 0:
            logger.warning(f"\n  WARNING: No entries matched city filter '{city}'")
            logger.info(f"  ({total_raw} raw entries were checked)")
            logger.info("  Falling back to unfiltered data\n")
            data_for_processing = RAW_OUTPUT
        else:
            pct = kept / total_raw * 100 if total_raw > 0 else 0
            logger.info(f"  City filter: {kept}/{total_raw} entries kept ({pct:.1f}%)")
            data_for_processing = filtered_path

    # データ処理
    logger.info("Processing data (incremental merge)...")
    proc = subprocess.run(
        [sys.executable, os.path.join(SCRIPT_DIR, "process_data.py"),
         data_for_processing, PROCESSED, "--incremental"],
    )
    if proc.returncode != 0:
        logger.error("[ERROR] Data processing failed")
        sys.exit(1)

    # 成功時クリーンアップ
    if failed == 0:
        for path in [progress_file, RAW_DIR]:
            if os.path.exists(path):
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                logger.info(f"Cleaned up: {path}")

    logger.info(f"\nOutput: {os.path.abspath(PROCESSED)}")


if __name__ == "__main__":
    run_batch()
