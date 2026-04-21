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
import json
import shutil
import tempfile
import re

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
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "2"))
RETRY_SLEEP = int(os.environ.get("RETRY_SLEEP", "300"))

FILTER_CITY = os.environ.get("CITY", "")
FILTER_PREF = os.environ.get("PREFECTURE", "")

# Docker設定
DOCKER_IMAGE = "gosom/google-maps-scraper"
SCRAPER_DEPTH = "1"
SCRAPER_LANG = "ja"
EXIT_ON_INACTIVITY = "5m"


# ============================================================
# I/Oユーティリティ
# ============================================================
def load_queries(path: str = QUERIES_FILE) -> list[str]:
    """クエリファイルを読み込む（空行・コメント行を除外）"""
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


def save_progress(done: set[int], path: str = PROGRESS_FILE):
    """進捗をファイルに書き出す"""
    with open(path, "w") as f:
        for idx in sorted(done):
            f.write(f"{idx}\n")


def merge_part_files(raw_dir: str, output_path: str, total: int):
    """partファイルを1つの出力ファイルにマージ"""
    with open(output_path, "w", encoding="utf-8") as outf:
        for i in range(1, total + 1):
            part = os.path.join(raw_dir, f"part_{i:03d}.json")
            if os.path.exists(part):
                with open(part, "r", encoding="utf-8") as pf:
                    outf.write(pf.read())


