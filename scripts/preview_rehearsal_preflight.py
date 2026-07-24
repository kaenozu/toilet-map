#!/usr/bin/env python3
"""Validate the local inputs for a Toilet Map v2 Preview migration rehearsal."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[1]
BACKEND_ROOT = REPO_ROOT / "v2" / "backend"
MIGRATION_ROOT = BACKEND_ROOT / "migrations"
SCHEMA_PATH = BACKEND_ROOT / "schema.sql"
DEFAULT_SNAPSHOT = REPO_ROOT / "data" / "toilets.json.gz"
DEFAULT_REPORT_DIR = REPO_ROOT / "artifacts" / "preview-rehearsal"


class PreflightError(RuntimeError):
    """Raised when the Preview rehearsal inputs are not safe or reproducible."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PreflightError(f"git {' '.join(args)} failed: {exc}") from exc


def migration_manifest() -> list[dict[str, str | int]]:
    if not MIGRATION_ROOT.is_dir():
        raise PreflightError(f"migration directory was not found: {MIGRATION_ROOT}")

    paths = sorted(MIGRATION_ROOT.glob("*.sql"))
    if not paths:
        raise PreflightError(f"no migrations were found: {MIGRATION_ROOT}")

    manifest: list[dict[str, str | int]] = []
    versions: set[str] = set()
    for path in paths:
        version, separator, name = path.stem.partition("_")
        if not separator or not version.isdigit() or not name:
            raise PreflightError(f"invalid migration filename: {path.name}")
        if version in versions:
            raise PreflightError(f"duplicate migration version: {version}")
        versions.add(version)
        manifest.append(
            {
                "version": version,
                "name": name,
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )

    if not SCHEMA_PATH.is_file():
        raise PreflightError(f"schema bootstrap was not found: {SCHEMA_PATH}")
    includes = [
        line.split(maxsplit=1)[1].strip()
        for line in SCHEMA_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("\\ir ")
    ]
    expected = [f"migrations/{item['filename']}" for item in manifest]
    if includes != expected:
        raise PreflightError(f"schema.sql migration includes differ: expected={expected}, actual={includes}")
    return manifest


def database_target() -> dict[str, str | int | None] | None:
    raw_url = os.environ.get("DATABASE_URL")
    if not raw_url:
        return None

    parsed = urlparse(raw_url.replace("postgresql+psycopg://", "postgresql://"))
    target = {
        "scheme": parsed.scheme,
        "host": parsed.hostname,
        "port": parsed.port,
        "database": unquote(parsed.path.lstrip("/")),
        "user": unquote(parsed.username or ""),
    }
    if target["scheme"] != "postgresql" or not target["host"] or not target["database"]:
        raise PreflightError("DATABASE_URL must be a complete PostgreSQL connection URL")

    expected_host = os.environ.get("TOILET_MAP_EXPECTED_DB_HOST")
    expected_database = os.environ.get("TOILET_MAP_EXPECTED_DB_NAME")
    if bool(expected_host) != bool(expected_database):
        raise PreflightError("expected Preview database host and name must be supplied together")
    if expected_host and target["host"] != expected_host:
        raise PreflightError(f"database host mismatch: expected {expected_host!r}, got {target['host']!r}")
    if expected_database and target["database"] != expected_database:
        raise PreflightError(
            f"database name mismatch: expected {expected_database!r}, got {target['database']!r}"
        )
    return target


def build_report(expected_branch: str | None, expected_sha: str | None) -> dict[str, Any]:
    if not BACKEND_ROOT.is_dir():
        raise PreflightError(f"v2 backend was not found: {BACKEND_ROOT}")

    snapshot = Path(os.environ.get("TOILET_MAP_SNAPSHOT", str(DEFAULT_SNAPSHOT))).resolve()
    if not snapshot.is_file():
        raise PreflightError(f"legacy snapshot was not found: {snapshot}")

    branch = git_output("branch", "--show-current")
    git_sha = git_output("rev-parse", "HEAD")
    dirty = [line for line in git_output("status", "--porcelain").splitlines() if line]
    if dirty:
        raise PreflightError("working tree must be clean before Preview rehearsal")
    if expected_branch and branch != expected_branch:
        raise PreflightError(f"git branch mismatch: expected {expected_branch!r}, got {branch!r}")
    if expected_sha and git_sha != expected_sha:
        raise PreflightError(f"git SHA mismatch: expected {expected_sha!r}, got {git_sha!r}")

    return {
        "status": "passed",
        "checked_at": datetime.now(UTC).isoformat(),
        "repository": {"root": str(REPO_ROOT), "branch": branch, "git_sha": git_sha},
        "snapshot": {
            "path": str(snapshot),
            "size_bytes": snapshot.stat().st_size,
            "sha256": sha256_file(snapshot),
        },
        "migrations": migration_manifest(),
        "database_target": database_target(),
        "next_command": "python -m app.cli migration-status",
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--expected-branch", help="approved branch name, usually main")
    result.add_argument("--expected-sha", help="approved full commit SHA")
    result.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    report_dir = args.report_dir.resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = report_dir / f"preview-preflight-{timestamp}.json"

    try:
        report = build_report(args.expected_branch, args.expected_sha)
        exit_code = 0
    except PreflightError as exc:
        report = {
            "status": "failed",
            "checked_at": datetime.now(UTC).isoformat(),
            "error": str(exc),
        }
        exit_code = 1

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    report_path.write_text(payload, encoding="utf-8")
    print(payload)
    print(f"\nReport: {report_path}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
