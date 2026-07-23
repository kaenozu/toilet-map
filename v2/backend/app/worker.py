from __future__ import annotations

import json
import os
import time
from typing import Any

from psycopg import connect
from psycopg.rows import dict_row

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://toilet_map:toilet_map@localhost:5432/toilet_map",
).replace("postgresql+psycopg://", "postgresql://")


def claim_job(connection) -> dict[str, Any] | None:
    row = connection.execute(
        """
        WITH candidate AS (
          SELECT id FROM jobs
           WHERE status = 'queued' AND available_at <= now()
           ORDER BY available_at, id
           FOR UPDATE SKIP LOCKED
           LIMIT 1
        )
        UPDATE jobs j
           SET status = 'running', started_at = now(), attempts = attempts + 1
          FROM candidate
         WHERE j.id = candidate.id
        RETURNING j.*
        """
    ).fetchone()
    connection.commit()
    return row


def execute_job(job: dict[str, Any]) -> None:
    kind = job["kind"]
    payload = job["payload"]
    if kind == "validate_dataset":
        validate_dataset(int(payload["dataset_version_id"]))
        return
    raise ValueError(f"unsupported job kind: {kind}")


def validate_dataset(dataset_version_id: int) -> None:
    with connect(DATABASE_URL, row_factory=dict_row) as connection:
        result = connection.execute(
            """
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE name = '') AS missing_name,
                   count(*) FILTER (WHERE ST_IsValid(location::geometry) = false) AS invalid_location
              FROM places WHERE dataset_version_id = %s
            """,
            (dataset_version_id,),
        ).fetchone()
        valid = bool(result and result["total"] > 0 and result["missing_name"] == 0 and result["invalid_location"] == 0)
        connection.execute(
            """
            UPDATE dataset_versions
               SET status = %s, record_count = %s, validation_report = %s::jsonb
             WHERE id = %s
            """,
            ("validating" if valid else "failed", result["total"], json.dumps(result), dataset_version_id),
        )
        connection.commit()


def finish_job(job_id: int, error: Exception | None = None) -> None:
    with connect(DATABASE_URL) as connection:
        if error is None:
            connection.execute(
                "UPDATE jobs SET status = 'succeeded', finished_at = now() WHERE id = %s",
                (job_id,),
            )
        else:
            connection.execute(
                """
                UPDATE jobs SET status = 'failed', finished_at = now(),
                       error_code = %s, error_message = %s
                 WHERE id = %s
                """,
                (error.__class__.__name__, str(error)[:2000], job_id),
            )
        connection.commit()


def run_forever() -> None:
    while True:
        with connect(DATABASE_URL, row_factory=dict_row) as connection:
            job = claim_job(connection)
        if not job:
            time.sleep(2)
            continue
        try:
            execute_job(job)
        except Exception as exc:
            finish_job(job["id"], exc)
        else:
            finish_job(job["id"])


if __name__ == "__main__":
    run_forever()
