"""
batch/scrape_filter.py
スクレイプ結果の都市フィルタリング
scrape_runner.py から抽出
"""
from pathlib import Path

from city_bounds import filter_raw_data, get_city_bounds
from exceptions import DataError
from progress_tracker import load_queries, merge_part_files
from utils import count_lines, logger


def fetch_city_bounds(city: str, pref: str) -> dict | None:
    if pref and not city:
        return get_city_bounds(pref)
    if pref:
        bounds = get_city_bounds(city, pref)
        if bounds:
            return bounds
    return get_city_bounds(city)


def apply_city_filter(
    city: str, pref: str, raw_output: str, raw_dir: str, queries_file: str
) -> tuple[str, int, int]:
    bounds = fetch_city_bounds(city, pref)
    filtered_path = str(Path(raw_output).with_name(Path(raw_output).stem + "_filtered.json"))
    total_raw, kept = filter_raw_data(raw_output, filtered_path, city, bounds)
    return filtered_path, total_raw, kept


def prepare_input_data(
    city: str, pref: str, raw_output: str, raw_dir: str, queries_file: str
) -> str:
    logger.info("Merging results...")
    merge_part_files(raw_dir, raw_output, len(load_queries(queries_file)))
    total_lines = count_lines(raw_output)
    logger.info(f"Total raw data: {total_lines} entries")

    if not city and not pref:
        return raw_output

    filtered_path, total_raw, kept = apply_city_filter(city, pref, raw_output, raw_dir, queries_file)
    if kept == 0:
        filter_label = f"{pref}{city}" if pref else city
        logger.warning(f"\n  WARNING: No entries matched city filter '{filter_label}'")
        logger.info(f"  ({total_raw} raw entries were checked)")
        raise DataError(f"No entries matched city filter '{filter_label}'")

    pct = kept / total_raw * 100 if total_raw > 0 else 0
    logger.info(f"  City filter: {kept}/{total_raw} entries kept ({pct:.1f}%)")
    return filtered_path