def count_lines(path: str) -> int:
    """ファイルの行数をカウント"""
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for _ in f)


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
    # 一時クエリファイル（レースコンディション回避）
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.txt') as tmp:
        tmp_query = tmp.name
        tmp.write(query)

    try:
        query_docker = to_docker_path(tmp_query)
        output_docker = to_docker_path(output_path)

        # 結果ファイル初期化
        with open(output_path, "w") as f:
            pass

        cmd = [
            "docker", "run", "--rm",
            "-v", f"{query_docker}:/query.txt",
            "-v", f"{output_docker}:/results.json",
            DOCKER_IMAGE,
            "-depth", SCRAPER_DEPTH,
            "-input", "/query.txt",
            "-results", "/results.json",
            "-json", "--extra-reviews",
            "-lang", SCRAPER_LANG,
            "-exit-on-inactivity", EXIT_ON_INACTIVITY,
        ]

        print(f"  Running: {query}")
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    finally:
        if os.path.exists(tmp_query):
            try:
                os.remove(tmp_query)
            except PermissionError:
                pass

    if result is None or result.returncode != 0:
        print(f"  Docker exit code: {result.returncode if result else 'N/A'}")
        for label, data in [("stdout", result.stdout), ("stderr", result.stderr)]:
            if data:
                print(f"  {label}: {data[:500]}")
        return False

    if not os.path.exists(output_path):
        return False

    with open(output_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    if not lines:
        print("  No results")
        return False

    print(f"  OK ({len(lines)} results)")
    return True


def parse_args() -> dict:
    """CLI引数をパース"""
    args = {
        "city": FILTER_CITY,
        "prefecture": FILTER_PREF,
        "progress_file": None,
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
        else:
            i += 1
    return args


def detect_city_from_queries(queries_path: str) -> tuple[str, str]:
    """クエリファイルから都市名と都道府県を自動検出
    1) '# city: XXX' ヘッダーコメント
    2) 'in XXX市' クエリパターン
    3) クエリ内に頻出する市区町村名
    Returns: (city, prefecture)
    """
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


# ============================================================
# メインループ
# ============================================================
def run_batch():
    """バッチスクレイプ全体を実行"""
    args = parse_args()
    queries = load_queries()
    total = len(queries)

    # 進捗ファイルの決定
    progress_file = args.get("progress_file") or PROGRESS_FILE

    # 都市名決定: CLI > 環境変数 > クエリから自動検出
    city = args["city"]
    pref = args["prefecture"]
    if not city:
        city, pref = detect_city_from_queries(QUERIES_FILE)

    if city:
        print(f"City filter: {pref}{city}")
    else:
        print("City filter: OFF (no --city specified, could not auto-detect)")

    print(f"Queries: {total}")
    print(f"Sleep between: {SLEEP_BETWEEN}s")
    print(f"Est. time: ~{total * (180 + SLEEP_BETWEEN) // 60} min")
    print()

    os.makedirs(RAW_DIR, exist_ok=True)

    # 進捗読み込み
    done = load_progress(progress_file)
    if done:
        print(f"Resuming: {len(done)}/{total} already done.")
        # 欠落partファイル確認
        for idx in list(done):
            if not os.path.exists(os.path.join(RAW_DIR, f"part_{idx:03d}.json")):
                print(f"  Missing part file for query #{idx} - will re-run")
                done.discard(idx)
        print()
    else:
        # 新規開始: バックアップ＆クリーン
        if os.path.exists(RAW_OUTPUT):
            shutil.copy2(RAW_OUTPUT, RAW_OUTPUT + ".bak")
            print("Previous data backed up.")
        if os.path.exists(RAW_DIR):
            shutil.rmtree(RAW_DIR)
        os.makedirs(RAW_DIR, exist_ok=True)
        print()

    success = skipped = failed = 0

    for i, query in enumerate(queries, 1):
        part_file = os.path.join(RAW_DIR, f"part_{i:03d}.json")
        if i in done and os.path.exists(part_file):
            print(f"[{i}/{total}] (done) {query}")
            skipped += 1
            continue

        print(f"\n{'=' * 50}")
        print(f"[{i}/{total}] {query}")
        print(f"{'=' * 50}")

        ok = False
        for retry in range(MAX_RETRIES + 1):
            if retry > 0:
                print(f"  Retry #{retry} ... waiting {RETRY_SLEEP}s")
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
            print(f"  !! FAILED: {query}")
            print(f"  Rerun to resume from here.")

        if ok and i < total:
            print(f"  Sleeping {SLEEP_BETWEEN}s ...")
            time.sleep(SLEEP_BETWEEN)

    # ── マージ ──
    print(f"\n{'=' * 50}")
    print(f"  Scraping done  OK: {success} / Skip: {skipped} / Fail: {failed}")
    print(f"{'=' * 50}\n")

    print("Merging results...")
    merge_part_files(RAW_DIR, RAW_OUTPUT, total)
    total_lines = count_lines(RAW_OUTPUT)
    print(f"Total raw data: {total_lines} entries")

    # ── 市フィルタ ──
    data_for_processing = RAW_OUTPUT
    if city:
        from city_bounds import get_city_bounds, filter_raw_data

        bounds = None
        if pref:
            print(f"Fetching bounding box for {pref}{city}...")
            bounds = get_city_bounds(city, pref)
        if not bounds:
            print(f"Fetching bounding box for {city}...")
            bounds = get_city_bounds(city)

        filtered_path = RAW_OUTPUT.replace(".json", "_filtered.json")
        total_raw, kept = filter_raw_data(RAW_OUTPUT, filtered_path, city, bounds)

        if kept == 0:
            print(f"\n  WARNING: No entries matched city filter '{city}'")
            print(f"  ({total_raw} raw entries were checked)")
            print(f"  Falling back to unfiltered data\n")
            data_for_processing = RAW_OUTPUT
        else:
            pct = kept / total_raw * 100 if total_raw > 0 else 0
            print(f"  City filter: {kept}/{total_raw} entries kept ({pct:.1f}%)")
            data_for_processing = filtered_path

    # ── データ処理 ──
    print("Processing data (incremental merge)...")
    proc = subprocess.run(
        [sys.executable, os.path.join(SCRIPT_DIR, "process_data.py"),
         data_for_processing, PROCESSED, "--incremental"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    print(proc.stdout)
    if proc.stderr:
        print(proc.stderr)
    if proc.returncode != 0:
        print("[ERROR] Data processing failed")
        sys.exit(1)

    # 成功時クリーンアップ
    if failed == 0:
        for path in [progress_file, RAW_DIR]:
            if os.path.exists(path):
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                print(f"Cleaned up: {path}")

    print(f"\nOutput: {os.path.abspath(PROCESSED)}")


if __name__ == "__main__":
    run_batch()
