"""
kanto_phase1.py
Phase 1 automated scraper for 7 prefecture capitals.
Runs batch files sequentially with resume capability.
"""
import subprocess
import sys
import os
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 対象: 7県庁所在地
TARGETS = [
    ("埼玉県", "さいたま市", "queries.d/埼玉県/batch_001.txt"),
    ("東京都", "千代田区", "queries.d/東京都/batch_001.txt"),
    ("千葉県", "千葉市",   "queries.d/千葉県/batch_001.txt"),
    ("神奈川県", "横浜市", "queries.d/神奈川県/batch_001.txt"),
    ("茨城県", "水戸市",   "queries.d/茨城県/batch_001.txt"),
    ("栃木県", "宇都宮市", "queries.d/栃木県/batch_001.txt"),
    ("群馬県", "前橋市",   "queries.d/群馬県/batch_001.txt"),
]

# 設定
SLEEP_BETWEEN = int(os.environ.get("SLEEP_BETWEEN", "120"))
DRY_RUN = '--dry-run' in sys.argv

# 進捗トラッキングファイル
PHASE_PROGRESS = os.path.join(SCRIPT_DIR, ".kanto_phase1_progress")


def load_phase_progress() -> set[str]:
    """完了済みの都道府県リストを読み込む"""
    done = set()
    if os.path.exists(PHASE_PROGRESS):
        with open(PHASE_PROGRESS, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    done.add(line)
    return done


def save_phase_progress(done: set[str]):
    """進捗を保存"""
    with open(PHASE_PROGRESS, "w", encoding="utf-8") as f:
        for pref in sorted(done):
            f.write(f"{pref}\n")


def run_scrape(pref: str, city: str, queries_rel: str, dry_run: bool = False) -> bool:
    """1都市をスクレイプ"""
    queries_abs = os.path.join(SCRIPT_DIR, queries_rel)
    progress_file = os.path.join(SCRIPT_DIR, f".progress_{pref}_phase1")

    # 進捗ファイルが既に100%完了しているかチェック
    if os.path.exists(progress_file):
        with open(progress_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if lines:
            last = int(lines[-1].strip())
            with open(queries_abs, "r", encoding="utf-8") as qf:
                total_queries = sum(1 for l in qf if l.strip() and not l.startswith("#"))
            if last >= total_queries:
                print(f"  [SKIP] {pref} already completed (progress: {last}/{total_queries})")
                return True

    print(f"  [{pref}] City: {city}")
    print(f"  [{pref}] Queries: {queries_rel}")
    print(f"  [{pref}] Progress file: {progress_file}")

    # scrape_runner.py を呼び出
    env = os.environ.copy()
    env["QUERIES"] = queries_abs
    env["PROGRESS_FILE"] = progress_file

    cmd = [
        sys.executable,
        os.path.join(SCRIPT_DIR, "scrape_runner.py"),
        "--city", city,
        "--prefecture", pref,
    ]
    if dry_run:
        cmd.append("--dry-run")

    print(f"  [{pref}] Running: {' '.join(cmd)}")
    try:
        # 出力はコンソールに直接流す（キャプチャしない）
        result = subprocess.run(
            cmd,
            env=env,
            cwd=SCRIPT_DIR,
            timeout=3600,  # 1 hour max per prefecture
        )
    except subprocess.TimeoutExpired:
        print(f"  [{pref}] [TIMEOUT] Exceeded 1 hour")
        return False
    except FileNotFoundError:
        print(f"  [{pref}] [ERROR] Docker executable not found. Is Docker Desktop running?")
        return False
    except Exception as e:
        print(f"  [{pref}] [ERROR] {type(e).__name__}: {e}")
        return False

    if result.returncode != 0:
        print(f"  [{pref}] FAILED with exit code {result.returncode}")
        print(f"  [{pref}] Resume with: python scrape_runner.py --city {city} --prefecture {pref} --progress-file {progress_file}")
        return False

    print(f"  [{pref}] Completed successfully")
    return True


def main():
    print("=" * 60)
    print("  Kanto Phase 1 Scraper")
    print("  Target: 7 prefecture capitals")
    print("=" * 60)
    print()

    # 既存進捗読み込み
    done_prefs = load_phase_progress()
    if done_prefs:
        print(f"Resuming: {len(done_prefs)}/7 prefectures already done.")
        for pref in sorted(done_prefs):
            print(f"  - {pref}")
        print()

    # 実行
    for pref, city, queries_rel in TARGETS:
        if pref in done_prefs:
            print(f"[{pref}/{city}] Already done, skipping.")
            continue

        print(f"\n{'=' * 60}")
        print(f"  Processing: {pref} {city}")
        print(f"{'=' * 60}")

        success = run_scrape(pref, city, queries_rel, dry_run=DRY_RUN)
        if success:
            done_prefs.add(pref)
            save_phase_progress(done_prefs)
            print(f"  [OK] Phase progress saved ({len(done_prefs)}/7 completed)")
        else:
            print(f"\n  [FAIL] Failed on {pref} {city}")
            print(f"  Re-run this script to resume from the failed prefecture.")
            print(f"  Current phase progress: {sorted(done_prefs)}")
            sys.exit(1)

        # 最終都市でなければスリープ（dry-run時はスキップ）
        if pref != TARGETS[-1][0]:
            if DRY_RUN:
                print("  [DRY-RUN] Skipping sleep between prefectures")
            else:
                print(f"\n  Sleeping {SLEEP_BETWEEN}s before next prefecture...")
                time.sleep(SLEEP_BETWEEN)

    print("\n" + "=" * 60)
    print("  [DONE] All Phase 1 prefectures completed!")
    print(f"  Total: {len(done_prefs)}/7")
    print("=" * 60)

    # クリーンアップ
    if os.path.exists(PHASE_PROGRESS):
        os.remove(PHASE_PROGRESS)
        print("Cleaned up phase progress file.")

    print("\nNext steps:")
    print("  1. Verify data: python -c \"import json; d=json.load(open('data/toilets.json')); print('Total:', d['metadata']['total'])\"")
    print("  2. Run app: streamlit run app.py")


if __name__ == "__main__":
    main()
