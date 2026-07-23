"""Tests for the staged post-process pipeline."""

import gzip
import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pipeline
import pytest


def _result(returncode: int):
    result = MagicMock()
    result.returncode = returncode
    return result


def test_success_builds_both_staged_artifacts(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    processed = data_dir / "toilets.json.gz"
    input_path = tmp_path / "raw.json"
    input_path.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(pipeline, "SYNC_LOCK_PATH", str(data_dir / ".lock"))
    db_path = data_dir / "toilets.db"
    manifest_path = data_dir / "snapshot.json"
    monkeypatch.setattr(pipeline, "DB_PATH", str(db_path))
    monkeypatch.setattr(pipeline, "SNAPSHOT_MANIFEST_PATH", str(manifest_path))
    calls = []

    def fake_run(command):
        calls.append(command)
        if "process_data.py" in command[1]:
            with gzip.open(command[3], "wt", encoding="utf-8") as file:
                json.dump({"metadata": {}, "toilets": []}, file)
        else:
            staged_db = Path(command[command.index("--db-path") + 1])
            with sqlite3.connect(staged_db) as connection:
                connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
        return _result(0)

    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)
    pipeline.run_postprocess_pipeline(str(input_path), str(processed), str(tmp_path))
    with gzip.open(processed, "rt", encoding="utf-8") as file:
        snapshot_id = json.load(file)["metadata"]["snapshot_id"]
    with sqlite3.connect(db_path) as connection:
        db_snapshot_id = connection.execute(
            "SELECT value FROM metadata WHERE key = 'snapshot_id'"
        ).fetchone()[0]
    assert db_snapshot_id == snapshot_id
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["snapshot_id"] == snapshot_id
    assert len(calls) == 2
    assert "--incremental" in calls[0]
    assert "--db-path" in calls[1]
    assert calls[1][-1] == "--incremental"


def test_raises_when_process_data_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "SYNC_LOCK_PATH", str(tmp_path / ".lock"))
    monkeypatch.setattr(pipeline.subprocess, "run", lambda *_: _result(1))
    with pytest.raises(pipeline.DataError, match="Data processing failed"):
        pipeline.run_postprocess_pipeline("in.json", str(tmp_path / "out.json.gz"), str(tmp_path))


def test_raises_when_sqlite_fails_without_publishing(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    processed = data_dir / "toilets.json.gz"
    processed.write_bytes(b"old-json")
    db_path = data_dir / "toilets.db"
    db_path.write_bytes(b"old-db")
    monkeypatch.setattr(pipeline, "SYNC_LOCK_PATH", str(data_dir / ".lock"))
    monkeypatch.setattr(pipeline, "DB_PATH", str(db_path))
    calls = []

    def fake_run(command):
        calls.append(command)
        if len(calls) == 1:
            with gzip.open(command[3], "wt", encoding="utf-8") as file:
                json.dump({"metadata": {}, "toilets": []}, file)
            return _result(0)
        return _result(1)

    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)
    with pytest.raises(pipeline.DataError, match="SQLite conversion failed"):
        pipeline.run_postprocess_pipeline("in.json", str(processed), str(tmp_path))
    assert processed.read_bytes() == b"old-json"
    assert db_path.read_bytes() == b"old-db"
