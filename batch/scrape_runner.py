# mypy: disable-error-code="no-redef"
"""Batch scrape runner with resumable query-fingerprint progress."""

from __future__ import annotations

import os
import shutil
import time

try:
    from .cli_parser import detect_city_from_queries, parse_args
    from .docker_exec import scrape_query
    from .pipeline import run_postprocess_pipeline
    from .progress_tracker import PROGRESS_FILE as DEFAULT_PROGRESS_FILE
    from .progress_tracker import (
        load_progress,
        load_queries,
        publish_expansion_status,
        query_fingerprint,
        save_progress,
    )
    from .scrape_filter import prepare_input_data
    from .utils import logger
except ImportError:
    from cli_parser import detect_city_from_queries, parse_args
    from docker_exec import scrape_query
    from pipeline import run_postprocess_pipeline
    from progress_tracker import PROGRESS_FILE as DEFAULT_PROGRESS_FILE
    from progress_tracker import load_progress, load_queries, publish_expansion_status, query_fingerprint, save_progress
    from scrape_filter import prepare_input_data
    from utils import logger

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
QUERIES_FILE = os.path.join(SCRIPT_DIR, os.environ.get("QUERIES", "queries.txt"))
RAW_DIR = os.path.join(SCRIPT_DIR, os.environ.get("RAW_DIR", "raw_parts"))
RAW_OUTPUT = os.path.join(SCRIPT_DIR, os.environ.get("RAW_OUTPUT", "raw_data.json"))
PROCESSED = os.path.join(SCRIPT_DIR, "..", "data", "toilets.json.gz")

SLEEP_BETWEEN = int(os.environ.get("SLEEP_BETWEEN", "120"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "2"))
RETRY_SLEEP = int(os.environ.get("RETRY_SLEEP", "300"))
SYNC_EVERY_SUCCESS = int(os.environ.get("SYNC_EVERY_SUCCESS", "0"))


def _sync_canonical_data(city: str, pref: str) -> None:
    data_for_processing = prepare_input_data(city, pref, RAW_OUTPUT, RAW_DIR, QUERIES_FILE)
    run_postprocess_pipeline(data_for_processing, PROCESSED, SCRIPT_DIR)


def _maybe_sync_after_success(city: str, pref: str, success_count: int) -> None:
    if SYNC_EVERY_SUCCESS > 0 and success_count % SYNC_EVERY_SUCCESS == 0:
        logger.info(f"Syncing canonical data after {success_count} successful queries...")
        _sync_canonical_data(city, pref)


def _execute_scraping_loop(
    queries: list[str],
    total: int,
    done: dict[int, str],
    progress_file: str,
    args: dict,
    run_id: str,
    started_at: float,
) -> tuple[int, int, int, dict[int, str]]:
    success = skipped = failed = 0
    city = args.get("city", "")
    pref = args.get("prefecture", "")

    max_queries = args.get("max_queries")
    if max_queries is not None:
        queries = queries[:max_queries]
        total = len(queries)
        logger.info(f"[MAX-QUERIES] Limited to first {total} queries")

    done = {index: fingerprint for index, fingerprint in done.items() if 1 <= index <= total}
    if done:
        logger.info(f"Resuming: {len(done)}/{total} progress rows loaded.")

    if args.get("dry_run"):
        logger.info("[DRY-RUN] Dockerスクレイプをスキップします。")
        for index, query in enumerate(queries, 1):
            done[index] = query_fingerprint(query)
        save_progress(done, progress_file)
        publish_expansion_status(
            run_id,
            pref=pref,
            city=city,
            total=total,
            done=len(done),
            success=0,
            failed=0,
            started_at=started_at,
            status="running",
            message="dry-run",
        )
        return 0, 0, 0, done

    for index, query in enumerate(queries, 1):
        part_file = os.path.join(RAW_DIR, f"part_{index:03d}.json")
        fingerprint = query_fingerprint(query)
        if done.get(index) == fingerprint and os.path.exists(part_file):
            logger.info(f"[{index}/{total}] (done) {query}")
            skipped += 1
            continue
        if index in done:
            logger.info(f"[{index}/{total}] Query changed; invalidating stale progress entry")
            done.pop(index, None)

        logger.info(f"\n{'=' * 50}")
        logger.info(f"[{index}/{total}] {query}")
        logger.info(f"{'=' * 50}")

        succeeded = False
        for retry in range(MAX_RETRIES + 1):
            if retry > 0:
                logger.info(f"  Retry #{retry} ... waiting {RETRY_SLEEP}s")
                time.sleep(RETRY_SLEEP)
            if scrape_query(query, part_file, cwd=SCRIPT_DIR):
                succeeded = True
                break

        if succeeded:
            success += 1
            done[index] = fingerprint
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

        if succeeded and index < total:
            logger.info(f"  Sleeping {SLEEP_BETWEEN}s ...")
            time.sleep(SLEEP_BETWEEN)

    return success, skipped, failed, done


def _cleanup_on_success(failed: int, progress_file: str) -> None:
    if failed != 0:
        return
    for path in [progress_file, RAW_DIR]:
        if not os.path.exists(path):
            continue
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        logger.info(f"Cleaned up: {path}")


def run_batch() -> None:
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

    logger.info(f"City filter: {pref}{city}" if city or pref else "City filter: OFF")
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
        logger.info(f"Resuming: {len(done)}/{total} progress rows found.")
        for index in list(done):
            if not os.path.exists(os.path.join(RAW_DIR, f"part_{index:03d}.json")):
                logger.warning(f"Missing part file for query #{index} - will re-run")
                done.pop(index, None)
    else:
        if os.path.exists(RAW_OUTPUT):
            shutil.copy(RAW_OUTPUT, RAW_OUTPUT + ".bak")
            logger.info("Previous data backed up.")
        if os.path.exists(RAW_DIR):
            shutil.rmtree(RAW_DIR)
        os.makedirs(RAW_DIR, exist_ok=True)

    success, skipped, failed, done = _execute_scraping_loop(
        queries, total, done, progress_file, args, run_id, started_at
    )

    logger.info(f"Scraping done  OK: {success} / Skip: {skipped} / Fail: {failed}")
    try:
        _sync_canonical_data(city, pref)
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
        raise SystemExit(1) from exc

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
        raise SystemExit(1)

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
    logger.info(f"Output: {os.path.abspath(PROCESSED)}")


if __name__ == "__main__":
    run_batch()
