"""
batch/quality_metrics.py
トイレデータ品質メトリクス収集・検証
verify_data.py から分離
"""
import os
import sqlite3
import logging
from collections import Counter
from typing import Iterable


logger = logging.getLogger(__name__)


def _coerce_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rate(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return count / total


def collect_quality_metrics(toilets: list[dict]) -> dict:
    pref_counts = Counter(t.get("prefecture", "不明") for t in toilets)
    missing_score = sum(1 for t in toilets if t.get("toilet_score") is None)
    missing_pref = sum(1 for t in toilets if not t.get("prefecture"))
    missing_addr = sum(1 for t in toilets if not t.get("address"))

    seen = {}
    duplicates = []
    for toilet in toilets:
        place_id = toilet.get("place_id", "")
        data_id = toilet.get("data_id", "")
        lat = _coerce_float(toilet.get("lat"))
        lng = _coerce_float(toilet.get("lng"))
        if place_id:
            key = ("place_id", str(place_id))
        elif data_id:
            key = ("data_id", str(data_id))
        elif lat is not None and lng is not None:
            key = ("coordinates", f"{lat:.6f}", f"{lng:.6f}")
        else:
            key = ("title_address", toilet.get("title", ""), toilet.get("address", ""))
        if key in seen:
            duplicates.append(
                {
                    "key": key,
                    "link": toilet.get("link", ""),
                }
            )
        else:
            seen[key] = toilet.get("link", "")

    return {
        "total": len(toilets),
        "prefecture_counts": pref_counts,
        "missing_score": missing_score,
        "missing_prefecture": missing_pref,
        "missing_address": missing_addr,
        "duplicates": duplicates,
    }


def collect_sqlite_metrics(db_path: str) -> dict | None:
    if not os.path.exists(db_path):
        return None

    conn = sqlite3.connect(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
        scored = conn.execute("SELECT COUNT(*) FROM toilets WHERE confidence > 0").fetchone()[0]
        public_toilets = conn.execute("SELECT COUNT(*) FROM toilets WHERE is_public_toilet = 1").fetchone()[0]
        prefecture_rows = conn.execute(
            """
            SELECT COALESCE(NULLIF(TRIM(prefecture), ''), '') AS prefecture, COUNT(*)
            FROM toilets
            GROUP BY COALESCE(NULLIF(TRIM(prefecture), ''), '')
            """
        ).fetchall()
        metadata_rows = conn.execute("SELECT key, value FROM metadata").fetchall()
        return {
            "total": total,
            "scored": scored,
            "public_toilets": public_toilets,
            "prefecture_counts": {str(prefecture or ""): int(count) for prefecture, count in prefecture_rows},
            "metadata": dict(metadata_rows),
        }
    except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
        logger.error(f"Failed to collect SQLite metrics from {db_path}: {exc}")
        return None
    finally:
        conn.close()


def _normalize_count_map(values: dict | Counter) -> dict[str, int]:
    normalized: dict[str, int] = {}
    for key, value in values.items():
        count = _coerce_int(value)
        if count is None:
            continue
        normalized[str(key or "")] = count
    return normalized


def compare_sqlite_metrics(meta: dict, sqlite_metrics: dict) -> tuple[list[str], list[str]]:
    errors = []
    warnings = []

    json_total = _coerce_int(meta.get("total"))
    json_scored = _coerce_int(meta.get("scored"))
    json_public = _coerce_int(meta.get("public_toilets"))

    if json_total is not None and json_total != sqlite_metrics["total"]:
        errors.append(f"SQLite total mismatch: json={json_total}, db={sqlite_metrics['total']}")
    if json_scored is not None and json_scored != sqlite_metrics["scored"]:
        errors.append(f"SQLite scored mismatch: json={json_scored}, db={sqlite_metrics['scored']}")
    if json_public is not None and json_public != sqlite_metrics["public_toilets"]:
        errors.append(f"SQLite public_toilets mismatch: json={json_public}, db={sqlite_metrics['public_toilets']}")

    json_last_updated = str(meta.get("last_updated") or "").strip()
    sqlite_last_updated = str(sqlite_metrics.get("metadata", {}).get("last_updated") or "").strip()
    sqlite_synced_at = str(sqlite_metrics.get("metadata", {}).get("db_synced_at") or "").strip()

    if json_last_updated and sqlite_last_updated and json_last_updated != sqlite_last_updated:
        warnings.append(f"SQLite last_updated mismatch: json={json_last_updated}, db={sqlite_last_updated}")
    if json_last_updated and not sqlite_last_updated:
        warnings.append("SQLite last_updated missing")
    if not sqlite_synced_at:
        warnings.append("SQLite db_synced_at missing")

    json_prefecture_counts = _normalize_count_map(meta.get("prefecture_counts", {}))
    sqlite_prefecture_counts = _normalize_count_map(sqlite_metrics.get("prefecture_counts", {}))
    for prefecture in sorted(set(json_prefecture_counts) | set(sqlite_prefecture_counts)):
        json_count = json_prefecture_counts.get(prefecture)
        sqlite_count = sqlite_prefecture_counts.get(prefecture)
        if json_count is None:
            errors.append(f"SQLite has unexpected prefecture: {prefecture}={sqlite_count}")
        elif sqlite_count is None:
            errors.append(f"SQLite missing prefecture: {prefecture} (json={json_count})")
        elif json_count != sqlite_count:
            errors.append(
                f"SQLite prefecture count mismatch: {prefecture}: json={json_count}, db={sqlite_count}"
            )

    return errors, warnings


def _format_duplicate_key(key: tuple[str, ...]) -> str:
    if not key:
        return ""
    kind = key[0]
    if kind == "place_id" and len(key) > 1:
        return f"place_id={key[1]}"
    if kind == "data_id" and len(key) > 1:
        return f"data_id={key[1]}"
    if kind == "coordinates" and len(key) > 2:
        return f"coordinates={key[1]},{key[2]}"
    if kind == "title_address" and len(key) > 2:
        title = key[1]
        address = key[2]
        return f"{title} / {address[:30]}..."
    return " / ".join(str(part) for part in key)


MAX_MISSING_SCORE_RATE = 0.2
MAX_MISSING_PREFECTURE_RATE = 0.1
MAX_MISSING_ADDRESS_RATE = 0.1
MAX_DUPLICATE_RATE = 0.02


def evaluate_quality_gate(metrics: dict, expected_prefectures: Iterable[str]) -> tuple[list[str], list[str]]:
    total = metrics.get("total", 0)
    errors = []
    warnings = []

    missing_score_rate = _rate(metrics.get("missing_score", 0), total)
    missing_pref_rate = _rate(metrics.get("missing_prefecture", 0), total)
    missing_addr_rate = _rate(metrics.get("missing_address", 0), total)
    duplicate_rate = _rate(len(metrics.get("duplicates", [])), total)

    if missing_score_rate > MAX_MISSING_SCORE_RATE:
        errors.append(f"Missing score rate too high: {missing_score_rate:.1%}")
    if missing_pref_rate > MAX_MISSING_PREFECTURE_RATE:
        errors.append(f"Missing prefecture rate too high: {missing_pref_rate:.1%}")
    if missing_addr_rate > MAX_MISSING_ADDRESS_RATE:
        errors.append(f"Missing address rate too high: {missing_addr_rate:.1%}")
    if duplicate_rate > MAX_DUPLICATE_RATE:
        errors.append(f"Duplicate rate too high: {duplicate_rate:.1%}")

    pref_counts = metrics.get("prefecture_counts", {})
    for pref in expected_prefectures:
        if pref_counts.get(pref, 0) == 0:
            warnings.append(f"No records found for {pref}")

    return errors, warnings
