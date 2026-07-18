"""Tests for the staged post-process pipeline."""

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
    monkeypatch.setattr(pipeline, "DB_PATH", str(data_dir / "toilets.db"))
    calls = []

    def fake_run(command):
        calls.append(command)
        if "process_data.py" in command[1]:
            Path(command[3]).write_bytes(b"json")
        else:
            Path(command[command.index("--db-path") + 1]).write_bytes(b"db")
        return _result(0)

    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)
    pipeline.run_postprocess_pipeline(str(input_path), str(processed), str(tmp_path))
    assert processed.read_bytes() == b"json"
    assert (data_dir / "toilets.db").read_bytes() == b"db"
    assert len(calls) == 2
    assert "--incremental" in calls[0]
    assert "--db-path" in calls[1]


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
            Path(command[3]).write_bytes(b"new-json")
            return _result(0)
        return _result(1)

    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)
    with pytest.raises(pipeline.DataError, match="SQLite conversion failed"):
        pipeline.run_postprocess_pipeline("in.json", str(processed), str(tmp_path))
    assert processed.read_bytes() == b"old-json"
    assert db_path.read_bytes() == b"old-db"
