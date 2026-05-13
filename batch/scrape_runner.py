"""
scrape_runner.py
バッチスクレイプの実行エンジン（Windows batから呼び出される）

使い方:
  python scrape_runner.py                          # queries.txtを使用
  python scrape_runner.py --city 羽生市            # 市名でフィルタ
  python scrape_runner.py --city 羽生市 --prefecture 埼玉県

関連: city_bounds.py, process_data.py, generate_queries.py
"""
import sys
import os
import time
import shutil
from pathlib import Path
from typing import Optional

from utils import logger, count_lines
from docker_exec import scrape_query
from progress_tracker import (
    load_queries, load_progress, save_progress, publish_expansion_status, merge_part_files,
    PROGRESS_FILE as DEFAULT_PROGRESS_FILE,
)
from cli_parser import parse_args, detect_city_from_queries
from pipeline import run_postprocess_pipeline

# ============================================================
# 設定
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
QUERIES_FILE = os.path.join(SCRIPT_DIR, os.environ.get("QUERIES", "queries.txt"))
RAW_DIR = os.path.join(SCRIPT_DIR, os.environ.get("RAW_DIR", "raw_parts"))
RAW_OUTPUT = os.path.join(SCRIPT_DIR, os.environ.get("RAW_OUTPUT", "raw_data.json"))
PROCESSED = os.path.join(SCRIPT_DIR, "..", "data", "toilets.json.gz")

SLEEP_BETWEEN = int(os.environ.get("SLEEP_BETWEEN", "120"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "2"))
RETRY_SLEEP = int(os.environ.get("RETRY_SLEEP", "300"))
SYNC_EVERY_SUCCESS = int(os.environ.get("SYNC_EVERY_SUCCESS", "0"))


# ============================================================
# 市フィルタ・境界取得
# ============================================================
def fetch_city_bounds(city: str, pref: str) -> Optional[dict]:
    from city_bounds import get_city_bounds
    if pref and not city:
        return get_city_bounds(pref)
    if pref:
        bounds = get_city_bounds(city, pref)
        if bounds:
            return bounds
    return get_city_bounds(city)


def apply_city_filter(city: str, pref: str, raw_output: str) -> tuple[str, int, int]:
    from city_bounds import filter_raw_data
    bounds = fetch_city_bounds(city, pref)
    filtered_path = str(Path(raw_output).with_name(Path(raw_output).stem + "_filtered.json"))
    total_raw, kept = filter_raw_data(raw_output, filtered_path, city, bounds)
    return filtered_path, total_raw, kept


# ============================================================
# データ準備
# ============================================================
def _prepare_input_data(city: str, pref: str) -> str:
    logger.info("Merging results...")
    merge_part_files(RAW_DIR, RAW_OUTPUT, len(load_queries(QUERIES_FILE)))
    total_lines = count_lines(RAW_OUTPUT)
    logger.info(f"Total raw data: {total_lines} entries")

    if not city and not pref:
        return RAW_OUTPUT

    filtered_path, total_raw, kept = apply_city_filter(city, pref, RAW_OUTPUT)
    if kept == 0:
        filter_label = f"{pref}{city}" if pref else city
        logger.warning(f"\n  WARNING: No entries matched city filter '{filter_label}'")
        logger.info(f"  ({total_raw} raw entries were checked)")
        raise RuntimeError(f"No entries matched city filter '{filter_label}'")

    pct = kept / total_raw * 100 if total_raw > 0 else 0
    logger.info(f"  City filter: {kept}/{total_raw} entries kept ({pct:.1f}%)")
    return filtered_path


def _sync_canonical_data(city: str, pref: str) -> None:
    data_for_processing = _prepare_input_data(city, pref)
    run_postprocess_pipeline(data_for_processing, PROCESSED, SCRIPT_DIR)


def _maybe_sync_after_success(city: str, pref: str, success_count: int) -> None:
    if SYNC_EVERY_SUCCESS > 0 and success_count % SYNC_EVERY_SUCCESS == 0:
        logger.info(f"Syncing canonical data after {success_count} successful queries...")
        _sync_canonical_data(city, pref)


