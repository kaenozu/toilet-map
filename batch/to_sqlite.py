"""
batch/to_sqlite.py
JSON データを SQLite データベースに変換し、検索と読み込みを高速化する。
--incremental でマージモード (既存データ保持)

関連ファイル:
  - batch/db_utils.py (共通ユーティリティ)
  - data/toilets.db (出力 DB)
"""
import sqlite3
import json
import gzip
import math
import os
import sys
from utils import logger

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_JSON_PATH = os.path.join(SCRIPT_DIR, "..", "data", "toilets.json.gz")

from db_utils import (  # noqa: E402
    DB_PATH, ensure_schema,
    dedupe_duplicate_toilets, fix_null_prefectures, update_metadata_from_db,
    load_json, upsert_metadata, upsert_toilets,
)


REQUIRED_TOILET_FIELDS = {
    "title",
    "category",
    "address",
    "lat",
    "lng",
    "rating",
    "review_count",
    "is_public_toilet",
    "toilet_score",
    "confidence",
    "toilet_review_count",
    "prefecture",
}
DEFAULT_TOILET_FIELDS = {
    "phone": "",
    "link": "",
    "sample_reviews": [],
    "top_keywords": [],
}


def _coerce_float(value: object, field_name: str, index: int) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"toilets[{index}] has invalid {field_name}: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"toilets[{index}] has invalid {field_name}: {value!r}")
    return number


def _coerce_int(value: object, field_name: str, index: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"toilets[{index}] has invalid {field_name}: {value!r}")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"toilets[{index}] has invalid {field_name}: {value!r}") from exc


def _validate_toilet_record(toilet: dict, index: int) -> dict:
    if not isinstance(toilet, dict):
        raise ValueError(f"toilets[{index}] must be an object")

    missing_fields = sorted(field for field in REQUIRED_TOILET_FIELDS if field not in toilet)
    if missing_fields:
        raise ValueError(f"toilets[{index}] is missing required fields: {', '.join(missing_fields)}")

    normalized = dict(toilet)
    for field, default in DEFAULT_TOILET_FIELDS.items():
        if field not in normalized or normalized[field] is None:
            normalized[field] = default.copy() if isinstance(default, list) else default

    normalized["title"] = str(normalized["title"]).strip()
    normalized["category"] = str(normalized["category"]).strip()
    normalized["address"] = str(normalized["address"]).strip()
    normalized["prefecture"] = str(normalized["prefecture"]).strip()
    normalized["phone"] = str(normalized["phone"]).strip()
    normalized["link"] = str(normalized["link"]).strip()
    normalized["lat"] = _coerce_float(normalized["lat"], "lat", index)
    normalized["lng"] = _coerce_float(normalized["lng"], "lng", index)
    normalized["rating"] = _coerce_float(normalized["rating"], "rating", index)
    normalized["review_count"] = _coerce_int(normalized["review_count"], "review_count", index)
    normalized["toilet_score"] = _coerce_float(normalized["toilet_score"], "toilet_score", index)
    normalized["confidence"] = _coerce_float(normalized["confidence"], "confidence", index)
    normalized["toilet_review_count"] = _coerce_int(normalized["toilet_review_count"], "toilet_review_count", index)

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


def _convert_core(
    json_path: str,
    db_path: str,
    incremental: bool = False,
) -> int:
    """JSON → SQLite 変換のコア処理。総件数を返す。"""
    from utils import logger

    data = load_json(json_path)
    metadata = data.get("metadata", {})
    toilets = _validate_toilet_records(data.get("toilets", []))

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    if not incremental:
        cur.execute("DROP TABLE IF EXISTS toilets")
        cur.execute("DROP TABLE IF EXISTS metadata")

    ensure_schema(cur)
    upsert_metadata(cur, metadata)
    upsert_toilets(cur, toilets)
    deduped = dedupe_duplicate_toilets(cur)

    fixed = fix_null_prefectures(conn)
    logger.info(f"Upserted {len(toilets)} toilets, deduped: {deduped}, prefecture fixed: {fixed}")

    update_metadata_from_db(conn)
    conn.commit()

    total = cur.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
    conn.close()
    return total


def json_to_sqlite(json_path: str, incremental: bool = False) -> None:
    from utils import logger

    if not incremental and os.path.exists(DB_PATH):
        import shutil
        backup_path = f"{DB_PATH}.bak"
        shutil.copy(DB_PATH, backup_path)
        logger.info(f"Existing database backed up to {backup_path}")

    logger.info(f"Converting {json_path} to SQLite (incremental={incremental})...")
    total = _convert_core(json_path, DB_PATH, incremental)
    logger.info(f"SQLite conversion complete: {DB_PATH} ({total} toilets)")


def merge(json_path: str, db_path: str = DB_PATH) -> None:
    from utils import logger
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


if __name__ == "__main__":
    incremental = "--incremental" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--incremental"]
    path = args[0] if args else DEFAULT_JSON_PATH
    if incremental:
        merge(path)
    else:
        json_to_sqlite(path)
