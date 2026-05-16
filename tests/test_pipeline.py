"""
tests/test_pipeline.py
Tests for batch/pipeline.py post-process pipeline

関連: batch/pipeline.py, batch/process_data.py, batch/to_sqlite.py
"""
from unittest.mock import MagicMock

import pipeline
import pytest


def _make_result(returncode):
    r = MagicMock()
    r.returncode = returncode
    return r


def _null_ctx():
    class NullCtx:
        def __enter__(self): return self
        def __exit__(self, *a): pass
    return NullCtx()


class TestRunPostProcessPipeline:
    def test_success_runs_both_steps(self, monkeypatch):
        calls = []

        def fake_run(cmd):
            calls.append(cmd)
            return _make_result(0)

        monkeypatch.setattr(pipeline, "file_lock", lambda *a, **kw: _null_ctx())
        monkeypatch.setattr(pipeline.subprocess, "run", fake_run)

        pipeline.run_postprocess_pipeline("input.json", "output.json.gz", "/tmp")

        assert len(calls) == 2
        assert "process_data.py" in calls[0][1]
        assert "--incremental" in calls[0]
        assert "to_sqlite.py" in calls[1][1]
        assert "--incremental" in calls[1]

    def test_raises_when_process_data_fails(self, monkeypatch):
        monkeypatch.setattr(pipeline, "file_lock", lambda *a, **kw: _null_ctx())
        monkeypatch.setattr(pipeline.subprocess, "run", lambda *a, **kw: _make_result(1))

        with pytest.raises(pipeline.DataError, match="Data processing failed"):
            pipeline.run_postprocess_pipeline("in.json", "out.json", "/tmp")

    def test_raises_when_sqlite_fails(self, monkeypatch):
        calls = []

        def fake_run(cmd):
            calls.append(1)
            rc = 0 if len(calls) == 1 else 1
            return _make_result(rc)

        monkeypatch.setattr(pipeline, "file_lock", lambda *a, **kw: _null_ctx())
        monkeypatch.setattr(pipeline.subprocess, "run", fake_run)

        with pytest.raises(pipeline.DataError, match="SQLite conversion failed"):
            pipeline.run_postprocess_pipeline("in.json", "out.json", "/tmp")
