"""Regression tests for scripts/evaluate_map_sampling.py."""

from __future__ import annotations

import json
import sqlite3

from scripts.evaluate_map_sampling import MISSING_PREFECTURE, evaluate_database, main


def _create_database(tmp_path, rows):
    db_path = tmp_path / "toilets.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE toilets (
                id INTEGER PRIMARY KEY,
                prefecture TEXT,
                lat REAL,
                lng REAL,
                confidence REAL,
                review_count INTEGER,
                toilet_review_count INTEGER,
                toilet_score REAL
            )
            """
        )
        connection.executemany("INSERT INTO toilets VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    return db_path


def test_balanced_sampling_represents_sparse_prefecture(tmp_path):
    db_path = _create_database(
        tmp_path,
        [
            (1, "東京都", 35.6, 139.7, 0.99, 100, 20, 90),
            (2, "東京都", 35.7, 139.8, 0.98, 90, 18, 85),
            (3, "東京都", 35.8, 139.9, 0.97, 80, 16, 80),
            (4, "東京都", 35.9, 140.0, 0.96, 70, 14, 75),
            (5, "大阪府", 34.7, 135.5, 0.50, 10, 2, 70),
        ],
    )

    report = evaluate_database(db_path, limit=3)

    assert report["current"]["sampled_by_prefecture"] == {"東京都": 3}
    assert report["current"]["omitted_prefectures"] == ["大阪府"]
    assert report["balanced"]["sampled_by_prefecture"] == {"大阪府": 1, "東京都": 2}
    assert report["balanced"]["omitted_prefectures"] == []


def test_invalid_coordinates_are_excluded_and_missing_prefecture_is_explicit(tmp_path):
    db_path = _create_database(
        tmp_path,
        [
            (1, None, 35.6, 139.7, 0.9, 10, 2, 80),
            (2, "東京都", 91.0, 139.8, 1.0, 100, 20, 90),
            (3, "大阪府", 34.7, 181.0, 1.0, 100, 20, 90),
        ],
    )

    report = evaluate_database(db_path, limit=10)

    assert report["total_valid_coordinates"] == 1
    assert report["total_prefectures"] == 1
    assert report["current"]["sampled_by_prefecture"] == {MISSING_PREFECTURE: 1}


def test_cli_outputs_json(tmp_path, capsys):
    db_path = _create_database(
        tmp_path,
        [(1, "東京都", 35.6, 139.7, 0.9, 10, 2, 80)],
    )

    assert main(["--db", str(db_path), "--limit", "1", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["database"] == str(db_path)
    assert payload["current"]["coverage_ratio"] == 1.0
    assert payload["balanced"]["top_prefecture"] == "東京都"
