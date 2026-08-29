from __future__ import annotations

from app import job_queue, worker


class _Result:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _Connection:
    def __init__(self, row=None):
        self.row = row
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, query: str, params=()):
        self.calls.append((query, tuple(params)))
        return _Result(self.row)


def test_heartbeat_is_fenced_by_claim_attempt_generation() -> None:
    connection = _Connection({"id": 7})
    assert job_queue.heartbeat_job(
        connection,
        job_id=7,
        expected_attempt=3,
        lease_seconds=30,
    )
    query, params = connection.calls[-1]
    assert "status = 'running'" in query
    assert "attempts = %s" in query
    assert params[-2:] == (7, 3)


def test_finish_rejects_stale_worker_generation() -> None:
    connection = _Connection(None)
    finished = job_queue.finish_job(
        connection,
        job={"id": 7, "attempts": 2, "max_attempts": 3, "retryable": True},
        stats={"rows": 1},
    )
    assert finished is False
    query, params = connection.calls[-1]
    assert "status = 'running'" in query
    assert "attempts = %s" in query
    assert params[-2:] == (7, 2)


class _StopAfterOneHeartbeat:
    def __init__(self) -> None:
        self.calls = 0

    def wait(self, _timeout: float) -> bool:
        self.calls += 1
        return self.calls > 1


def test_heartbeat_loop_renews_while_job_is_running(monkeypatch) -> None:
    renewals: list[tuple[int, int]] = []

    def renew(job, lease_seconds: int) -> bool:
        renewals.append((int(job["id"]), lease_seconds))
        return True

    monkeypatch.setattr(worker, "_renew_job_lease", renew)
    lease_lost = worker.Event()
    worker._heartbeat_loop(
        {"id": 7, "attempts": 2},
        _StopAfterOneHeartbeat(),
        lease_lost,
        lease_seconds=30,
        interval_seconds=10.0,
    )
    assert renewals == [(7, 30)]
    assert not lease_lost.is_set()


def test_heartbeat_loop_marks_generation_lost(monkeypatch) -> None:
    monkeypatch.setattr(worker, "_renew_job_lease", lambda _job, _lease_seconds: False)
    lease_lost = worker.Event()
    worker._heartbeat_loop(
        {"id": 7, "attempts": 2},
        _StopAfterOneHeartbeat(),
        lease_lost,
        lease_seconds=30,
        interval_seconds=10.0,
    )
    assert lease_lost.is_set()
