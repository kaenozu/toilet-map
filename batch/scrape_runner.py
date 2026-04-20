"""
scrape_runner.py
バッチスクレイプの実行エンジン（Windows batから呼び出される）
"""
import subprocess
import sys
import os
import time
import json
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
QUERIES_FILE = os.path.join(SCRIPT_DIR, os.environ.get("QUERIES", "queries.txt"))
RAW_DIR = os.path.join(SCRIPT_DIR, "raw_parts")
RAW_OUTPUT = os.path.join(SCRIPT_DIR, "raw_data.json")
PROCESSED = os.path.join(SCRIPT_DIR, "..", "data", "toilets.json")
PROGRESS_FILE = os.path.join(SCRIPT_DIR, ".progress")

SLEEP_BETWEEN = 120    # クエリ間スリープ（秒）
MAX_RETRIES = 2        # リトライ回数
RETRY_SLEEP = 300      # リトライ前スリープ（秒）


def load_queries():
    queries = []
    with open(QUERIES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            queries.append(line)
    return queries


def load_progress():
    done = set()
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    done.add(int(line))
    return done


def save_progress(done):
    with open(PROGRESS_FILE, "w") as f:
        for idx in sorted(done):
            f.write(f"{idx}\n")


def win_to_docker_path(win_path):
    """WindowsパスをDockerが認識できる形式に変換。
    C:\\foo\\bar -> /c/foo/bar (Git Bash/Docker for Windows)
    """
    # os.path -> 正規化
    p = os.path.normpath(win_path)
    # ドライブレター処理
    if len(p) >= 2 and p[1] == ':':
        drive = p[0].lower()
        rest = p[2:].replace('\\', '/')
        return f'/{drive}{rest}'
    return p.replace('\\', '/')


def scrape_query(query, output_path):
    """1クエリをスクレイプ。成功ならTrue。"""
    # 一時クエリファイル
    tmp_query = os.path.join(SCRIPT_DIR, "tmp_query.txt")
    with open(tmp_query, "w", encoding="utf-8") as f:
        f.write(query)

    # パス変換
    query_docker = win_to_docker_path(tmp_query)
    output_docker = win_to_docker_path(output_path)

    # 結果ファイル初期化
    with open(output_path, "w") as f:
        pass

    cmd = [
        "docker", "run", "--rm",
        "-v", f"{query_docker}:/query.txt",
        "-v", f"{output_docker}:/results.json",
        "gosom/google-maps-scraper",
        "-depth", "1",
        "-input", "/query.txt",
        "-results", "/results.json",
        "-json",
        "--extra-reviews",
        "-lang", "ja",
        "-exit-on-inactivity", "5m",
    ]

    print(f"  Running: {query}")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")

    # クリーンアップ
    if os.path.exists(tmp_query):
        try:
            os.remove(tmp_query)
        except PermissionError:
            pass

    if result.returncode != 0:
        print(f"  Docker exit code: {result.returncode}")
        if result.stderr:
            print(f"  stderr: {result.stderr[:200]}")
        return False

    # 結果ファイル確認
    if not os.path.exists(output_path):
        return False

    with open(output_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    if len(lines) == 0:
        print("  No results")
        return False

    print(f"  OK ({len(lines)} results)")
    return True


def main():
    queries = load_queries()
    total = len(queries)

    print(f"Queries: {total}")
    print(f"Sleep between: {SLEEP_BETWEEN}s")
    print(f"Est. time: ~{total * (180 + SLEEP_BETWEEN) // 60} min")
    print()

    # ディレクトリ準備
    os.makedirs(RAW_DIR, exist_ok=True)

    # 進捗読み込み
    done = load_progress()
    if done:
        print(f"Resuming: {len(done)}/{total} already done.")
        print()

        # 既存のpartファイル確認
        missing = []
        for idx in done:
            part = os.path.join(RAW_DIR, f"part_{idx:03d}.json")
            if not os.path.exists(part):
                missing.append(idx)
        if missing:
            print(f"  Missing part files for: {missing}")
            print(f"  Those queries will be re-run.")
            for idx in missing:
                done.discard(idx)
    else:
        # 新規開始
        if os.path.exists(RAW_OUTPUT):
            bak = RAW_OUTPUT + ".bak"
            shutil.copy2(RAW_OUTPUT, bak)
            print("Previous data backed up.")
        # raw_parts クリア
        if os.path.exists(RAW_DIR):
            shutil.rmtree(RAW_DIR)
        os.makedirs(RAW_DIR, exist_ok=True)
        print()

    success = 0
    skipped = 0
    failed = 0

    for i, query in enumerate(queries, 1):
        # 完了済みチェック（partファイル存在確認）
        part_file = os.path.join(RAW_DIR, f"part_{i:03d}.json")
        if i in done and os.path.exists(part_file):
            print(f"[{i}/{total}] (done) {query}")
            skipped += 1
            continue

        print(f"\n{'='*50}")
        print(f"[{i}/{total}] {query}")
        print(f"{'='*50}")

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
            save_progress(done)
        else:
            failed += 1
            print(f"  !! FAILED: {query}")
            print(f"  Rerun to resume from here.")

        # 最後以外はスリープ
        if ok and i < total:
            print(f"  Sleeping {SLEEP_BETWEEN}s ...")
            time.sleep(SLEEP_BETWEEN)

    # ── マージ ──
    print()
    print(f"{'='*50}")
    print(f"  Scraping done  OK: {success} / Skip: {skipped} / Fail: {failed}")
    print(f"{'='*50}")
    print()
    print("Merging results...")

    with open(RAW_OUTPUT, "w", encoding="utf-8") as outf:
        for i in range(1, total + 1):
            part = os.path.join(RAW_DIR, f"part_{i:03d}.json")
            if os.path.exists(part):
                with open(part, "r", encoding="utf-8") as pf:
                    outf.write(pf.read())

    # 行数カウント
    with open(RAW_OUTPUT, "r", encoding="utf-8") as f:
        total_lines = sum(1 for _ in f)
    print(f"Total raw data: {total_lines} entries")

    # ── データ処理（差分更新）──
    print("Processing data (incremental merge)...")
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPT_DIR, "process_data.py"),
         RAW_OUTPUT, PROCESSED, "--incremental"],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    if result.returncode != 0:
        print("[ERROR] Data processing failed")
        sys.exit(1)

    # 成功ならクリーンアップ
    if failed == 0:
        if os.path.exists(PROGRESS_FILE):
            os.remove(PROGRESS_FILE)
            print("Progress file cleared.")
        if os.path.exists(RAW_DIR):
            shutil.rmtree(RAW_DIR)
            print("Temp files cleaned up.")

    print()
    print(f"Output: {os.path.abspath(PROCESSED)}")


if __name__ == "__main__":
    main()
