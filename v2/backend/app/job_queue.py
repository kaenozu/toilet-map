"""Leased, idempotent PostgreSQL job queue state machine."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from psycopg import Connection

DEFAULT_LEASE_SECONDS = 300


@dataclass(frozen=True)
class EnqueueRequest:
    kind: str
    payload: dict[str, Any]
    idempotency_key: str | None = None
    dataset_version_id: int | None = None
    provider: str | None = None
    parent_job_id: int | None = None
    max_attempts: int = 3
    retryable: bool = True


def retry_delay_seconds(attempts: int) -> int:
    return min(300, 2 ** max(1, attempts))


def enqueue_job(connection: Connection, request: EnqueueRequest) -> tuple[int, bool]:
    row = connection.execute(
        """
        INSERT INTO jobs (
          kind, payload, idempotency_key, dataset_version_id, provider,
          parent_job_id, max_attempts, retryable
        ) VALUES (%s, %s::jsonb, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (idempotency_key) WHERE idempotency_key IS NOT NULL
        DO NOTHING
        RETURNING id
        """,
        (
            request.kind,
            json.dumps(request.payload, ensure_ascii=False),
            request.idempotency_key,
            request.dataset_version_id,
            request.provider,
            request.parent_job_id,
            request.max_attempts,
            request.retryable,
        ),
    ).fetchone()
    if row is not None:
        return int(row["id"]), True
    if request.idempotency_key is None:
        raise RuntimeError("job insertion failed")
    existing = connection.execute(
        "SELECT id FROM jobs WHERE idempotency_key = %s",
        (request.idempotency_key,),
    ).fetchone()
    if existing is None:
        raise RuntimeError("idempotent job lookup failed")
    return int(existing["id"]), False


def recover_expired_jobs(connection: Connection) -> int:
    row = connection.execute(
        """
        WITH changed AS (
          UPDATE jobs
             SET status = CASE
                            WHEN retryable AND attempts < max_attempts THEN 'retry_wait'::job_status
                            ELSE 'failed'::job_status
                          END,
                 available_at = CASE
                                  WHEN retryable AND attempts < max_attempts
                                    THEN now() + make_interval(secs => LEAST(300, power(2, attempts)::INTEGER))
                                  ELSE available_at
                                END,
                 finished_at = CASE
                                 WHEN retryable AND attempts < max_attempts THEN NULL
                                 ELSE now()
                               END,
                 error_code = 'LeaseExpired',
                 error_message = 'Job lease expired before completion',
                 lease_expires_at = NULL,
                 heartbeat_at = NULL,
                 updated_at = now()
           WHERE status = 'running'
             AND lease_expires_at IS NOT NULL
             AND lease_expires_at <= now()
          RETURNING id
        )
        SELECT count(*) AS total FROM changed
        """
    ).fetchone()
    return int(row["total"] if row else 0)


def claim_job(connection: Connection, *, lease_seconds: int = DEFAULT_LEASE_SECONDS) -> dict[str, Any] | None:
    recover_expired_jobs(connection)
    row = connection.execute(
        """
        WITH candidate AS (
          SELECT id FROM jobs
           WHERE status IN ('queued', 'retry_wait')
             AND available_at <= now()
             AND attempts < max_attempts
             AND (parent_job_id IS NULL OR EXISTS (
               SELECT 1 FROM jobs parent WHERE parent.id = jobs.parent_job_id AND parent.status = 'succeeded'
             ))
           ORDER BY available_at, id
           FOR UPDATE SKIP LOCKED
           LIMIT 1
        )
        UPDATE jobs job
           SET status = 'running',
               started_at = COALESCE(started_at, now()),
               heartbeat_at = now(),
               lease_expires_at = now() + make_interval(secs => %s),
               attempts = attempts + 1,
               error_code = NULL,
               error_message = NULL,
               updated_at = now()
          FROM candidate
         WHERE job.id = candidate.id
        RETURNING job.*
        """,
        (lease_seconds,),
    ).fetchone()
    return dict(row) if row else None


def heartbeat_job(
    connection: Connection,
    *,
    job_id: int,
    expected_attempt: int,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    stats: dict[str, Any] | None = None,
) -> bool:
    row = connection.execute(
        """
        UPDATE jobs
           SET heartbeat_at = now(),
               lease_expires_at = now() + make_interval(secs => %s),
               stats = stats || %s::jsonb,
               updated_at = now()
         WHERE id = %s AND status = 'running' AND attempts = %s
        RETURNING id
        """,
        (lease_seconds, json.dumps(stats or {}, ensure_ascii=False), job_id, expected_attempt),
    ).fetchone()
    return row is not None


def finish_job(
    connection: Connection,
    *,
    job: dict[str, Any],
    error: Exception | None = None,
    stats: dict[str, Any] | None = None,
) -> bool:
    expected_attempt = int(job["attempts"])
    if error is None:
        row = connection.execute(
            """
            UPDATE jobs
               SET status = 'succeeded', finished_at = now(), lease_expires_at = NULL,
                   heartbeat_at = NULL, stats = stats || %s::jsonb, updated_at = now()
             WHERE id = %s AND status = 'running' AND attempts = %s
            RETURNING id
            """,
            (json.dumps(stats or {}, ensure_ascii=False), job["id"], expected_attempt),
        ).fetchone()
        return row is not None
    attempts = int(job["attempts"])
    max_attempts = int(job["max_attempts"])
    retryable = bool(job.get("retryable", True))
    if retryable and attempts < max_attempts:
        row = connection.execute(
            """
            UPDATE jobs
               SET status = 'retry_wait',
                   available_at = now() + make_interval(secs => %s),
                   lease_expires_at = NULL,
                   heartbeat_at = NULL,
                   error_code = %s,
                   error_message = %s,
                   stats = stats || %s::jsonb,
                   updated_at = now()
             WHERE id = %s AND status = 'running' AND attempts = %s
            RETURNING id
            """,
            (
                retry_delay_seconds(attempts),
                error.__class__.__name__,
                str(error)[:2000],
                json.dumps(stats or {}, ensure_ascii=False),
                job["id"],
                expected_attempt,
            ),
        ).fetchone()
        return row is not None
    else:
        row = connection.execute(
            """
            UPDATE jobs
               SET status = 'failed', finished_at = now(), lease_expires_at = NULL,
                   heartbeat_at = NULL, error_code = %s, error_message = %s,
                   stats = stats || %s::jsonb, updated_at = now()
             WHERE id = %s AND status = 'running' AND attempts = %s
            RETURNING id
            """,
            (
                error.__class__.__name__,
                str(error)[:2000],
                json.dumps(stats or {}, ensure_ascii=False),
                job["id"],
                expected_attempt,
            ),
        ).fetchone()
        return row is not None


def cancel_job(connection: Connection, *, job_id: int) -> bool:
    row = connection.execute(
        """
        UPDATE jobs SET status = 'cancelled', finished_at = now(), updated_at = now()
         WHERE id = %s AND status IN ('queued', 'retry_wait')
        RETURNING id
        """,
        (job_id,),
    ).fetchone()
    return row is not None


def lease_duration() -> timedelta:
    return timedelta(seconds=DEFAULT_LEASE_SECONDS)
