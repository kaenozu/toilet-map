"""Tests for the database-free Preview rehearsal preflight."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "preview_rehearsal_preflight.py"


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("preview_rehearsal_preflight", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare_bundle(module: ModuleType, tmp_path: Path) -> tuple[Path, Path]:
    backend = tmp_path / "v2" / "backend"
    migrations = backend / "migrations"
    migrations.mkdir(parents=True)
    (migrations / "0001_initial.sql").write_text("SELECT 1;", encoding="utf-8")
    (migrations / "0002_source.sql").write_text("SELECT 2;", encoding="utf-8")
    schema = backend / "schema.sql"
    schema.write_text(
        "\\ir migrations/0001_initial.sql\n\\ir migrations/0002_source.sql\n",
        encoding="utf-8",
    )
    module.BACKEND_ROOT = backend
    module.MIGRATION_ROOT = migrations
    module.SCHEMA_PATH = schema
    return backend, migrations


def test_sha256_file_is_stable(tmp_path: Path) -> None:
    module = load_module()
    path = tmp_path / "sample.txt"
    path.write_text("abc", encoding="utf-8")
    assert module.sha256_file(path) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_migration_manifest_validates_schema_order(tmp_path: Path) -> None:
    module = load_module()
    prepare_bundle(module, tmp_path)
    manifest = module.migration_manifest()
    assert [item["version"] for item in manifest] == ["0001", "0002"]
    assert all(len(item["sha256"]) == 64 for item in manifest)


def test_migration_manifest_rejects_schema_drift(tmp_path: Path) -> None:
    module = load_module()
    backend, _ = prepare_bundle(module, tmp_path)
    (backend / "schema.sql").write_text("\\ir migrations/0002_source.sql\n", encoding="utf-8")
    with pytest.raises(module.PreflightError, match="migration includes differ"):
        module.migration_manifest()


def test_migration_manifest_rejects_invalid_and_duplicate_versions(tmp_path: Path) -> None:
    module = load_module()
    _, migrations = prepare_bundle(module, tmp_path)
    (migrations / "bad.sql").write_text("SELECT 3;", encoding="utf-8")
    with pytest.raises(module.PreflightError, match="invalid migration filename"):
        module.migration_manifest()

    (migrations / "bad.sql").unlink()
    (migrations / "0001_duplicate.sql").write_text("SELECT 3;", encoding="utf-8")
    with pytest.raises(module.PreflightError, match="duplicate migration version"):
        module.migration_manifest()


def test_database_target_is_optional_and_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert module.database_target() is None

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://preview:secret@db.example:5432/toilet_preview")
    monkeypatch.setenv("TOILET_MAP_EXPECTED_DB_HOST", "db.example")
    monkeypatch.setenv("TOILET_MAP_EXPECTED_DB_NAME", "toilet_preview")
    target = module.database_target()
    assert target == {
        "scheme": "postgresql",
        "host": "db.example",
        "port": 5432,
        "database": "toilet_preview",
        "user": "preview",
    }
    assert "secret" not in json.dumps(target)


def test_database_target_rejects_incomplete_or_mismatched_guards(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module()
    monkeypatch.setenv("DATABASE_URL", "sqlite:///tmp.db")
    with pytest.raises(module.PreflightError, match="complete PostgreSQL"):
        module.database_target()

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db.example/toilet_preview")
    monkeypatch.setenv("TOILET_MAP_EXPECTED_DB_HOST", "db.example")
    monkeypatch.delenv("TOILET_MAP_EXPECTED_DB_NAME", raising=False)
    with pytest.raises(module.PreflightError, match="supplied together"):
        module.database_target()

    monkeypatch.setenv("TOILET_MAP_EXPECTED_DB_NAME", "other")
    with pytest.raises(module.PreflightError, match="database name mismatch"):
        module.database_target()


def test_build_report_checks_checkout_snapshot_and_bundle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = load_module()
    prepare_bundle(module, tmp_path)
    snapshot = tmp_path / "toilets.json.gz"
    snapshot.write_bytes(b"snapshot")
    module.DEFAULT_SNAPSHOT = snapshot
    monkeypatch.delenv("TOILET_MAP_SNAPSHOT", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    outputs = {
        ("branch", "--show-current"): "main",
        ("rev-parse", "HEAD"): "a" * 40,
        ("status", "--porcelain"): "",
    }
    monkeypatch.setattr(module, "git_output", lambda *args: outputs[args])

    report = module.build_report("main", "a" * 40)
    assert report["status"] == "passed"
    assert report["repository"]["branch"] == "main"
    assert report["snapshot"]["size_bytes"] == 8
    assert report["next_command"] == "python -m app.cli migration-status"


def test_build_report_rejects_dirty_or_wrong_checkout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = load_module()
    prepare_bundle(module, tmp_path)
    snapshot = tmp_path / "toilets.json.gz"
    snapshot.write_bytes(b"snapshot")
    module.DEFAULT_SNAPSHOT = snapshot

    outputs = {
        ("branch", "--show-current"): "feature",
        ("rev-parse", "HEAD"): "b" * 40,
        ("status", "--porcelain"): " M file.py",
    }
    monkeypatch.setattr(module, "git_output", lambda *args: outputs[args])
    with pytest.raises(module.PreflightError, match="working tree must be clean"):
        module.build_report("main", "a" * 40)

    outputs[("status", "--porcelain")] = ""
    with pytest.raises(module.PreflightError, match="branch mismatch"):
        module.build_report("main", "b" * 40)
    with pytest.raises(module.PreflightError, match="SHA mismatch"):
        module.build_report("feature", "a" * 40)


def test_git_output_wraps_process_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module()

    def fail_run(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ["git"])

    monkeypatch.setattr(module.subprocess, "run", fail_run)
    with pytest.raises(module.PreflightError, match="git status failed"):
        module.git_output("status")


def test_main_writes_success_and_failure_reports(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = load_module()
    report_dir = tmp_path / "reports"
    monkeypatch.setattr(module, "build_report", lambda branch, sha: {"status": "passed"})
    assert module.main(["--report-dir", str(report_dir)]) == 0
    assert json.loads(next(report_dir.glob("*.json")).read_text(encoding="utf-8"))["status"] == "passed"

    module = load_module()
    report_dir = tmp_path / "failed"

    def fail_report(branch, sha):
        raise module.PreflightError("blocked")

    monkeypatch.setattr(module, "build_report", fail_report)
    assert module.main(["--report-dir", str(report_dir)]) == 1
    assert json.loads(next(report_dir.glob("*.json")).read_text(encoding="utf-8"))["error"] == "blocked"
