"""Regression tests for the full-source-review fixes."""

from __future__ import annotations

import gzip
import json
import sqlite3
import sys
from pathlib import Path

import pytest

from batch import cli_parser
from batch.api_server import ToiletModel
from batch.snapshot_integrity import snapshot_ids_match


def _write_snapshot_files(tmp_path: Path, *, json_id: str, db_id: str, manifest_id: str) -> tuple[str, str, str]:
    json_path = tmp_path / "toilets.json.gz"
    db_path = tmp_path / "toilets.db"
    manifest_path = tmp_path / "snapshot.json"

    with gzip.open(json_path, "wt", encoding="utf-8") as handle:
        json.dump({"metadata": {"snapshot_id": json_id}, "toilets": []}, handle)
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
        connection.execute("INSERT INTO metadata VALUES ('snapshot_id', ?)", (db_id,))
    manifest_path.write_text(json.dumps({"snapshot_id": manifest_id}), encoding="utf-8")
    return str(json_path), str(db_path), str(manifest_path)


def test_snapshot_ids_match_only_for_one_complete_generation(tmp_path: Path) -> None:
    paths = _write_snapshot_files(tmp_path, json_id="same", db_id="same", manifest_id="same")
    assert snapshot_ids_match(*paths)


def test_snapshot_ids_reject_mixed_generations(tmp_path: Path) -> None:
    paths = _write_snapshot_files(tmp_path, json_id="new", db_id="old", manifest_id="new")
    assert not snapshot_ids_match(*paths)


@pytest.mark.parametrize("value", ["0", "-1", "abc", "1O"])
def test_max_queries_rejects_invalid_values(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setattr(sys, "argv", ["scrape_runner.py", "--max-queries", value])
    with pytest.raises(SystemExit):
        cli_parser.parse_args()


def test_max_queries_accepts_positive_integer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["scrape_runner.py", "--max-queries", "2"])
    assert cli_parser.parse_args()["max_queries"] == 2


def test_api_model_accepts_unscored_toilet() -> None:
    model = ToiletModel(id=1, source_id="source", toilet_score=None, confidence=None)
    assert model.toilet_score is None
    assert model.confidence is None


def test_scraper_image_is_version_pinned() -> None:
    from batch.docker_exec import DOCKER_IMAGE

    assert DOCKER_IMAGE == "gosom/google-maps-scraper:v1.12.1"
