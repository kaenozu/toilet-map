"""Inventory ignored v1 raw scrape files against the canonical snapshot."""

from __future__ import annotations

import argparse
import glob
import gzip
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast

from batch.identity import build_fallback_source_id, build_source_id
from batch.process_data import process_place
from batch.scoring import PlaceDict

DEFAULT_CANONICAL_PATH = Path("data/toilets.json.gz")
DEFAULT_RAW_PATTERNS = (
    "batch/raw_data.json",
    "batch/raw_data_*.json",
    "batch/raw_parts/**/*.json",
    "batch/raw_parts/**/*.jsonl",
    "batch/raw_parts_*/**/*.json",
    "batch/raw_parts_*/**/*.jsonl",
    "batch/*_raw.json",
)


@dataclass(frozen=True)
class FileInventory:
    path: str
    nonempty_lines: int
    valid_objects: int
    published_records: int
    pending_records: int
    duplicate_records: int
    rejected_records: int
    malformed_records: int


def _record_aliases(record: Mapping[str, object]) -> set[str]:
    return {build_source_id(record), build_fallback_source_id(record)}


def load_canonical_aliases(path: str | Path) -> tuple[set[str], int]:
    """Load canonical identities without exposing or rewriting snapshot contents."""
    canonical_path = Path(path)
    if canonical_path.suffix == ".gz":
        with gzip.open(canonical_path, "rt", encoding="utf-8") as file:
            payload = json.load(file)
    else:
        with canonical_path.open(encoding="utf-8") as file:
            payload = json.load(file)
    toilets = payload.get("toilets") if isinstance(payload, dict) else None
    if not isinstance(toilets, list):
        raise ValueError("canonical snapshot must contain a toilets list")

    aliases: set[str] = set()
    valid_records = 0
    for record in toilets:
        if not isinstance(record, dict):
            continue
        aliases.update(_record_aliases(record))
        valid_records += 1
    return aliases, valid_records


def discover_raw_files(root: str | Path = ".", patterns: Sequence[str] = DEFAULT_RAW_PATTERNS) -> list[Path]:
    """Resolve ignored raw-data glob patterns to a stable, duplicate-free file list."""
    root_path = Path(root)
    found: dict[str, Path] = {}
    for pattern in patterns:
        raw_pattern = Path(pattern)
        search_pattern = raw_pattern if raw_pattern.is_absolute() else root_path / raw_pattern
        for match in glob.glob(str(search_pattern), recursive=True):
            path = Path(match)
            if path.is_file():
                found[str(path.resolve())] = path
    return sorted(found.values(), key=lambda path: path.as_posix())


def inventory_raw_file(
    path: str | Path,
    canonical_aliases: set[str],
    seen_raw_aliases: set[str],
) -> FileInventory:
    """Classify one JSONL file using the current v1 processing and identity rules."""
    raw_path = Path(path)
    counts = {
        "nonempty_lines": 0,
        "valid_objects": 0,
        "published_records": 0,
        "pending_records": 0,
        "duplicate_records": 0,
        "rejected_records": 0,
        "malformed_records": 0,
    }
    with raw_path.open(encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            counts["nonempty_lines"] += 1
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                counts["malformed_records"] += 1
                continue
            if not isinstance(value, dict):
                counts["malformed_records"] += 1
                continue
            counts["valid_objects"] += 1
            try:
                processed = process_place(cast(PlaceDict, value))
            except (TypeError, ValueError, OverflowError):
                processed = None
            if processed is None:
                counts["rejected_records"] += 1
                continue

            aliases = _record_aliases(processed)
            if aliases & seen_raw_aliases:
                counts["duplicate_records"] += 1
                continue
            seen_raw_aliases.update(aliases)
            if aliases & canonical_aliases:
                counts["published_records"] += 1
            else:
                counts["pending_records"] += 1

    return FileInventory(
        path=str(raw_path),
        nonempty_lines=counts["nonempty_lines"],
        valid_objects=counts["valid_objects"],
        published_records=counts["published_records"],
        pending_records=counts["pending_records"],
        duplicate_records=counts["duplicate_records"],
        rejected_records=counts["rejected_records"],
        malformed_records=counts["malformed_records"],
    )


def evaluate_inventory(
    canonical_path: str | Path,
    raw_files: Sequence[str | Path],
) -> dict[str, object]:
    """Return a machine-readable inventory without changing raw or canonical files."""
    canonical_aliases, canonical_records = load_canonical_aliases(canonical_path)
    seen_raw_aliases: set[str] = set()
    files = [inventory_raw_file(path, canonical_aliases, seen_raw_aliases) for path in raw_files]
    total_fields = (
        "nonempty_lines",
        "valid_objects",
        "published_records",
        "pending_records",
        "duplicate_records",
        "rejected_records",
        "malformed_records",
    )
    totals = {field: sum(getattr(item, field) for item in files) for field in total_fields}
    return {
        "canonical": str(canonical_path),
        "canonical_records": canonical_records,
        "raw_file_count": len(files),
        "files_with_pending": [item.path for item in files if item.pending_records],
        "totals": totals,
        "files": [asdict(item) for item in files],
    }


def _print_human(report: dict[str, object]) -> None:
    totals = report["totals"]
    assert isinstance(totals, dict)
    print(f"Canonical: {report['canonical']} ({report['canonical_records']} records)")
    print(f"Raw files: {report['raw_file_count']}")
    print(
        "Summary: "
        f"pending={totals['pending_records']}, published={totals['published_records']}, "
        f"duplicates={totals['duplicate_records']}, rejected={totals['rejected_records']}, "
        f"malformed={totals['malformed_records']}"
    )
    files = report["files"]
    assert isinstance(files, list)
    if not files:
        print("No raw files matched the configured patterns.")
    for item in files:
        assert isinstance(item, dict)
        state = "PENDING" if item["pending_records"] else "covered"
        print(
            f"[{state}] {item['path']}: pending={item['pending_records']}, "
            f"published={item['published_records']}, duplicates={item['duplicate_records']}, "
            f"rejected={item['rejected_records']}, malformed={item['malformed_records']}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inventory ignored v1 raw scrape files against the canonical JSON snapshot."
    )
    parser.add_argument("--root", type=Path, default=Path("."), help="Repository root")
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL_PATH, help="Canonical JSON or JSON.gz")
    parser.add_argument(
        "--pattern",
        action="append",
        dest="patterns",
        help="Raw-file glob relative to --root; repeatable (defaults cover raw_data and raw_parts)",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--fail-on-pending", action="store_true", help="Return exit code 2 when pending records exist")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    canonical = args.canonical if args.canonical.is_absolute() else args.root / args.canonical
    patterns = tuple(args.patterns) if args.patterns else DEFAULT_RAW_PATTERNS
    raw_files = discover_raw_files(args.root, patterns)
    try:
        report = evaluate_inventory(canonical, raw_files)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not inventory raw data: {exc}") from exc
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_human(report)
    totals = report["totals"]
    assert isinstance(totals, dict)
    return 2 if args.fail_on_pending and totals["pending_records"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
