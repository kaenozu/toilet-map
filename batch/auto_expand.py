"""
batch/auto_expand.py
不足エリア向けの自動拡張スクリプト
本モジュールは test_batch_regressions.py からインポートされる。
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from utils import logger
except ModuleNotFoundError:  # pragma: no cover - import path fallback
    from batch.utils import logger

try:
    from db_utils import load_json
except ModuleNotFoundError:  # pragma: no cover - import path fallback
    from batch.db_utils import load_json

try:
    from gap_analyzer import find_gaps, get_stats
except ModuleNotFoundError:  # pragma: no cover - import path fallback
    from batch.gap_analyzer import find_gaps, get_stats

try:
    from generate_queries import (
        CITY_QUERY_TEMPLATES as GENERATE_CITY_QUERY_TEMPLATES,
        PREFECTURE_QUERY_TEMPLATES as GENERATE_PREFECTURE_QUERY_TEMPLATES,
        build_queries,
        write_batches,
    )
except ModuleNotFoundError:  # pragma: no cover - import path fallback
    from batch.generate_queries import (
        CITY_QUERY_TEMPLATES as GENERATE_CITY_QUERY_TEMPLATES,
        PREFECTURE_QUERY_TEMPLATES as GENERATE_PREFECTURE_QUERY_TEMPLATES,
        build_queries,
        write_batches,
    )


CITY_QUERY_TEMPLATES = ["{city} トイレ", "{city} 公衆トイレ"]
PREFECTURE_QUERY_TEMPLATES = ["{pref} トイレ きれい", "{pref} トイレ アクセス"]


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
QUERIES_DIR = os.path.join(SCRIPT_DIR, "queries.d")
CURRENT_DATA_PATHS = [
    os.path.join(PROJECT_ROOT, "data", "toilets.json.gz"),
    os.path.join(PROJECT_ROOT, "data", "toilets.json"),
]

_ACTIVE_TARGET_PREF = ""
_ACTIVE_TARGET_CITY = ""
_ACTIVE_CITY_BUDGET = 0
_ACTIVE_PREF_BUDGET = 0


def _query_limits_for_count(count: int) -> tuple[int, int]:
    """エリアのデータ数に応じたクエリ制限を算出する。"""
    if count == 0:
        return (8, 4)
    if count < 4:
        return (12, 4)
    if count < 6:
        return (16, 6)
    return (len(CITY_QUERY_TEMPLATES), len(PREFECTURE_QUERY_TEMPLATES))


def _slugify(value: str) -> str:
    """ファイル名向けに簡単に文字列を正規化する。"""
    safe_chars = []
    for char in value:
        if char.isalnum() or char in {"-", "_"}:
            safe_chars.append(char)
        else:
            safe_chars.append("_")
    slug = "".join(safe_chars).strip("_")
    return slug or "all"


def _load_query_lines(path: Path) -> list[str]:
    lines: list[str] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for raw_line in f:
                stripped = raw_line.strip()
                if stripped and not stripped.startswith("#"):
                    lines.append(stripped)
    except OSError:
        return []
    return lines


def _read_query_header(path: Path) -> tuple[str, str]:
    city = ""
    prefecture = ""
    try:
        with path.open("r", encoding="utf-8") as f:
            for _ in range(5):
                raw_line = f.readline()
                if not raw_line:
                    break
                stripped = raw_line.strip()
                if stripped.startswith("# city:"):
                    city = stripped.split(":", 1)[1].strip()
                elif stripped.startswith("# prefecture:"):
                    prefecture = stripped.split(":", 1)[1].strip()
                if city and prefecture:
                    break
    except OSError as exc:
        logger.warning(f"Failed to read query header: {path} ({exc})")
    return city, prefecture


def _file_mentions_city(path: Path, city: str) -> bool:
    if not city:
        return False
    return any(city in line for line in _load_query_lines(path))


def _next_batch_index(pref_dir: Path) -> int:
    indices = [0]
    for path in pref_dir.glob("batch_*.txt"):
        try:
            indices.append(int(path.stem.split("_", 1)[1]))
        except (IndexError, ValueError):
            continue
    return max(indices) + 1


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


def _ensure_query_files(pref: str) -> None:
    """クエリファイルが存在することを確認する。"""
    pref_dir = Path(QUERIES_DIR) / pref
    pref_dir.mkdir(parents=True, exist_ok=True)

    if not _ACTIVE_TARGET_CITY:
        return

    target_label = f"{pref}{_ACTIVE_TARGET_CITY}" if pref else _ACTIVE_TARGET_CITY
    target_path = pref_dir / "batch_000_target.txt"
    city_queries = build_queries([target_label], GENERATE_CITY_QUERY_TEMPLATES)
    with target_path.open("w", encoding="utf-8") as f:
        f.write(f"# city: {_ACTIVE_TARGET_CITY}\n")
        if pref:
            f.write(f"# prefecture: {pref}\n")
        f.write("\n".join(city_queries) + "\n")

    if not pref:
        return

    has_pref_queries = False
    for path in pref_dir.glob("batch_*.txt"):
        if path.name == target_path.name:
            continue
        header_city, header_pref = _read_query_header(path)
        if header_pref == pref and not header_city:
            has_pref_queries = True
            break

    if has_pref_queries:
        return

    pref_queries = build_queries([pref], GENERATE_PREFECTURE_QUERY_TEMPLATES)
    write_batches(
        pref_queries,
        str(pref_dir),
        city="",
        prefecture=pref,
        start_index=_next_batch_index(pref_dir),
    )


def _find_batch_files(pref: str) -> list[Path]:
    """バッチファイルを検索する。"""
    pref_dir = Path(QUERIES_DIR) / pref
    if not pref_dir.exists():
        return []
    return sorted(pref_dir.glob("batch_*.txt"))


def _classify_query_file(path: Path) -> str:
    header_city, header_pref = _read_query_header(path)
    if _ACTIVE_TARGET_CITY:
        if header_city and header_city != _ACTIVE_TARGET_CITY:
            return ""
        if header_city == _ACTIVE_TARGET_CITY or _file_mentions_city(path, _ACTIVE_TARGET_CITY):
            return "city"
        if header_pref and _ACTIVE_TARGET_PREF and header_pref != _ACTIVE_TARGET_PREF:
            return ""
        return "pref"
    return "pref" if not header_city else "city"


def _merge_query_files(files: list[str | Path]) -> str:
    """クエリファイルをマージする。"""
    city_budget = _ACTIVE_CITY_BUDGET or len(CITY_QUERY_TEMPLATES)
    pref_budget = _ACTIVE_PREF_BUDGET or len(PREFECTURE_QUERY_TEMPLATES)
    city_queries: list[str] = []
    pref_queries: list[str] = []
    seen: set[str] = set()

    for file_path in files:
        path = Path(file_path)
        if not path.exists():
            continue

        bucket = _classify_query_file(path)
        if not bucket:
            continue

        bucket_queries = city_queries if bucket == "city" else pref_queries
        bucket_budget = city_budget if bucket == "city" else pref_budget

        for query in _load_query_lines(path):
            if len(bucket_queries) >= bucket_budget:
                break
            if query in seen:
                continue
            bucket_queries.append(query)
            seen.add(query)

    merged_queries = city_queries + pref_queries
    if not merged_queries:
        return ""

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".txt", dir=SCRIPT_DIR) as tmp:
        if _ACTIVE_TARGET_PREF:
            tmp.write(f"# prefecture: {_ACTIVE_TARGET_PREF}\n")
        if _ACTIVE_TARGET_CITY:
            tmp.write(f"# city: {_ACTIVE_TARGET_CITY}\n")
        for query in merged_queries:
            tmp.write(f"{query}\n")
        return tmp.name


def run_auto_expansion(max_areas: int = 5, target_pref: str = "", target_city: str = "") -> None:
    """不足エリアに対して優先順位付きで自動拡張を実行する。"""
    if max_areas <= 0:
        return

    stats = _load_current_stats()
    targets = _select_targets(stats, max_areas=max_areas, target_pref=target_pref, target_city=target_city)
    if not targets:
        logger.info("No expansion targets found.")
        return

    global _ACTIVE_TARGET_PREF, _ACTIVE_TARGET_CITY, _ACTIVE_CITY_BUDGET, _ACTIVE_PREF_BUDGET
    previous_context = (_ACTIVE_TARGET_PREF, _ACTIVE_TARGET_CITY, _ACTIVE_CITY_BUDGET, _ACTIVE_PREF_BUDGET)

    try:
        logger.info(f"Selected {len(targets)} area(s) for auto expansion.")
        for target in targets[:max_areas]:
            prefecture = str(target.get("prefecture") or "")
            city = str(target.get("city") or "")
            count = int(target.get("count", 0) or 0)
            city_budget, pref_budget = _query_limits_for_count(count)

            _ACTIVE_TARGET_PREF = prefecture
            _ACTIVE_TARGET_CITY = city
            _ACTIVE_CITY_BUDGET = city_budget
            _ACTIVE_PREF_BUDGET = pref_budget

            logger.info(
                f"[EXPAND] {prefecture} {city} (count={count}, city_budget={city_budget}, pref_budget={pref_budget})"
            )

            _ensure_query_files(prefecture)
            batch_files = _find_batch_files(prefecture)
            merged_query_file = _merge_query_files(batch_files)
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
        _ACTIVE_TARGET_PREF, _ACTIVE_TARGET_CITY, _ACTIVE_CITY_BUDGET, _ACTIVE_PREF_BUDGET = previous_context


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
