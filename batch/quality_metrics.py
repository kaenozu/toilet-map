# mypy: disable-error-code="no-redef"
"""Data quality metrics for JSON and SQLite snapshots."""

from __future__ import annotations

import logging
import os
import sqlite3
from collections import Counter
from collections.abc import Iterable

try:
    from .identity import build_source_id
except ImportError:
    from identity import build_source_id

logger = logging.getLogger(__name__)


def _coerce_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return None


def _coerce_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _rate(count: int, total: int) -> float:
    return count / total if total > 0 else 0.0


def collect_quality_metrics(toilets: list[dict]) -> dict:
    prefecture_counts = Counter(toilet.get("prefecture", "不明") for toilet in toilets)
    seen: dict[str, str] = {}
    duplicates: list[dict] = []
    for toilet in toilets:
        explicit_source_id = str(toilet.get("source_id") or "").strip()
        place_id = str(toilet.get("place_id") or "").strip()
        data_id = str(toilet.get("data_id") or "").strip()
        lat = _coerce_float(toilet.get("lat"))
        lng = _coerce_float(toilet.get("lng"))
        if explicit_source_id:
            key: tuple[str, ...] = ("source_id", explicit_source_id)
        elif place_id:
            key = ("place_id", place_id)
        elif data_id:
            key = ("data_id", data_id)
        elif lat is not None and lng is not None and not toilet.get("address") and not toilet.get("category"):
            key = ("coordinates", f"{lat:.6f}", f"{lng:.6f}")
        else:
            key = ("source_id", build_source_id(toilet))
        key_text = "|".join(key)
        if key_text in seen:
            duplicates.append({"key": key, "link": toilet.get("link", "")})
        else:
            seen[key_text] = str(toilet.get("link", ""))
    return {
        "total": len(toilets),
        "prefecture_counts": prefecture_counts,
        "missing_score": sum(toilet.get("toilet_score") is None for toilet in toilets),
        "missing_prefecture": sum(not toilet.get("prefecture") for toilet in toilets),
        "missing_address": sum(not toilet.get("address") for toilet in toilets),
        "duplicates": duplicates,
    }


def collect_sqlite_metrics(db_path: str) -> dict | None:
    if not os.path.exists(db_path):
        return None
    connection = sqlite3.connect(db_path)
    try:
        total = connection.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
        scored = connection.execute("SELECT COUNT(*) FROM toilets WHERE confidence > 0").fetchone()[0]
        public_toilets = connection.execute("SELECT COUNT(*) FROM toilets WHERE is_public_toilet = 1").fetchone()[0]
        prefecture_rows = connection.execute(
            "SELECT COALESCE(NULLIF(TRIM(prefecture), ''), ''), COUNT(*) FROM toilets GROUP BY 1"
        ).fetchall()
        metadata_rows = connection.execute("SELECT key, value FROM metadata").fetchall()
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
        connection.close()


def _normalize_count_map(values: dict | Counter) -> dict[str, int]:
    normalized: dict[str, int] = {}
    for key, value in values.items():
        if (count := _coerce_int(value)) is not None:
            normalized[str(key or "")] = count
    return normalized


def compare_sqlite_metrics(meta: dict, sqlite_metrics: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for meta_key, sqlite_key in (("total", "total"), ("scored", "scored"), ("public_toilets", "public_toilets")):
        expected = _coerce_int(meta.get(meta_key))
        actual = sqlite_metrics[sqlite_key]
        if expected is not None and expected != actual:
            errors.append(f"SQLite {sqlite_key} mismatch: json={expected}, db={actual}")
    json_last_updated = str(meta.get("last_updated") or "").strip()
    sqlite_metadata = sqlite_metrics.get("metadata", {})
    sqlite_last_updated = str(sqlite_metadata.get("last_updated") or "").strip()
    if json_last_updated and sqlite_last_updated and json_last_updated != sqlite_last_updated:
        warnings.append(f"SQLite last_updated mismatch: json={json_last_updated}, db={sqlite_last_updated}")
    if json_last_updated and not sqlite_last_updated:
        warnings.append("SQLite last_updated missing")
    if not sqlite_metadata.get("db_synced_at"):
        warnings.append("SQLite db_synced_at missing")

    json_counts = _normalize_count_map(meta.get("prefecture_counts", {}))
    sqlite_counts = _normalize_count_map(sqlite_metrics.get("prefecture_counts", {}))
    for prefecture in sorted(set(json_counts) | set(sqlite_counts)):
        expected, actual = json_counts.get(prefecture), sqlite_counts.get(prefecture)
        if expected is None:
            errors.append(f"SQLite has unexpected prefecture: {prefecture}={actual}")
        elif actual is None:
            errors.append(f"SQLite missing prefecture: {prefecture} (json={expected})")
        elif expected != actual:
            errors.append(f"SQLite prefecture count mismatch: {prefecture}: json={expected}, db={actual}")
    return errors, warnings


def _format_duplicate_key(key: tuple[str, ...]) -> str:
    if not key:
        return ""
    kind = key[0]
    if kind in {"source_id", "place_id", "data_id"} and len(key) > 1:
        return f"{kind}={key[1]}"
    if kind == "coordinates" and len(key) > 2:
        return f"coordinates={key[1]},{key[2]}"
    if kind == "title_address" and len(key) > 2:
        return f"{key[1]} / {key[2][:30]}..."
    return " / ".join(str(part) for part in key)


MAX_MISSING_SCORE_RATE = 0.2
MAX_MISSING_PREFECTURE_RATE = 0.1
MAX_MISSING_ADDRESS_RATE = 0.1
MAX_DUPLICATE_RATE = 0.02


def evaluate_quality_gate(metrics: dict, expected_prefectures: Iterable[str]) -> tuple[list[str], list[str]]:
    total = metrics.get("total", 0)
    errors: list[str] = []
    warnings: list[str] = []
    checks = [
        ("Missing score", _rate(metrics.get("missing_score", 0), total), MAX_MISSING_SCORE_RATE),
        ("Missing prefecture", _rate(metrics.get("missing_prefecture", 0), total), MAX_MISSING_PREFECTURE_RATE),
        ("Missing address", _rate(metrics.get("missing_address", 0), total), MAX_MISSING_ADDRESS_RATE),
        ("Duplicate", _rate(len(metrics.get("duplicates", [])), total), MAX_DUPLICATE_RATE),
    ]
    for label, rate, maximum in checks:
        if rate > maximum:
            errors.append(f"{label} rate too high: {rate:.1%}")
    counts = metrics.get("prefecture_counts", {})
    for prefecture in expected_prefectures:
        if counts.get(prefecture, 0) == 0:
            warnings.append(f"No records found for {prefecture}")
    return errors, warnings
