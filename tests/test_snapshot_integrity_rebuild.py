"""End-to-end tests for atomic SQLite snapshot rebuilding."""

from __future__ import annotations

import gzip
import json
import sqlite3
from pathlib import Path

from batch import snapshot_integrity


def _write_json_snapshot(path: Path, snapshot_id: str) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump({"metadata": {"snapshot_id": snapshot_id}, "toilets": []}, handle)


def test_ensure_snapshot_current_returns_when_generation_matches(tmp_path, monkeypatch) -> None:
    json_path = tmp_path / "toilets.json.gz"
    db_path = tmp_path / "toilets.db"
    manifest_path = tmp_path / "snapshot.json"
    _write_json_snapshot(json_path, "current")
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
        connection.execute("INSERT INTO metadata VALUES ('snapshot_id', 'current')")
    manifest_path.write_text('{"snapshot_id": "current"}', encoding="utf-8")
    monkeypatch.setattr(snapshot_integrity, "database_requires_rebuild", lambda _: False)
    called = False

    def fail_if_called(*_args, **_kwargs) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(snapshot_integrity, "_convert_core", fail_if_called)
    snapshot_integrity.ensure_snapshot_current(str(json_path), str(db_path), str(manifest_path))
    assert not called


def test_ensure_snapshot_current_rebuilds_database_and_manifest(tmp_path, monkeypatch) -> None:
    json_path = tmp_path / "toilets.json.gz"
    db_path = tmp_path / "toilets.db"
    manifest_path = tmp_path / "snapshot.json"
    _write_json_snapshot(json_path, "generation-2")
    monkeypatch.setattr(snapshot_integrity, "database_requires_rebuild", lambda _: True)

    def fake_convert(_json_path: str, output_path: str, *, incremental: bool) -> None:
        assert incremental is False
        with sqlite3.connect(output_path) as connection:
            connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
            connection.execute("INSERT INTO metadata VALUES ('seed', 'ok')")

    monkeypatch.setattr(snapshot_integrity, "_convert_core", fake_convert)
    snapshot_integrity.ensure_snapshot_current(str(json_path), str(db_path), str(manifest_path))

    with sqlite3.connect(db_path) as connection:
        row = connection.execute("SELECT value FROM metadata WHERE key = 'snapshot_id'").fetchone()
    assert row == ("generation-2",)
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == {"snapshot_id": "generation-2"}
    assert snapshot_integrity.snapshot_ids_match(str(json_path), str(db_path), str(manifest_path))


def test_ensure_snapshot_current_requires_canonical_json(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(snapshot_integrity, "database_requires_rebuild", lambda _: True)
    missing = tmp_path / "missing.json.gz"
    try:
        snapshot_integrity.ensure_snapshot_current(
            str(missing),
            str(tmp_path / "toilets.db"),
            str(tmp_path / "snapshot.json"),
        )
    except FileNotFoundError as exc:
        assert exc.filename == str(missing) or str(exc) == str(missing)
    else:
        raise AssertionError("missing canonical JSON must abort rebuilding")
