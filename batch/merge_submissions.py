"""
batch/merge_submissions.py
Merge user submissions (JSONL) into canonical toilets JSON.

Steps:
1. Read data/user_submissions.jsonl
2. Validate each submission (name required, lat/lng valid)
3. De-duplicate against existing data/toilets.json.gz
4. Append new unique submissions
5. Re-save data/toilets.json.gz
6. Run to_sqlite.py --incremental
7. Archive processed submissions as .processed

Related: ui/submission_form.py, batch/to_sqlite.py, batch/db_utils.py
"""
import json
import gzip
import os
import sys
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from utils import extract_prefecture, logger  # noqa: E402
from db_utils import load_json  # noqa: E402

SUBMISSIONS_PATH = os.path.join(SCRIPT_DIR, "..", "data", "user_submissions.jsonl")
CANONICAL_PATH = os.path.join(SCRIPT_DIR, "..", "data", "toilets.json.gz")
PROCESSED_SUFFIX = ".processed"
TO_SQLITE_PATH = os.path.join(SCRIPT_DIR, "to_sqlite.py")


def read_submissions(path: str) -> list[dict]:
    """Read JSONL file, return list of submission dicts."""
    if not os.path.exists(path):
        logger.info(f"No submissions file found: {path}")
        return []
    submissions = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                submissions.append(json.loads(line))
            except json.JSONDecodeError as e:
                logger.warning(f"Skipping invalid JSON line: {e}")
    return submissions


def validate_submission(sub: dict) -> bool:
    """Validate a single submission has name and valid coordinates."""
    name = sub.get("title", "").strip()
    if not name:
        return False
    lat = sub.get("lat")
    lng = sub.get("lng")
    if lat is None or lng is None:
        return False
    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except (TypeError, ValueError):
        return False
    if not (-90 <= lat_f <= 90 and -180 <= lng_f <= 180):
        return False
    return True


def submission_to_canonical(sub: dict) -> dict:
    """Convert a user submission dict to canonical toilet dict with defaults."""
    return {
        "title": sub.get("title", "").strip(),
        "category": sub.get("category", "other"),
        "address": sub.get("address", "").strip(),
        "lat": float(sub["lat"]),
        "lng": float(sub["lng"]),
        "phone": "",
        "rating": 0.0,
        "review_count": 0,
        "link": "",
        "is_public_toilet": sub.get("is_public_toilet", False),
        "toilet_score": 50.0,
        "confidence": 0.0,
        "toilet_review_count": 0,
        "top_keywords": [],
        "sample_reviews": [],
        "prefecture": extract_prefecture(sub.get("address", "") or ""),
    }


def _dedup_key(t: dict) -> str:
    """Unique key for de-duplication: title + lat + lng."""
    return f"{t.get('title', '')}|{t.get('lat', 0):.6f}|{t.get('lng', 0):.6f}"


def save_json_gz(data: dict, path: str) -> None:
    """Save dictionary as gzipped JSON."""
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main() -> None:
    logger.info("=== Merge Submissions ===")

    submissions = read_submissions(SUBMISSIONS_PATH)
    if not submissions:
        logger.info("No submissions to process.")
        return

    valid = [s for s in submissions if validate_submission(s)]
    invalid_count = len(submissions) - len(valid)
    if invalid_count:
        logger.warning(
            f"Skipped {invalid_count} invalid submissions "
            "(missing name or invalid coords)"
        )

    if not valid:
        logger.info("No valid submissions to merge.")
        shutil.move(SUBMISSIONS_PATH, SUBMISSIONS_PATH + PROCESSED_SUFFIX)
        return

    existing = load_json(CANONICAL_PATH)
    existing_toilets = existing.get("toilets", [])
    metadata = existing.get("metadata", {})

    existing_keys = {_dedup_key(t) for t in existing_toilets}

    new_toilets = []
    for sub in valid:
        canon = submission_to_canonical(sub)
        key = _dedup_key(canon)
        if key not in existing_keys:
            existing_keys.add(key)
            new_toilets.append(canon)

    if not new_toilets:
        logger.info("No new unique submissions to add.")
        shutil.move(SUBMISSIONS_PATH, SUBMISSIONS_PATH + PROCESSED_SUFFIX)
        return

    all_toilets = existing_toilets + new_toilets
    metadata["total"] = len(all_toilets)
    metadata["scored"] = sum(
        1 for t in all_toilets if t.get("confidence", 0) > 0
    )
    metadata["public_toilets"] = sum(
        1 for t in all_toilets if t.get("is_public_toilet", False)
    )

    save_json_gz({"metadata": metadata, "toilets": all_toilets}, CANONICAL_PATH)
    logger.info(
        f"Added {len(new_toilets)} new submissions, "
        f"total {len(all_toilets)} toilets"
    )

    ret = os.system(
        f'python "{TO_SQLITE_PATH}" "{CANONICAL_PATH}" --incremental'
    )
    if ret != 0:
        logger.error("to_sqlite.py failed, SQLite may be out of sync")

    shutil.move(SUBMISSIONS_PATH, SUBMISSIONS_PATH + PROCESSED_SUFFIX)
    logger.info(
        f"Archived submissions to {SUBMISSIONS_PATH + PROCESSED_SUFFIX}"
    )
    logger.info("=== Merge complete ===")


if __name__ == "__main__":
    main()
