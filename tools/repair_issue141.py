from pathlib import Path

queue_path = Path("v2/backend/app/job_queue.py")
text = queue_path.read_text(encoding="utf-8")
old = """    job_id: int,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    stats: dict[str, Any] | None = None,
) -> bool:
"""
new = """    job_id: int,
    expected_attempt: int,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    stats: dict[str, Any] | None = None,
) -> bool:
"""
if text.count(old) != 1:
    raise SystemExit(f"heartbeat signature count={text.count(old)}")
text = text.replace(old, new, 1)
old = """         WHERE id = %s AND status = 'running'
        RETURNING id
        \"\"\",
        (lease_seconds, json.dumps(stats or {}, ensure_ascii=False), job_id),
"""
new = """         WHERE id = %s AND status = 'running' AND attempts = %s
        RETURNING id
        \"\"\",
        (lease_seconds, json.dumps(stats or {}, ensure_ascii=False), job_id, expected_attempt),
"""
if text.count(old) != 1:
    raise SystemExit(f"heartbeat SQL count={text.count(old)}")
text = text.replace(old, new, 1)
old = """    stats: dict[str, Any] | None = None,
) -> None:
    if error is None:
        connection.execute(
"""
new = """    stats: dict[str, Any] | None = None,
) -> bool:
    expected_attempt = int(job[\"attempts\"])
    if error is None:
        row = connection.execute(
"""
if text.count(old) != 1:
    raise SystemExit(f"finish signature count={text.count(old)}")
text = text.replace(old, new, 1)
old = """             WHERE id = %s
            \"\"\",
            (json.dumps(stats or {}, ensure_ascii=False), job[\"id\"]),
        )
        return
"""
new = """             WHERE id = %s AND status = 'running' AND attempts = %s
            RETURNING id
            \"\"\",
            (json.dumps(stats or {}, ensure_ascii=False), job[\"id\"], expected_attempt),
        ).fetchone()
        return row is not None
"""
if text.count(old) != 1:
    raise SystemExit(f"success finish count={text.count(old)}")
text = text.replace(old, new, 1)
old = """        connection.execute(
            \"\"\"
            UPDATE jobs
               SET status = 'retry_wait',
"""
new = """        row = connection.execute(
            \"\"\"
            UPDATE jobs
               SET status = 'retry_wait',
"""
if text.count(old) != 1:
    raise SystemExit(f"retry finish start count={text.count(old)}")
text = text.replace(old, new, 1)
old = """             WHERE id = %s
            \"\"\",
            (
                retry_delay_seconds(attempts),
                error.__class__.__name__,
                str(error)[:2000],
                json.dumps(stats or {}, ensure_ascii=False),
                job[\"id\"],
            ),
        )
    else:
        connection.execute(
"""
new = """             WHERE id = %s AND status = 'running' AND attempts = %s
            RETURNING id
            \"\"\",
            (
                retry_delay_seconds(attempts),
                error.__class__.__name__,
                str(error)[:2000],
                json.dumps(stats or {}, ensure_ascii=False),
                job[\"id\"],
                expected_attempt,
            ),
        ).fetchone()
        return row is not None
    else:
        row = connection.execute(
"""
if text.count(old) != 1:
    raise SystemExit(f"retry finish tail count={text.count(old)}")
text = text.replace(old, new, 1)
old = """             WHERE id = %s
            \"\"\",
            (
                error.__class__.__name__,
                str(error)[:2000],
                json.dumps(stats or {}, ensure_ascii=False),
                job[\"id\"],
            ),
        )


def cancel_job"""
new = """             WHERE id = %s AND status = 'running' AND attempts = %s
            RETURNING id
            \"\"\",
            (
                error.__class__.__name__,
                str(error)[:2000],
                json.dumps(stats or {}, ensure_ascii=False),
                job[\"id\"],
                expected_attempt,
            ),
        ).fetchone()
        return row is not None


def cancel_job"""
if text.count(old) != 1:
    raise SystemExit(f"failed finish count={text.count(old)}")
queue_path.write_text(text.replace(old, new, 1), encoding="utf-8")

worker_path = Path("v2/backend/app/worker.py")
text = worker_path.read_text(encoding="utf-8")
text = text.replace(
    "import json\nimport os\nimport time\n",
    "import json\nimport logging\nimport os\nimport time\nfrom threading import Event, Thread\n",
    1,
)
text = text.replace(
    "from .job_queue import claim_job, finish_job\n",
    "from .job_queue import DEFAULT_LEASE_SECONDS, claim_job, finish_job, heartbeat_job\n",
    1,
)
text = text.replace(
    "from .resolution import generate_match_candidates\n\n\n",
    "from .resolution import generate_match_candidates\n\nlogger = logging.getLogger(__name__)\n\n\n",
    1,
)
old = """def run_once() -> bool:
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
"""
new = """def _renew_job_lease(job: dict[str, Any], lease_seconds: int) -> bool:
    with database() as connection:
        renewed = heartbeat_job(
            connection,
            job_id=int(job[\"id\"]),
            expected_attempt=int(job[\"attempts\"]),
            lease_seconds=lease_seconds,
        )
        connection.commit()
    return renewed


def _heartbeat_loop(
    job: dict[str, Any],
    stop_event: Event,
    lease_lost: Event,
    *,
    lease_seconds: int,
    interval_seconds: float,
) -> None:
    while not stop_event.wait(interval_seconds):
        try:
            renewed = _renew_job_lease(job, lease_seconds)
        except Exception:
            logger.exception(\"Job heartbeat failed for job %s\", job[\"id\"])
            continue
        if not renewed:
            lease_lost.set()
            logger.warning(
                \"Job lease generation was lost for job %s attempt %s\",
                job[\"id\"],
                job[\"attempts\"],
            )
            return


def run_once(
    *,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    heartbeat_interval_seconds: float | None = None,
) -> bool:
    with database() as connection:
        job = claim_job(connection, lease_seconds=lease_seconds)
        connection.commit()
    if not job:
        return False

    interval = heartbeat_interval_seconds or max(1.0, lease_seconds / 3)
    stop_event = Event()
    lease_lost = Event()
    heartbeat = Thread(
        target=_heartbeat_loop,
        args=(job, stop_event, lease_lost),
        kwargs={\"lease_seconds\": lease_seconds, \"interval_seconds\": interval},
        daemon=True,
    )
    heartbeat.start()
    error: Exception | None = None
    stats: dict[str, Any] | None = None
    try:
        stats = execute_job(job)
    except Exception as exc:
        error = exc
    finally:
        stop_event.set()
        heartbeat.join(timeout=max(1.0, interval * 2))

    with database() as connection:
        finished = finish_job(connection, job=job, error=error, stats=stats)
        connection.commit()
    if not finished or lease_lost.is_set():
        logger.warning(
            \"Ignored stale completion for job %s attempt %s\",
            job[\"id\"],
            job[\"attempts\"],
        )
    return True
"""
if text.count(old) != 1:
    raise SystemExit(f"run_once block count={text.count(old)}")
worker_path.write_text(text.replace(old, new, 1), encoding="utf-8")
Path("tools/repair_issue141.py").unlink()
Path(".github/workflows/repair-issue141-job-fencing.yml").unlink()
