"""
batch/auto_expand.py
不足エリア向けの自動拡張スクリプト
本モジュールは test_batch_regressions.py からインポートされる。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import logger
from db_utils import load_json
from gap_analyzer import find_gaps, get_stats
from expansion_query import (
    CITY_QUERY_BUDGET_TEMPLATES,
    PREFECTURE_QUERY_BUDGET_TEMPLATES,
    query_limits_for_count,
    set_active_context,
    _slugify,
    ensure_query_files,
    find_batch_files,
    merge_query_files,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
QUERIES_DIR = os.path.join(SCRIPT_DIR, "queries.d")
CURRENT_DATA_PATHS = [
    os.path.join(PROJECT_ROOT, "data", "toilets.json.gz"),
    os.path.join(PROJECT_ROOT, "data", "toilets.json"),
]


def _load_current_stats() -> dict:
    for data_path in CURRENT_DATA_PATHS:
        if not os.path.exists(data_path):
            continue
        try:
            data = load_json(data_path)
        except (OSError, ValueError):
            continue
        toilets = data.get("toilets", []) if isinstance(data, dict) else []
        if isinstance(toilets, list):
            return get_stats(toilets)
    return get_stats([])


def _lookup_city_count(stats: dict, prefecture: str, city: str) -> int:
    nested = stats.get("prefecture_city_counts", {})
    if isinstance(nested, dict):
        city_counts = nested.get(prefecture, {})
        if isinstance(city_counts, dict) and city in city_counts:
            try:
                return int(city_counts.get(city, 0))
            except (TypeError, ValueError):
                return 0
    return 0


def _build_gap_entry(stats: dict, prefecture: str, city: str, count: int | None = None) -> dict:
    if count is None:
        count = _lookup_city_count(stats, prefecture, city)
    nested = stats.get("prefecture_city_counts", {})
    prefecture_total = 0
    if isinstance(nested, dict):
        city_counts = nested.get(prefecture, {})
        if isinstance(city_counts, dict):
            try:
                prefecture_total = sum(int(value) for value in city_counts.values())
            except (TypeError, ValueError):
                prefecture_total = 0
    return {
        "prefecture": prefecture,
        "city": city,
        "count": int(count or 0),
        "prefecture_total": prefecture_total,
        "active": prefecture_total > 0,
        "message": f"データ不足: {int(count or 0)}件",
    }


def _select_targets(stats: dict, max_areas: int, target_pref: str = "", target_city: str = "") -> list[dict]:
    gaps = find_gaps(stats, include_catalog=True)

    if target_pref and target_city:
        exact = [gap for gap in gaps if gap.get("prefecture") == target_pref and gap.get("city") == target_city]
        if exact:
            return exact[:1]
        return [_build_gap_entry(stats, target_pref, target_city)]

    if target_pref:
        filtered = [gap for gap in gaps if gap.get("prefecture") == target_pref]
        if filtered:
            return filtered[:max_areas]

        nested = stats.get("prefecture_city_counts", {})
        city_counts = nested.get(target_pref, {}) if isinstance(nested, dict) else {}
        if isinstance(city_counts, dict) and city_counts:
            ordered = sorted(city_counts.items(), key=lambda item: (int(item[1]), item[0]))
            return [_build_gap_entry(stats, target_pref, city) for city, _ in ordered[:max_areas]]

        return []

    if target_city:
        filtered = [gap for gap in gaps if gap.get("city") == target_city]
        if filtered:
            return filtered[:1]

        nested = stats.get("prefecture_city_counts", {})
        if isinstance(nested, dict):
            for prefecture, city_counts in nested.items():
                if isinstance(city_counts, dict) and target_city in city_counts:
                    return [_build_gap_entry(stats, prefecture, target_city)]

        return []

    return gaps[:max_areas]


def run_auto_expansion(max_areas: int = 5, target_pref: str = "", target_city: str = "") -> None:
    if max_areas <= 0:
        return

    stats = _load_current_stats()
    targets = _select_targets(stats, max_areas=max_areas, target_pref=target_pref, target_city=target_city)
    if not targets:
        logger.info("No expansion targets found.")
        return

    prev_context = set_active_context("", "", 0, 0)

    try:
        logger.info(f"Selected {len(targets)} area(s) for auto expansion.")
        for target in targets[:max_areas]:
            prefecture = str(target.get("prefecture") or "")
            city = str(target.get("city") or "")
            count = int(target.get("count", 0) or 0)
            city_budget, pref_budget = query_limits_for_count(count)

            set_active_context(prefecture, city, city_budget, pref_budget)

            logger.info(
                f"[EXPAND] {prefecture} {city} (count={count}, city_budget={city_budget}, pref_budget={pref_budget})"
            )

            ensure_query_files(prefecture)
            batch_files = find_batch_files(prefecture)
            merged_query_file = merge_query_files(batch_files)
            if not merged_query_file:
                logger.warning(f"[{prefecture}] No query files were merged.")
                continue

            area_slug = _slugify(f"{prefecture}_{city or 'pref'}")
            raw_dir = os.path.join(SCRIPT_DIR, f"raw_parts_{area_slug}")
            raw_output = os.path.join(SCRIPT_DIR, f"raw_data_{area_slug}.json")
            progress_file = os.path.join(SCRIPT_DIR, f".progress_auto_{area_slug}")

            env = os.environ.copy()
            env["QUERIES"] = merged_query_file
            env["RAW_DIR"] = raw_dir
            env["RAW_OUTPUT"] = raw_output
            env["PROGRESS_FILE"] = progress_file
            env["SYNC_EVERY_SUCCESS"] = "1"

            cmd = [
                sys.executable,
                os.path.join(SCRIPT_DIR, "scrape_runner.py"),
                "--prefecture",
                prefecture,
            ]
            if city:
                cmd.extend(["--city", city])

            try:
                result = subprocess.run(cmd, env=env, cwd=SCRIPT_DIR)
            except FileNotFoundError:
                logger.error("Python executable or Docker runtime not found for auto expansion.")
                break

            if result.returncode != 0:
                logger.error(f"[{prefecture}] auto expansion failed with exit code {result.returncode}")
    finally:
        set_active_context(*prev_context)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="不足エリア向けの自動拡張を実行する")
    parser.add_argument("--max-areas", type=int, default=5, help="一度に拡張する最大エリア数")
    parser.add_argument("--prefecture", default="", help="対象都道府県を固定する")
    parser.add_argument("--city", default="", help="対象市区町村を固定する")
    args = parser.parse_args()

    run_auto_expansion(args.max_areas, args.prefecture, args.city)


if __name__ == "__main__":
    main()
