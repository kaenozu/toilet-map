# mypy: disable-error-code="no-redef"
"""Convert canonical JSON into SQLite with validation and schema migration."""

from __future__ import annotations

import math
import os
import shutil
import sqlite3
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_JSON_PATH = os.path.join(SCRIPT_DIR, "..", "data", "toilets.json.gz")

try:
    from .db_utils import (
        DB_PATH,
        dedupe_duplicate_toilets,
        ensure_schema,
        fix_null_prefectures,
        load_json,
        update_metadata_from_db,
        upsert_metadata,
        upsert_toilets,
    )
    from .identity import build_source_id
    from .utils import logger
except ImportError:
    from db_utils import (
        DB_PATH,
        dedupe_duplicate_toilets,
        ensure_schema,
        fix_null_prefectures,
        load_json,
        update_metadata_from_db,
        upsert_metadata,
        upsert_toilets,
    )
    from identity import build_source_id
    from utils import logger

REQUIRED_TOILET_FIELDS = {
    "title", "category", "address", "lat", "lng", "rating", "review_count",
    "is_public_toilet", "toilet_score", "confidence", "toilet_review_count", "prefecture",
}
DEFAULT_TOILET_FIELDS = {
    "source_id": "",
    "phone": "",
    "link": "",
    "sample_reviews": [],
    "top_keywords": [],
}


def _coerce_float(value: object, field_name: str, index: int) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"toilets[{index}] has invalid {field_name}: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"toilets[{index}] has invalid {field_name}: {value!r}")
    return number


def _coerce_int(value: object, field_name: str, index: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"toilets[{index}] has invalid {field_name}: {value!r}")
    try:
        return int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"toilets[{index}] has invalid {field_name}: {value!r}") from exc


def _validate_toilet_record(toilet: dict, index: int) -> dict:
    if not isinstance(toilet, dict):
        raise ValueError(f"toilets[{index}] must be an object")
    missing = sorted(field for field in REQUIRED_TOILET_FIELDS if field not in toilet)
    if missing:
        raise ValueError(f"toilets[{index}] is missing required fields: {', '.join(missing)}")

    has_canonical_identity_fields = any(field in toilet for field in ("source_id", "phone", "link"))
    normalized = dict(toilet)
    for field, default in DEFAULT_TOILET_FIELDS.items():
        if field not in normalized or normalized[field] is None:
            normalized[field] = default.copy() if isinstance(default, list) else default

    for field in ("title", "category", "address", "prefecture", "phone", "link"):
        normalized[field] = str(normalized[field]).strip()
    normalized["lat"] = _coerce_float(normalized["lat"], "lat", index)
    normalized["lng"] = _coerce_float(normalized["lng"], "lng", index)
    normalized["rating"] = _coerce_float(normalized["rating"], "rating", index)
    normalized["review_count"] = _coerce_int(normalized["review_count"], "review_count", index)
    normalized["toilet_score"] = _coerce_float(normalized["toilet_score"], "toilet_score", index)
    normalized["confidence"] = _coerce_float(normalized["confidence"], "confidence", index)
    normalized["toilet_review_count"] = _coerce_int(
        normalized["toilet_review_count"], "toilet_review_count", index
    )
    existing_source_id = str(normalized.get("source_id") or "").strip()
    if existing_source_id:
        normalized["source_id"] = existing_source_id
    elif has_canonical_identity_fields:
        normalized["source_id"] = build_source_id(normalized)
    else:
        normalized["source_id"] = f"legacy_coords:{normalized['lat']:.6f},{normalized['lng']:.6f}"

    if not -90 <= normalized["lat"] <= 90 or not -180 <= normalized["lng"] <= 180:
        raise ValueError(f"toilets[{index}] has invalid coordinates")
    if not 0.0 <= normalized["confidence"] <= 1.0:
        raise ValueError(f"toilets[{index}] has invalid confidence: {normalized['confidence']!r}")
    if not 0 <= normalized["toilet_score"] <= 100:
        raise ValueError(f"toilets[{index}] has invalid toilet_score: {normalized['toilet_score']!r}")
    if normalized["review_count"] < 0 or normalized["toilet_review_count"] < 0:
        raise ValueError(f"toilets[{index}] has invalid count fields")
    if not isinstance(normalized["sample_reviews"], list):
        raise ValueError(f"toilets[{index}] has invalid sample_reviews: expected list")
    if not isinstance(normalized["top_keywords"], list):
        raise ValueError(f"toilets[{index}] has invalid top_keywords: expected list")
    return normalized


def _validate_toilet_records(toilets: list[dict]) -> list[dict]:
    return [_validate_toilet_record(toilet, index) for index, toilet in enumerate(toilets)]


def _convert_core(json_path: str, db_path: str, incremental: bool = False) -> int:
    data = load_json(json_path)
    metadata = data.get("metadata", {})
    toilets = _validate_toilet_records(data.get("toilets", []))

    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        if not incremental:
            cur.execute("DROP TABLE IF EXISTS toilets")
            cur.execute("DROP TABLE IF EXISTS metadata")
        ensure_schema(cur)
        upsert_metadata(cur, metadata)
        upsert_toilets(cur, toilets)
        deduped = dedupe_duplicate_toilets(cur)
        fixed = fix_null_prefectures(conn)
        update_metadata_from_db(conn)
        conn.commit()
        total = cur.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
        logger.info(f"Upserted {len(toilets)} toilets, deduped IDs: {deduped}, prefecture fixed: {fixed}")
        return total
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def json_to_sqlite(json_path: str, incremental: bool = False, db_path: str | None = None) -> None:
    db_path = db_path or DB_PATH
    if not incremental and os.path.exists(db_path):
        backup_path = f"{db_path}.bak"
        shutil.copy(db_path, backup_path)
        logger.info(f"Existing database backed up to {backup_path}")
    logger.info(f"Converting {json_path} to SQLite (incremental={incremental})...")
    total = _convert_core(json_path, db_path, incremental)
    logger.info(f"SQLite conversion complete: {db_path} ({total} toilets)")


def merge(json_path: str, db_path: str | None = None) -> None:
    db_path = db_path or DB_PATH
    logger.info(f"Merging {json_path} into SQLite...")
    total = _convert_core(json_path, db_path, incremental=True)
    conn = sqlite3.connect(db_path)
    try:
        null_pref = conn.execute(
            "SELECT COUNT(*) FROM toilets WHERE prefecture IS NULL OR prefecture = ''"
        ).fetchone()[0]
    finally:
        conn.close()
    logger.info(f"Done: {total} total toilets, {null_pref} remaining NULL prefecture")


def _parse_cli(argv: list[str]) -> tuple[str, bool, str]:
    incremental = "--incremental" in argv
    db_path = DB_PATH
    positional: list[str] = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--incremental":
            index += 1
            continue
        if arg == "--db-path" and index + 1 < len(argv):
            db_path = argv[index + 1]
            index += 2
            continue
        positional.append(arg)
        index += 1
    return positional[0] if positional else DEFAULT_JSON_PATH, incremental, db_path


if __name__ == "__main__":
    path, incremental_mode, target_db = _parse_cli(sys.argv[1:])
    if incremental_mode:
        merge(path, target_db)
    else:
        json_to_sqlite(path, db_path=target_db)