# ============================================================
# スクレイプループ
# ============================================================
def _execute_scraping_loop(
    queries: list[str],
    total: int,
    done: set[int],
    progress_file: str,
    args: dict,
    run_id: str,
    started_at: float,
) -> tuple[int, int, int, set[int]]:
    success = skipped = failed = 0
    city = args.get("city", "")
    pref = args.get("prefecture", "")

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
        publish_expansion_status(
            run_id,
            pref=args.get("prefecture", ""),
            city=args.get("city", ""),
            total=total,
            done=len(done),
            success=0,
            failed=0,
            started_at=started_at,
            status="running",
            message="dry-run",
        )
        logger.info(f"[DRY-RUN] 進捗ファイルに {len(done)}/{total} 件を記録しました。")
        return 0, 0, 0, done

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
            if scrape_query(query, part_file, cwd=SCRIPT_DIR):
                ok = True
                break

        if ok:
            success += 1
            done.add(i)
            save_progress(done, progress_file)
            _maybe_sync_after_success(city, pref, success)
        else:
            failed += 1
            logger.error(f"  !! FAILED: {query}")
            logger.info("  Rerun to resume from here.")

        publish_expansion_status(
            run_id,
            pref=pref,
            city=city,
            total=total,
            done=len(done),
            success=success,
            failed=failed,
            started_at=started_at,
            status="running",
            message=query,
        )

        if ok and i < total:
            logger.info(f"  Sleeping {SLEEP_BETWEEN}s ...")
            time.sleep(SLEEP_BETWEEN)

    return success, skipped, failed, done


# ============================================================
# 後片付け
# ============================================================
def _cleanup_on_success(failed: int, progress_file: str) -> None:
    if failed == 0:
        for path in [progress_file, RAW_DIR]:
            if os.path.exists(path):
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                logger.info(f"Cleaned up: {path}")


# ============================================================
# メイン
# ============================================================
def run_batch():
    args = parse_args()
    queries = load_queries(QUERIES_FILE)
    total = len(queries)
    started_at = time.time()

    progress_file = args.get("progress_file") or DEFAULT_PROGRESS_FILE

    city = args["city"]
    pref = args["prefecture"]
    if not city:
        city, pref = detect_city_from_queries(QUERIES_FILE)
    run_id = f"{pref}_{city}".replace(" ", "_")

    if city or pref:
        logger.info(f"City filter: {pref}{city}")
    else:
        logger.info("City filter: OFF (no --city specified, could not auto-detect)")

    logger.info(f"Queries: {total}")
    logger.info(f"Sleep between: {SLEEP_BETWEEN}s")
    logger.info(f"Est. time: ~{total * (180 + SLEEP_BETWEEN) // 60} min")

    os.makedirs(RAW_DIR, exist_ok=True)
    publish_expansion_status(
        run_id,
        pref=pref,
        city=city,
        total=total,
        done=0,
        success=0,
        failed=0,
        started_at=started_at,
        status="running",
        message="started",
    )

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
            shutil.copy(RAW_OUTPUT, RAW_OUTPUT + ".bak")
            logger.info("Previous data backed up.")
        if os.path.exists(RAW_DIR):
            shutil.rmtree(RAW_DIR)
        os.makedirs(RAW_DIR, exist_ok=True)
        logger.info("")

    success, skipped, failed, done = _execute_scraping_loop(
        queries, total, done, progress_file, args, run_id, started_at,
    )

    logger.info(f"\n{'=' * 50}")
    logger.info(f"  Scraping done  OK: {success} / Skip: {skipped} / Fail: {failed}")
    logger.info(f"{'=' * 50}\n")

    try:
        data_for_processing = _prepare_input_data(city, pref)
        run_postprocess_pipeline(data_for_processing, PROCESSED, SCRIPT_DIR)
    except RuntimeError as exc:
        publish_expansion_status(
            run_id,
            pref=pref,
            city=city,
            total=total,
            done=len(done),
            success=success,
            failed=failed + 1,
            started_at=started_at,
            status="failed",
            message=str(exc),
        )
        logger.error(f"[ERROR] {exc}")
        sys.exit(1)

    _cleanup_on_success(failed, progress_file)
    if failed > 0:
        publish_expansion_status(
            run_id,
            pref=pref,
            city=city,
            total=total,
            done=len(done),
            success=success,
            failed=failed,
            started_at=started_at,
            status="failed",
            message=f"{failed} queries failed",
        )
        logger.error(f"[ERROR] Scrape finished with {failed} failed queries")
        sys.exit(1)

    publish_expansion_status(
        run_id,
        pref=pref,
        city=city,
        total=total,
        done=len(done),
        success=success,
        failed=failed,
        started_at=started_at,
        status="done",
        message="completed",
    )
    logger.info(f"\nOutput: {os.path.abspath(PROCESSED)}")


if __name__ == "__main__":
    run_batch()
