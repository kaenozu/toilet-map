from __future__ import annotations

import gzip
import hashlib
import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from psycopg import Connection

from .db import database


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


def normalized_records(records: Iterable[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    for record in records:
        coordinates = _coordinates(record)
        name = str(_first(record, "name", "title", default="")).strip()
        if not name or coordinates is None:
            continue
        lat, lon = coordinates
        known = {
            "stable_key", "source_id", "place_id", "data_id", "id", "name", "title",
            "address", "prefecture", "category", "latitude", "lat", "longitude", "lng", "lon",
            "toilet_score", "score", "confidence", "review_count", "user_ratings_total", "reviews",
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
            "toilet_score": _first(record, "toilet_score", "score"),
            "confidence": _first(record, "confidence"),
            "review_count": int(_first(record, "review_count", "user_ratings_total", default=0) or 0),
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


def import_legacy(path: Path, *, source: str = "legacy-json") -> tuple[int, int]:
    records, metadata = load_legacy_snapshot(path)
    normalized = list(normalized_records(records))
    if not normalized:
        raise ValueError("snapshot contains no valid places")

    with database() as connection:
        dataset_id = create_dataset(connection, source=source, source_metadata=metadata)
        for item in normalized:
            row = connection.execute(
                """
                INSERT INTO places (
                    dataset_version_id, stable_key, name, address, prefecture, category,
                    location, toilet_score, confidence, review_count, attributes
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                    %s, %s, %s, %s::jsonb
                )
                RETURNING id
                """,
                (
                    dataset_id, item["stable_key"], item["name"], item["address"],
                    item["prefecture"], item["category"], item["longitude"], item["latitude"],
                    item["toilet_score"], item["confidence"], item["review_count"],
                    json.dumps(item["attributes"], ensure_ascii=False),
                ),
            ).fetchone()
            connection.execute(
                """
                INSERT INTO provider_records (dataset_version_id, place_id, provider, external_id, raw_payload)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                """,
                (
                    dataset_id, row["id"], source, item["stable_key"],
                    json.dumps(item["raw_payload"], ensure_ascii=False),
                ),
            )
        connection.execute(
            "UPDATE dataset_versions SET record_count = %s WHERE id = %s",
            (len(normalized), dataset_id),
        )
        connection.commit()
    return dataset_id, len(normalized)
