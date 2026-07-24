"""Regression tests for scripts/inventory_raw_data.py."""

from __future__ import annotations

import gzip
import json

import pytest

from scripts import inventory_raw_data
from scripts.inventory_raw_data import (
    discover_raw_files,
    evaluate_inventory,
    inventory_raw_file,
    load_canonical_aliases,
    main,
)


def _write_canonical(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as file:
        json.dump({"metadata": {}, "toilets": records}, file, ensure_ascii=False)


def _raw_record(place_id: str, title: str) -> dict[str, object]:
    return {
        "place_id": place_id,
        "title": title,
        "category": "公衆トイレ",
        "address": "東京都千代田区",
        "latitude": 35.68,
        "longitude": 139.76,
    }


def _write_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            if isinstance(record, str):
                file.write(record + "\n")
            else:
                file.write(json.dumps(record, ensure_ascii=False) + "\n")


def test_inventory_classifies_pending_published_duplicate_and_invalid_lines(tmp_path):
    canonical = tmp_path / "data" / "toilets.json.gz"
    _write_canonical(
        canonical,
        [
            {
                "source_id": "place_id:existing",
                "title": "既存トイレ",
                "address": "東京都千代田区",
                "lat": 35.68,
                "lng": 139.76,
            }
        ],
    )
    first = tmp_path / "batch" / "raw_data.json"
    second = tmp_path / "batch" / "raw_parts_1" / "part.json"
    pending = _raw_record("pending", "新規トイレ")
    _write_jsonl(
        first,
        [
            _raw_record("existing", "既存トイレ"),
            pending,
            {"title": "座標なしトイレ", "category": "公衆トイレ"},
            "not-json",
            [],
        ],
    )
    _write_jsonl(second, [pending])

    report = evaluate_inventory(canonical, [first, second])

    assert report["canonical_records"] == 1
    assert report["raw_file_count"] == 2
    assert report["files_with_pending"] == [str(first)]
    assert report["totals"] == {
        "nonempty_lines": 6,
        "valid_objects": 4,
        "published_records": 1,
        "pending_records": 1,
        "duplicate_records": 1,
        "rejected_records": 1,
        "malformed_records": 2,
    }


def test_discovery_is_recursive_sorted_and_duplicate_free(tmp_path):
    paths = [
        tmp_path / "batch" / "raw_data.json",
        tmp_path / "batch" / "raw_data_tokyo.json",
        tmp_path / "batch" / "raw_parts_1" / "nested" / "part.jsonl",
    ]
    for path in paths:
        _write_jsonl(path, [])
    _write_jsonl(tmp_path / "batch" / "output" / "ignored.json", [])

    discovered = discover_raw_files(tmp_path)

    assert discovered == sorted(paths, key=lambda path: path.as_posix())


def test_cli_json_and_fail_on_pending(tmp_path, capsys):
    canonical = tmp_path / "data" / "toilets.json.gz"
    raw_file = tmp_path / "batch" / "raw_data.json"
    _write_canonical(canonical, [])
    _write_jsonl(raw_file, [_raw_record("pending", "新規トイレ")])

    exit_code = main(
        [
            "--root",
            str(tmp_path),
            "--canonical",
            "data/toilets.json.gz",
            "--json",
            "--fail-on-pending",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["totals"]["pending_records"] == 1
    assert payload["files_with_pending"] == [str(raw_file)]


def test_cli_handles_clean_checkout_without_raw_files(tmp_path, capsys):
    canonical = tmp_path / "data" / "toilets.json.gz"
    _write_canonical(canonical, [])

    assert main(["--root", str(tmp_path), "--canonical", "data/toilets.json.gz"]) == 0
    assert "No raw files matched" in capsys.readouterr().out


def test_load_canonical_plain_json_skips_non_objects_and_rejects_invalid_shape(tmp_path):
    canonical = tmp_path / "toilets.json"
    canonical.write_text(
        json.dumps(
            {
                "toilets": [
                    {
                        "source_id": "place_id:existing",
                        "title": "既存トイレ",
                        "address": "東京都千代田区",
                        "lat": 35.68,
                        "lng": 139.76,
                    },
                    "invalid",
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    aliases, records = load_canonical_aliases(canonical)

    assert records == 1
    assert "place_id:existing" in aliases

    canonical.write_text(json.dumps({"toilets": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="toilets list"):
        load_canonical_aliases(canonical)


def test_processing_errors_are_counted_as_rejected(tmp_path, monkeypatch):
    raw_file = tmp_path / "raw.json"
    _write_jsonl(raw_file, [_raw_record("broken", "壊れたトイレ")])

    def raise_invalid(_record):
        raise ValueError("invalid")

    monkeypatch.setattr(inventory_raw_data, "process_place", raise_invalid)

    result = inventory_raw_file(raw_file, set(), set())

    assert result.valid_objects == 1
    assert result.rejected_records == 1
    assert result.pending_records == 0


def test_cli_human_output_marks_pending_file(tmp_path, capsys):
    canonical = tmp_path / "data" / "toilets.json.gz"
    raw_file = tmp_path / "batch" / "raw_data.json"
    _write_canonical(canonical, [])
    _write_jsonl(raw_file, [_raw_record("pending", "新規トイレ")])

    assert main(["--root", str(tmp_path), "--canonical", "data/toilets.json.gz"]) == 0

    output = capsys.readouterr().out
    assert f"[PENDING] {raw_file}" in output
    assert "pending=1" in output


def test_cli_reports_invalid_canonical_snapshot(tmp_path):
    canonical = tmp_path / "data" / "toilets.json.gz"
    canonical.parent.mkdir(parents=True)
    with gzip.open(canonical, "wt", encoding="utf-8") as file:
        json.dump({"toilets": {}}, file)

    with pytest.raises(SystemExit, match="Could not inventory raw data"):
        main(["--root", str(tmp_path), "--canonical", "data/toilets.json.gz"])
