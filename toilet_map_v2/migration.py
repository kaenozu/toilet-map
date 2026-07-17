from __future__ import annotations

import argparse
import gzip
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .database import connect, initialize
from .identifiers import build_place_id, build_review_id, build_toilet_id
from .normalization import content_hash, first_present, safe_float, safe_int


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
    initialize(database_path)

    with connect(database_path) as db:
        for index, row in enumerate(load_rows(input_path)):
            report.input_count += 1
            _migrate_row(db, index, row, report)

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
    migrated_at = _timestamp(first_present(row, "collected_at", "updated_at", "scraped_at"))

    if not title or latitude is None or longitude is None:
        reason = "missing_title" if not title else "invalid_coordinates"
        report.reject(reason)
        db.execute(
            """
            INSERT INTO migration_rejections(
                source_index, reason, payload_json, rejected_at
            ) VALUES(?, ?, ?, ?)
            """,
            (index, reason, json.dumps(row, ensure_ascii=False), migrated_at),
        )
        return

    source = str(first_present(row, "source") or "google_maps")
    source_place_id = _optional_text(first_present(row, "place_id", "source_place_id"))
    data_id = _optional_text(first_present(row, "data_id"))
    address = _optional_text(first_present(row, "address", "full_address"))
    toilet_type = str(first_present(row, "toilet_type") or "unknown")
    place_id = build_place_id(
        source=source,
        source_place_id=source_place_id,
        data_id=data_id,
        title=title,
        address=address,
        latitude=latitude,
        longitude=longitude,
    )
    toilet_id = build_toilet_id(place_id, toilet_type)
    reviews = review_items(row)

    review_count = safe_int(
        first_present(row, "toilet_reviews_count", "review_count"),
        minimum=0,
    )
    if review_count is None:
        review_count = len(reviews)

    score = safe_float(
        first_present(row, "toilet_score", "score"),
        minimum=0,
        maximum=100,
    )
    confidence = safe_float(first_present(row, "confidence"), minimum=0, maximum=1)
    if confidence is None:
        confidence = min(1.0, review_count / 10) if review_count else 0.0

    if review_count == 0 or score is None:
        score_status = "unrated"
        score = None
    elif review_count < 3:
        score_status = "provisional"
    else:
        score_status = "rated"

    _upsert_place(
        db,
        row=row,
        place_id=place_id,
        source=source,
        source_place_id=source_place_id or data_id,
        title=title,
        address=address,
        latitude=latitude,
        longitude=longitude,
        migrated_at=migrated_at,
    )
    _upsert_toilet(
        db,
        row=row,
        toilet_id=toilet_id,
        place_id=place_id,
        toilet_type=toilet_type,
        score=score,
        confidence=confidence,
        review_count=review_count,
        score_status=score_status,
        migrated_at=migrated_at,
    )
    report.places_upserted += 1
    report.toilets_upserted += 1

    for review in reviews:
        _insert_review(db, place_id, review, migrated_at, report)


def _upsert_place(
    db: sqlite3.Connection,
    *,
    row: dict[str, Any],
    place_id: str,
    source: str,
    source_place_id: str | None,
    title: str,
    address: str | None,
    latitude: float,
    longitude: float,
    migrated_at: str,
) -> None:
    db.execute(
        """
        INSERT INTO places(
            id, source, source_place_id, title, category, address,
            latitude, longitude, external_url, overall_rating,
            overall_review_count, first_seen_at, last_seen_at, is_active
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title,
            category=excluded.category,
            address=excluded.address,
            latitude=excluded.latitude,
            longitude=excluded.longitude,
            external_url=excluded.external_url,
            overall_rating=excluded.overall_rating,
            overall_review_count=excluded.overall_review_count,
            last_seen_at=excluded.last_seen_at,
            is_active=1
        """,
        (
            place_id,
            source,
            source_place_id,
            title,
            first_present(row, "category", "type"),
            address,
            latitude,
            longitude,
            first_present(row, "external_url", "url", "maps_url"),
            safe_float(first_present(row, "overall_rating", "rating"), minimum=0, maximum=5),
            safe_int(first_present(row, "overall_review_count", "reviews_count"), minimum=0),
            migrated_at,
            migrated_at,
        ),
    )


def _upsert_toilet(
    db: sqlite3.Connection,
    *,
    row: dict[str, Any],
    toilet_id: str,
    place_id: str,
    toilet_type: str,
    score: float | None,
    confidence: float,
    review_count: int,
    score_status: str,
    migrated_at: str,
) -> None:
    db.execute(
        """
        INSERT INTO toilets(
            id, place_id, toilet_type, score, confidence, review_count,
            score_status, scoring_version, scored_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            score=excluded.score,
            confidence=excluded.confidence,
            review_count=excluded.review_count,
            score_status=excluded.score_status,
            scoring_version=excluded.scoring_version,
            scored_at=excluded.scored_at
        """,
        (
            toilet_id,
            place_id,
            toilet_type,
            score,
            confidence,
            review_count,
            score_status,
            str(first_present(row, "scoring_version") or "legacy-v1"),
            migrated_at if score is not None else None,
        ),
    )


def _insert_review(
    db: sqlite3.Connection,
    place_id: str,
    review: dict[str, Any],
    migrated_at: str,
    report: MigrationReport,
) -> None:
    text = str(first_present(review, "text", "review", "comment") or "").strip()
    if not text:
        return

    digest = content_hash(text)
    source_review_id = _optional_text(first_present(review, "review_id", "id"))
    review_id = build_review_id(
        place_id,
        source_review_id=source_review_id,
        content_hash=digest,
    )
    cursor = db.execute(
        """
        INSERT OR IGNORE INTO reviews(
            id, place_id, source_review_id, text, rating, posted_at,
            collected_at, content_hash, is_toilet_related
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            review_id,
            place_id,
            source_review_id,
            text,
            safe_float(first_present(review, "rating", "stars"), minimum=0, maximum=5),
            _optional_text(first_present(review, "posted_at", "date", "published_at")),
            _timestamp(first_present(review, "collected_at") or migrated_at),
            digest,
            1,
        ),
    )
    if cursor.rowcount:
        report.reviews_inserted += 1
    else:
        report.duplicate_reviews += 1


def _optional_text(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _timestamp(value: Any) -> str:
    if value is not None and str(value).strip():
        return str(value)
    return datetime.now(UTC).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate legacy toilet data into the v2 database")
    parser.add_argument("input", type=Path)
    parser.add_argument("database", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    report = migrate(args.input, args.database, args.report)
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    return 0 if report.input_count else 2


if __name__ == "__main__":
    raise SystemExit(main())
