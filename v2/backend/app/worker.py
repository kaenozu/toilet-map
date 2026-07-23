"""Dataset validation and leased background job execution."""

from __future__ import annotations

import json
import os
import time
from typing import Any

from .db import database
from .ingestion import ingest_provider, ingestion_stats
from .job_queue import claim_job, finish_job
from .osm_provider import OsmOverpassProvider
from .providers import FetchRequest, OSM_REGIONS
from .resolution import generate_match_candidates


def validate_dataset(dataset_version_id: int) -> None:
    with database() as connection:
        result = connection.execute(
            """
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE btrim(name) = '') AS missing_name,
                   count(*) FILTER (WHERE NOT ST_IsValid(location::geometry)) AS invalid_location,
                   count(*) - count(DISTINCT stable_key) AS duplicate_keys,
                   count(*) FILTER (
                     WHERE toilet_score IS NOT NULL AND toilet_score NOT BETWEEN 0 AND 100
                   ) AS invalid_score,
                   count(*) FILTER (WHERE facility_id IS NULL) AS missing_facility,
                   count(*) FILTER (WHERE source_record_id IS NULL) AS missing_source_record
              FROM places WHERE dataset_version_id = %s
            """,
            (dataset_version_id,),
        ).fetchone()
        if result is None:
            raise RuntimeError("validation query returned no result")
        unresolved = connection.execute(
            """
            SELECT count(*) AS total
              FROM places place
              LEFT JOIN source_records source ON source.id = place.source_record_id
              LEFT JOIN facility_source_links link
                ON link.source_record_id = place.source_record_id
               AND link.facility_id = place.facility_id
               AND link.status = 'matched'
             WHERE place.dataset_version_id = %s
               AND (
                 source.id IS NULL
                 OR source.record_status IN ('stale', 'rejected')
                 OR link.id IS NULL
               )
            """,
            (dataset_version_id,),
        ).fetchone()
        unresolved_count = int(unresolved["total"] if unresolved else 0)
        report = {**dict(result), "unresolved_source_records": unresolved_count}
        valid = all(
            (
                result["total"] > 0,
                result["missing_name"] == 0,
                result["invalid_location"] == 0,
                result["duplicate_keys"] == 0,
                result["invalid_score"] == 0,
                result["missing_facility"] == 0,
                result["missing_source_record"] == 0,
                unresolved_count == 0,
            )
        )
        connection.execute(
            """
            UPDATE dataset_versions
               SET status = %s, record_count = %s, validation_report = %s::jsonb,
                   validated_at = CASE WHEN %s THEN now() ELSE NULL END
             WHERE id = %s AND status IN ('staging', 'validating', 'validated', 'failed')
            """,
            (
                "validated" if valid else "failed",
                result["total"],
                json.dumps(report, ensure_ascii=False),
                valid,
                dataset_version_id,
            ),
        )
        connection.commit()
        if not valid:
            raise ValueError(f"dataset validation failed: {report}")


def publish_dataset(dataset_version_id: int) -> None:
    with database() as connection:
        connection.execute("SELECT publish_dataset(%s)", (dataset_version_id,))
        connection.commit()


def detect_stale_source_records() -> int:
    with database() as connection:
        row = connection.execute(
            """
            WITH changed AS (
              UPDATE source_records
                 SET record_status = 'stale', verification_status = 'stale'
               WHERE record_status = 'active'
                 AND expires_at IS NOT NULL
                 AND expires_at <= now()
               RETURNING id
            )
            SELECT count(*) AS total FROM changed
            """
        ).fetchone()
        connection.commit()
    return int(row["total"] if row else 0)


def resolve_source_records() -> int:
    """Reuse only an earlier exact provider/external-ID decision."""
    with database() as connection:
        row = connection.execute(
            """
            WITH candidates AS (
              SELECT DISTINCT ON (pending.source_record_id)
                     pending.source_record_id,
                     previous.facility_id
                FROM facility_source_links pending
                JOIN source_records current_record ON current_record.id = pending.source_record_id
                JOIN source_records previous_record
                  ON previous_record.provider = current_record.provider
                 AND previous_record.external_id = current_record.external_id
                 AND previous_record.id <> current_record.id
                JOIN facility_source_links previous
                  ON previous.source_record_id = previous_record.id
                 AND previous.status = 'matched'
               WHERE pending.status = 'pending'
               ORDER BY pending.source_record_id, previous_record.fetched_at DESC, previous_record.id DESC
            ), changed AS (
              UPDATE facility_source_links link
                 SET facility_id = candidates.facility_id,
                     status = 'matched',
                     match_method = 'provider_external_id',
                     match_score = 1.0,
                     decision_reason = 'Matched to a previously resolved provider external ID',
                     decided_at = now(),
                     decided_by = 'system'
                FROM candidates
               WHERE link.source_record_id = candidates.source_record_id
              RETURNING link.id
            )
            SELECT count(*) AS total FROM changed
            """
        ).fetchone()
        connection.commit()
    return int(row["total"] if row else 0)


def ingest_osm_region(region_key: str) -> dict[str, int]:
    try:
        region = OSM_REGIONS[region_key]
    except KeyError as exc:
        raise ValueError(f"unknown OSM region: {region_key}") from exc
    provider = OsmOverpassProvider(endpoint=os.environ.get("OVERPASS_URL", "https://overpass-api.de/api/interpreter"))
    with database() as connection:
        result = ingest_provider(
            connection,
            provider,
            FetchRequest(prefecture=region.prefecture, city=region.city, bbox=region.bbox),
        )
        connection.commit()
    return ingestion_stats(result)


def execute_job(job: dict[str, Any]) -> dict[str, Any]:
    payload = job["payload"]
    dataset_id = int(payload.get("dataset_version_id", 0))
    if job["kind"] == "validate_dataset":
        validate_dataset(dataset_id)
        return {"dataset_version_id": dataset_id, "validated": True}
    if job["kind"] == "publish_dataset":
        publish_dataset(dataset_id)
        return {"dataset_version_id": dataset_id, "published": True}
    if job["kind"] == "detect_stale_source_records":
        return {"expired": detect_stale_source_records()}
    if job["kind"] == "resolve_source_records":
        return {"resolved": resolve_source_records()}
    if job["kind"] == "generate_match_candidates":
        with database() as connection:
            total = generate_match_candidates(
                connection,
                dataset_version_id=payload.get("dataset_version_id"),
                source_record_id=payload.get("source_record_id"),
            )
            connection.commit()
        return {"generated": total}
    if job["kind"] == "ingest_osm":
        return ingest_osm_region(str(payload["region"]))
    raise ValueError(f"unsupported job kind: {job['kind']}")


def run_once() -> bool:
    with database() as connection:
        job = claim_job(connection)
        connection.commit()
    if not job:
        return False
    try:
        stats = execute_job(job)
    except Exception as exc:
        with database() as connection:
            finish_job(connection, job=job, error=exc)
            connection.commit()
    else:
        with database() as connection:
            finish_job(connection, job=job, stats=stats)
            connection.commit()
    return True


def run_forever() -> None:
    while True:
        if not run_once():
            time.sleep(2)


if __name__ == "__main__":
    run_forever()
