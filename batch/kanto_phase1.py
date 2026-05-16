"""
kanto_phase1.py
Phase 1 automated scraper for 7 prefecture capitals.
Runs batch files sequentially with resume capability.
"""
import subprocess
import sys
import os
import time
from pathlib import Path
from utils import logger
from expansion_query import find_batch_files

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 対象: 7県庁所在地
TARGETS = [
    ("埼玉県", "さいたま市"),
    ("東京都", "千代田区"),
    ("千葉県", "千葉市"),
    ("神奈川県", "横浜市"),
    ("茨城県", "水戸市"),
    ("栃木県", "宇都宮市"),
    ("群馬県", "前橋市"),
]


def _resolve_query_path(pref: str) -> Path:
    """都道府県の最初のバッチファイルパスを解決する。見つからなければ queries.d/{pref}/batch_001.txt をデフォルトとする。"""
    files = find_batch_files(pref)
    if files:
        return Path(files[0])
    return Path(SCRIPT_DIR) / "queries.d" / pref / "batch_001.txt"

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


def run_scrape(pref: str, city: str, queries_path: Path, dry_run: bool = False) -> bool:
    """1都市をスクレイプ"""
    queries_abs = str(queries_path)
    progress_file = os.path.join(SCRIPT_DIR, f".progress_{pref}_phase1")

    # 進捗ファイルが既に100%完了しているかチェック
    if os.path.exists(progress_file):
        with open(progress_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if lines:
            last = int(lines[-1].strip())
            with open(queries_abs, "r", encoding="utf-8") as qf:
                total_queries = sum(1 for line in qf if line.strip() and not line.startswith("#"))
            if last >= total_queries:
                logger.info(f"  [SKIP] {pref} already completed (progress: {last}/{total_queries})")
                return True

    logger.info(f"  [{pref}] City: {city}")
    logger.info(f"  [{pref}] Queries: {queries_path}")
    logger.info(f"  [{pref}] Progress file: {progress_file}")

    env = os.environ.copy()
    env["QUERIES"] = queries_abs
    env["PROGRESS_FILE"] = progress_file
    env["SYNC_EVERY_SUCCESS"] = os.environ.get("SYNC_EVERY_SUCCESS", "10")

    cmd = [
        sys.executable,
        os.path.join(SCRIPT_DIR, "scrape_runner.py"),
        "--city", city,
        "--prefecture", pref,
    ]
    if dry_run:
        cmd.append("--dry-run")

    logger.info(f"  [{pref}] Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            env=env,
            cwd=SCRIPT_DIR,
            timeout=3600,  # 1 hour max per prefecture
        )
    except subprocess.TimeoutExpired:
        logger.error(f"  [{pref}] [TIMEOUT] Exceeded 1 hour")
        return False
    except FileNotFoundError:
        logger.error(f"  [{pref}] [ERROR] Docker executable not found. Is Docker Desktop running?")
        return False
    except OSError as e:
        logger.error(f"  [{pref}] [ERROR] {type(e).__name__}: {e}")
        return False

    if result.returncode != 0:
        logger.error(f"  [{pref}] FAILED with exit code {result.returncode}")
        logger.info(f"  [{pref}] Resume with: python scrape_runner.py --city {city} --prefecture {pref} --progress-file {progress_file}")
        return False

    logger.info(f"  [{pref}] Completed successfully")
    return True


def main():
    logger.info("=" * 60)
    logger.info("  Kanto Phase 1 Scraper")
    logger.info("  Target: 7 prefecture capitals")
    logger.info("=" * 60)
    logger.info("")

    # 既存進捗読み込み
    done_prefs = load_phase_progress()
    if done_prefs:
        logger.info(f"Resuming: {len(done_prefs)}/7 prefectures already done.")
        for pref in sorted(done_prefs):
            logger.info(f"  - {pref}")
        logger.info("")

    # 実行
    for pref, city in TARGETS:
        if pref in done_prefs:
            logger.info(f"[{pref}/{city}] Already done, skipping.")
            continue

        queries_path = _resolve_query_path(pref)
        logger.info(f"\n{'=' * 60}")
        logger.info(f"  Processing: {pref} {city}")
        logger.info(f"  Queries: {queries_path}")
        logger.info(f"{'=' * 60}")

        success = run_scrape(pref, city, queries_path, dry_run=DRY_RUN)
        if success:
            done_prefs.add(pref)
            save_phase_progress(done_prefs)
            logger.info(f"  [OK] Phase progress saved ({len(done_prefs)}/7 completed)")
        else:
            logger.info(f"\n  [SKIP] Failed on {pref} {city} - moving to next prefecture")
            logger.info("  Re-run this script later to retry failed prefectures.")
            logger.info(f"  Current phase progress: {sorted(done_prefs)}")
            # 失敗しても進捗ファイルは保存済み（完了分のみ）
            # スキップして次へ（進捗ファイルはそのまま保持）

        # 最終都市でなければスリープ（dry-run時はスキップ）
        if pref != TARGETS[-1][0]:
            if DRY_RUN:
                logger.info("  [DRY-RUN] Skipping sleep between prefectures")
            else:
                logger.info(f"\n  Sleeping {SLEEP_BETWEEN}s before next prefecture...")
                time.sleep(SLEEP_BETWEEN)

    logger.info("\n" + "=" * 60)
    logger.info("  [DONE] All Phase 1 prefectures completed!")
    logger.info(f"  Total: {len(done_prefs)}/7")
    logger.info("=" * 60)

    # クリーンアップ
    if os.path.exists(PHASE_PROGRESS):
        os.remove(PHASE_PROGRESS)
        logger.info("Cleaned up phase progress file.")

    logger.info("\nNext steps:")
    logger.info("  1. Verify data: python -c \"import gzip, json; d=json.load(gzip.open('data/toilets.json.gz', 'rt', encoding='utf-8')); print('Total:', d['metadata']['total'])\"")
    logger.info("  2. Run app: streamlit run app.py")


if __name__ == "__main__":
    main()
