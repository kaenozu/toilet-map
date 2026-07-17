from __future__ import annotations

import argparse
import gzip
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from .normalization import content_hash, first_present, normalize_text, safe_float, safe_int

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS places(
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_place_id TEXT,
    title TEXT NOT NULL,
    address TEXT,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    category TEXT,
    UNIQUE(source, source_place_id)
);
CREATE TABLE IF NOT EXISTS toilets(
    id TEXT PRIMARY KEY,
    place_id TEXT NOT NULL UNIQUE REFERENCES places(id),
    score REAL,
    confidence REAL NOT NULL,
    review_count INTEGER NOT NULL,
    score_status TEXT NOT NULL,
    scoring_version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews(
    id TEXT PRIMARY KEY,
    place_id TEXT NOT NULL REFERENCES places(id),
    text TEXT NOT NULL,
    rating REAL,
    content_hash TEXT NOT NULL,
    UNIQUE(place_id, content_hash)
);
CREATE TABLE IF NOT EXISTS migration_rejections(
    id INTEGER PRIMARY KEY,
    source_index INTEGER,
    reason TEXT,
    payload_json TEXT
);
"""


@dataclass
class MigrationReport:
    input_count: int = 0
    places_upserted: int = 0
    toilets_upserted: int = 0
    reviews_inserted: int = 0
    duplicate_reviews: int = 0
    rejected_count: int = 0
    rejection_reasons: dict[str, int] = field(default_factory=dict)

    def reject(self, reason: str) -> None:
        self.rejected_count += 1
        self.rejection_reasons[reason] = self.rejection_reasons.get(reason, 0) + 1


def stable_id(kind: str, *parts: Any) -> str:
    normalized_parts = [normalize_text(part) for part in parts]
    return str(uuid5(NAMESPACE_URL, ":".join([kind, *normalized_parts])))


def load_rows(path: Path) -> list[dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as file:
        if path.name.endswith((".jsonl", ".jsonl.gz")):
            return [json.loads(line) for line in file if line.strip()]
        value = json.load(file)

    rows = value.get("results", value) if isinstance(value, dict) else value
    if not isinstance(rows, list):
        raise ValueError("input must be a list or contain results")
    return [row for row in rows if isinstance(row, dict)]


def review_items(row: dict[str, Any]) -> list[dict[str, Any]]:
    raw = first_present(row, "reviews", "review_items", "toilet_reviews") or []
    if not isinstance(raw, list):
        return []
    return [
        {"text": item} if isinstance(item, str) else item
        for item in raw
        if isinstance(item, (str, dict))
    ]


def migrate(
    input_path: Path,
    database_path: Path,
    report_path: Path | None = None,
) -> MigrationReport:
    report = MigrationReport()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(database_path)
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(SCHEMA)

    try:
        with db:
            for index, row in enumerate(load_rows(input_path)):
                report.input_count += 1
                _migrate_row(db, index, row, report)
    finally:
        db.close()

    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(asdict(report), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return report


def _migrate_row(
    db: sqlite3.Connection,
    index: int,
    row: dict[str, Any],
    report: MigrationReport,
) -> None:
    title = str(first_present(row, "title", "name") or "").strip()
    latitude = safe_float(first_present(row, "latitude", "lat"), minimum=-90, maximum=90)
    longitude = safe_float(
        first_present(row, "longitude", "lng", "lon"),
        minimum=-180,
        maximum=180,
    )
    if not title or latitude is None or longitude is None:
        reason = "missing_title" if not title else "invalid_coordinates"
        report.reject(reason)
        db.execute(
            "INSERT INTO migration_rejections(source_index, reason, payload_json) VALUES(?, ?, ?)",
            (index, reason, json.dumps(row, ensure_ascii=False)),
        )
        return

    source = str(first_present(row, "source") or "google_maps")
    source_id = first_present(row, "place_id", "data_id", "source_place_id")
    address = first_present(row, "address", "full_address")
    place_id = stable_id(
        "place",
        source,
        source_id or title,
        "" if source_id else address,
        "" if source_id else f"{latitude:.6f}",
        "" if source_id else f"{longitude:.6f}",
    )
    toilet_id = stable_id("toilet", place_id, "default")
    reviews = review_items(row)

    review_count = safe_int(first_present(row, "toilet_reviews_count", "review_count"), minimum=0)
    if review_count is None:
        review_count = len(reviews)
    score = safe_float(first_present(row, "toilet_score", "score"), minimum=0, maximum=100)
    confidence = safe_float(first_present(row, "confidence"), minimum=0, maximum=1)
    if confidence is None:
        confidence = min(1.0, review_count / 10) if review_count else 0.0

    if review_count == 0 or score is None:
        status = "unrated"
        score = None
    elif review_count < 3:
        status = "provisional"
    else:
        status = "rated"

    db.execute(
        """
        INSERT INTO places VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title,
            address=excluded.address,
            latitude=excluded.latitude,
            longitude=excluded.longitude,
            category=excluded.category
        """,
        (
            place_id,
            source,
            str(source_id) if source_id else None,
            title,
            address,
            latitude,
            longitude,
            first_present(row, "category", "type"),
        ),
    )
    db.execute(
        """
        INSERT INTO toilets VALUES(?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            score=excluded.score,
            confidence=excluded.confidence,
            review_count=excluded.review_count,
            score_status=excluded.score_status,
            scoring_version=excluded.scoring_version
        """,
        (
            toilet_id,
            place_id,
            score,
            confidence,
            review_count,
            status,
            str(first_present(row, "scoring_version") or "legacy-v1"),
        ),
    )
    report.places_upserted += 1
    report.toilets_upserted += 1

    for review in reviews:
        text = str(first_present(review, "text", "review", "comment") or "").strip()
        if not text:
            continue
        digest = content_hash(text)
        review_id = stable_id(
            "review",
            place_id,
            first_present(review, "review_id", "id") or digest,
        )
        cursor = db.execute(
            "INSERT OR IGNORE INTO reviews VALUES(?, ?, ?, ?, ?)",
            (
                review_id,
                place_id,
                text,
                safe_float(first_present(review, "rating", "stars"), minimum=0, maximum=5),
                digest,
            ),
        )
        if cursor.rowcount:
            report.reviews_inserted += 1
        else:
            report.duplicate_reviews += 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("database", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    report = migrate(args.input, args.database, args.report)
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    return 0 if report.input_count else 2


if __name__ == "__main__":
    raise SystemExit(main())
