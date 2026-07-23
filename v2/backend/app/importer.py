from __future__ import annotations

import gzip
import hashlib
import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from psycopg import Connection

from .db import database
from .entities import upsert_legacy_entity
from .scoring import (
    DIMENSION_SCORING_VERSION,
    SCORING_VERSION,
    ScoreDimension,
    score_review_dimensions,
    score_reviews,
)


def _records(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("toilets", "places", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise ValueError("unsupported legacy snapshot format")


def load_legacy_snapshot(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
    return _records(payload), metadata if isinstance(metadata, dict) else {}


def _first(record: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = record.get(key)
        if value is not None and value != "":
            return value
    return default


def _stable_key(record: dict[str, Any]) -> str:
    explicit = _first(record, "stable_key", "source_id", "place_id", "data_id", "id")
    if explicit is not None:
        return str(explicit)
    canonical = "|".join(
        str(_first(record, key, default=""))
        for key in ("name", "address", "latitude", "longitude")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def _coordinates(record: dict[str, Any]) -> tuple[float, float] | None:
    latitude = _first(record, "latitude", "lat")
    longitude = _first(record, "longitude", "lng", "lon")
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


def _reviews(record: dict[str, Any]) -> list[dict[str, Any]]:
    value = record.get("reviews") or record.get("sample_reviews") or []
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for index, review in enumerate(value):
        if isinstance(review, str):
            body = review.strip()
            payload = {"body": body}
        elif isinstance(review, dict):
            body = str(review.get("text") or review.get("body") or review.get("review") or "").strip()
            payload = review
        else:
            continue
        if not body:
            continue
        result.append(
            {
                "external_id": str(payload.get("review_id") or payload.get("id") or index),
                "body": body,
                "rating": payload.get("rating") or payload.get("stars"),
            }
        )
    return result


def normalized_records(records: Iterable[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    for record in records:
        coordinates = _coordinates(record)
        name = str(_first(record, "name", "title", default="")).strip()
        if not name or coordinates is None:
            continue
        lat, lon = coordinates
        reviews = _reviews(record)
        review_bodies = [review["body"] for review in reviews]
        score_result = score_reviews(review_bodies)
        dimension_scores = score_review_dimensions(review_bodies)
        imported_score = _first(record, "toilet_score", "score")
        imported_confidence = _first(record, "confidence")
        known = {
            "stable_key", "source_id", "place_id", "data_id", "id", "name", "title",
            "address", "prefecture", "category", "latitude", "lat", "longitude", "lng", "lon",
            "toilet_score", "score", "confidence", "review_count", "user_ratings_total", "reviews",
            "sample_reviews",
        }
        attributes = {key: value for key, value in record.items() if key not in known}
        yield {
            "stable_key": _stable_key(record),
            "name": name,
            "address": str(_first(record, "address", default="")),
            "prefecture": str(_first(record, "prefecture", default="")),
            "category": str(_first(record, "category", default="")),
            "latitude": lat,
            "longitude": lon,
            "toilet_score": imported_score if imported_score is not None else score_result.score,
            "confidence": imported_confidence if imported_confidence is not None else score_result.confidence,
            "review_count": int(_first(record, "review_count", "user_ratings_total", default=len(reviews)) or 0),
            "reviews": reviews,
            "score_explanation": {
                **score_result.explanation,
                "dimensions": {
                    dimension.value: {
                        "score": result.score,
                        "confidence": result.confidence,
                        "evidence_count": result.evidence_count,
                        "positive_matches": result.positive_matches,
                        "negative_matches": result.negative_matches,
                    }
                    for dimension, result in dimension_scores.items()
                },
            },
            "dimension_scores": dimension_scores,
            "attributes": attributes,
            "raw_payload": record,
        }


def create_dataset(connection: Connection, *, source: str, source_metadata: dict[str, Any]) -> int:
    row = connection.execute(
        """
        INSERT INTO dataset_versions (status, source, source_metadata)
        VALUES ('staging', %s, %s::jsonb)
        RETURNING id
        """,
        (source, json.dumps(source_metadata, ensure_ascii=False)),
    ).fetchone()
    if row is None:
        raise RuntimeError("failed to create dataset")
    return int(row["id"])


def _store_dimension_scores(
    connection: Connection,
    *,
    facility_id: int,
    source_record_id: int,
    dimension_scores: dict[ScoreDimension, Any],
) -> None:
    for dimension, result in dimension_scores.items():
        if result.score is None:
            continue
        connection.execute(
            """
            INSERT INTO facility_scores (
              facility_id, dimension, model_version, score, confidence, evidence_count, last_observed_at
            ) VALUES (%s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (facility_id, dimension, model_version) DO UPDATE SET
              score = EXCLUDED.score,
              confidence = EXCLUDED.confidence,
              evidence_count = EXCLUDED.evidence_count,
              last_observed_at = EXCLUDED.last_observed_at,
              calculated_at = now()
            """,
            (
                facility_id,
                dimension.value,
                DIMENSION_SCORING_VERSION,
                result.score,
                result.confidence,
                result.evidence_count,
            ),
        )
        connection.execute(
            """
            INSERT INTO score_evidence (
              facility_id, source_record_id, dimension, model_version, value,
              reliability_weight, extraction_method, observed_at
            ) VALUES (%s, %s, %s, %s, %s, %s, 'keyword', now())
            ON CONFLICT (source_record_id, dimension, model_version) DO UPDATE SET
              facility_id = EXCLUDED.facility_id,
              value = EXCLUDED.value,
              reliability_weight = EXCLUDED.reliability_weight,
              observed_at = EXCLUDED.observed_at
            """,
            (
                facility_id,
                source_record_id,
                dimension.value,
                DIMENSION_SCORING_VERSION,
                result.score,
                result.confidence,
            ),
        )


def import_legacy(path: Path, *, source: str = "legacy-json") -> tuple[int, int]:
    records, metadata = load_legacy_snapshot(path)
    normalized = list(normalized_records(records))
    if not normalized:
        raise ValueError("snapshot contains no valid places")

    with database() as connection:
        dataset_id = create_dataset(connection, source=source, source_metadata=metadata)
        for item in normalized:
            entity_ids = upsert_legacy_entity(
                connection,
                dataset_id=dataset_id,
                provider=source,
                item=item,
            )
            row = connection.execute(
                """
                INSERT INTO places (
                    dataset_version_id, stable_key, name, address, prefecture, category,
                    location, toilet_score, confidence, review_count, attributes,
                    facility_id, source_record_id
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                    %s, %s, %s, %s::jsonb, %s, %s
                )
                RETURNING id
                """,
                (
                    dataset_id, item["stable_key"], item["name"], item["address"],
                    item["prefecture"], item["category"], item["longitude"], item["latitude"],
                    item["toilet_score"], item["confidence"], item["review_count"],
                    json.dumps(item["attributes"], ensure_ascii=False),
                    entity_ids.facility_id,
                    entity_ids.source_record_id,
                ),
            ).fetchone()
            if row is None:
                raise RuntimeError("failed to insert place")
            place_id = int(row["id"])
            connection.execute(
                """
                INSERT INTO provider_records (dataset_version_id, place_id, provider, external_id, raw_payload)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                """,
                (
                    dataset_id, place_id, source, item["stable_key"],
                    json.dumps(item["raw_payload"], ensure_ascii=False),
                ),
            )
            for review in item["reviews"]:
                connection.execute(
                    """
                    INSERT INTO reviews (place_id, provider, external_id, body, rating)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (place_id, provider, external_id) DO NOTHING
                    """,
                    (place_id, source, review["external_id"], review["body"], review["rating"]),
                )
            connection.execute(
                """
                INSERT INTO score_history (place_id, model_version, score, confidence, explanation)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                """,
                (
                    place_id, SCORING_VERSION, item["toilet_score"], item["confidence"],
                    json.dumps(item["score_explanation"], ensure_ascii=False),
                ),
            )
            _store_dimension_scores(
                connection,
                facility_id=entity_ids.facility_id,
                source_record_id=entity_ids.source_record_id,
                dimension_scores=item["dimension_scores"],
            )
        connection.execute(
            "UPDATE dataset_versions SET record_count = %s WHERE id = %s",
            (len(normalized), dataset_id),
        )
        connection.commit()
    return dataset_id, len(normalized)
