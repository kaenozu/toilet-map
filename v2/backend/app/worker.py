from __future__ import annotations

import json
import time
from typing import Any

from .db import database


def claim_job(connection) -> dict[str, Any] | None:
    row = connection.execute(
        """
        WITH candidate AS (
          SELECT id FROM jobs
           WHERE status = 'queued' AND available_at <= now() AND attempts < max_attempts
           ORDER BY available_at, id
           FOR UPDATE SKIP LOCKED
           LIMIT 1
        )
        UPDATE jobs j
           SET status = 'running', started_at = now(), attempts = attempts + 1,
               error_code = NULL, error_message = NULL
          FROM candidate
         WHERE j.id = candidate.id
        RETURNING j.*
        """
    ).fetchone()
    connection.commit()
    return row


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
              FROM source_records sr
              LEFT JOIN facility_source_links link ON link.source_record_id = sr.id
             WHERE sr.dataset_version_id = %s
               AND (link.id IS NULL OR link.status <> 'matched')
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
             WHERE id = %s AND status IN ('staging', 'validating', 'failed')
            """,
            (
                "validated" if valid else "failed",
                result["total"],
                json.dumps(report),
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
    """Reuse a previous exact provider/external-id decision for a new observation."""
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


def execute_job(job: dict[str, Any]) -> None:
    payload = job["payload"]
    dataset_id = int(payload.get("dataset_version_id", 0))
    if job["kind"] == "validate_dataset":
        validate_dataset(dataset_id)
    elif job["kind"] == "publish_dataset":
        publish_dataset(dataset_id)
    elif job["kind"] == "detect_stale_source_records":
        detect_stale_source_records()
    elif job["kind"] == "resolve_source_records":
        resolve_source_records()
    else:
        raise ValueError(f"unsupported job kind: {job['kind']}")


def finish_job(job: dict[str, Any], error: Exception | None = None) -> None:
    with database() as connection:
        if error is None:
            connection.execute(
                "UPDATE jobs SET status = 'succeeded', finished_at = now() WHERE id = %s",
                (job["id"],),
            )
        elif job["attempts"] < job["max_attempts"]:
            delay_seconds = min(300, 2 ** int(job["attempts"]))
            connection.execute(
                """
                UPDATE jobs SET status = 'queued', available_at = now() + make_interval(secs => %s),
                       error_code = %s, error_message = %s
                 WHERE id = %s
                """,
                (delay_seconds, error.__class__.__name__, str(error)[:2000], job["id"]),
            )
        else:
            connection.execute(
                """
                UPDATE jobs SET status = 'failed', finished_at = now(),
                       error_code = %s, error_message = %s
                 WHERE id = %s
                """,
                (error.__class__.__name__, str(error)[:2000], job["id"]),
            )
        connection.commit()


def run_once() -> bool:
    with database() as connection:
        job = claim_job(connection)
    if not job:
        return False
    try:
        execute_job(job)
    except Exception as exc:
        finish_job(job, exc)
    else:
        finish_job(job)
    return True


def run_forever() -> None:
    while True:
        if not run_once():
            time.sleep(2)


if __name__ == "__main__":
    run_forever()
