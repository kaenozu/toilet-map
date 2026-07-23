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
                   count(*) FILTER (WHERE toilet_score IS NOT NULL AND toilet_score NOT BETWEEN 0 AND 100) AS invalid_score
              FROM places WHERE dataset_version_id = %s
            """,
            (dataset_version_id,),
        ).fetchone()
        if result is None:
            raise RuntimeError("validation query returned no result")
        valid = all(
            (
                result["total"] > 0,
                result["missing_name"] == 0,
                result["invalid_location"] == 0,
                result["duplicate_keys"] == 0,
                result["invalid_score"] == 0,
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
                json.dumps(dict(result)),
                valid,
                dataset_version_id,
            ),
        )
        connection.commit()
        if not valid:
            raise ValueError(f"dataset validation failed: {dict(result)}")


def publish_dataset(dataset_version_id: int) -> None:
    with database() as connection:
        connection.execute("SELECT publish_dataset(%s)", (dataset_version_id,))
        connection.commit()


def execute_job(job: dict[str, Any]) -> None:
    payload = job["payload"]
    dataset_id = int(payload.get("dataset_version_id", 0))
    if job["kind"] == "validate_dataset":
        validate_dataset(dataset_id)
    elif job["kind"] == "publish_dataset":
        publish_dataset(dataset_id)
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
