"""Evaluate geographic bias in the v1 initial map marker selection."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

DEFAULT_DB_PATH = Path("data/toilets.db")
DEFAULT_LIMIT = 1500
MISSING_PREFECTURE = "(都道府県未設定)"


@dataclass(frozen=True)
class MapCandidate:
    id: int
    prefecture: str
    priority_index: int


@dataclass(frozen=True)
class SamplingReport:
    strategy: str
    sampled_count: int
    represented_prefectures: int
    coverage_ratio: float
    top_prefecture: str | None
    top_prefecture_share: float
    omitted_prefectures: list[str]
    sampled_by_prefecture: dict[str, int]


def _normalize_prefecture(value: object) -> str:
    prefecture = str(value or "").strip()
    return prefecture or MISSING_PREFECTURE


def load_candidates(connection: sqlite3.Connection) -> list[MapCandidate]:
    """Load valid map candidates in the same priority order as the v1 query."""
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT id, prefecture
        FROM toilets
        WHERE lat BETWEEN -90 AND 90
          AND lng BETWEEN -180 AND 180
        ORDER BY COALESCE(confidence, 0) DESC,
                 COALESCE(review_count, 0) DESC,
                 COALESCE(toilet_review_count, 0) DESC,
                 COALESCE(toilet_score, 0) DESC,
                 id ASC
        """
    ).fetchall()
    return [
        MapCandidate(
            id=int(row["id"]),
            prefecture=_normalize_prefecture(row["prefecture"]),
            priority_index=index,
        )
        for index, row in enumerate(rows)
    ]


def select_current(candidates: Sequence[MapCandidate], limit: int) -> list[MapCandidate]:
    """Reproduce the current global-priority LIMIT behavior."""
    return list(candidates[: max(1, int(limit))])


def select_balanced(candidates: Sequence[MapCandidate], limit: int) -> list[MapCandidate]:
    """Select prefecture representatives by rank, preserving priority within each round."""
    safe_limit = max(1, int(limit))
    buckets: dict[str, list[MapCandidate]] = defaultdict(list)
    for candidate in candidates:
        buckets[candidate.prefecture].append(candidate)

    selected: list[MapCandidate] = []
    rank = 0
    while len(selected) < safe_limit:
        round_candidates = [bucket[rank] for bucket in buckets.values() if rank < len(bucket)]
        if not round_candidates:
            break
        round_candidates.sort(key=lambda candidate: candidate.priority_index)
        selected.extend(round_candidates[: safe_limit - len(selected)])
        rank += 1
    return selected


def _build_report(
    candidates: Sequence[MapCandidate], sampled: Sequence[MapCandidate], strategy: str
) -> SamplingReport:
    all_counts = Counter(candidate.prefecture for candidate in candidates)
    sampled_counts = Counter(candidate.prefecture for candidate in sampled)
    omitted = sorted(
        (prefecture for prefecture in all_counts if prefecture not in sampled_counts),
        key=lambda prefecture: (-all_counts[prefecture], prefecture),
    )
    top_prefecture: str | None = None
    top_share = 0.0
    if sampled_counts:
        top_prefecture, top_count = min(
            sampled_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
        top_share = top_count / len(sampled)
    total_prefectures = len(all_counts)
    coverage_ratio = len(sampled_counts) / total_prefectures if total_prefectures else 1.0
    return SamplingReport(
        strategy=strategy,
        sampled_count=len(sampled),
        represented_prefectures=len(sampled_counts),
        coverage_ratio=coverage_ratio,
        top_prefecture=top_prefecture,
        top_prefecture_share=top_share,
        omitted_prefectures=omitted,
        sampled_by_prefecture=dict(sorted(sampled_counts.items())),
    )


def evaluate_database(db_path: str | Path, limit: int = DEFAULT_LIMIT) -> dict[str, object]:
    """Compare current and prefecture-balanced selection against one SQLite snapshot."""
    path = Path(db_path)
    with sqlite3.connect(path) as connection:
        candidates = load_candidates(connection)

    safe_limit = max(1, int(limit))
    all_prefectures = {candidate.prefecture for candidate in candidates}
    current = select_current(candidates, safe_limit)
    balanced = select_balanced(candidates, safe_limit)
    return {
        "database": str(path),
        "limit": safe_limit,
        "total_valid_coordinates": len(candidates),
        "total_prefectures": len(all_prefectures),
        "current": asdict(_build_report(candidates, current, "current_global_priority")),
        "balanced": asdict(_build_report(candidates, balanced, "prefecture_round_robin")),
    }


def _format_percent(value: object) -> str:
    return f"{float(value) * 100:.1f}%"


def _print_human(report: dict[str, object]) -> None:
    print(f"Database: {report['database']}")
    print(f"Valid coordinates: {report['total_valid_coordinates']}")
    print(f"Prefectures: {report['total_prefectures']}")
    print(f"Marker limit: {report['limit']}")
    for key in ("current", "balanced"):
        item = report[key]
        assert isinstance(item, dict)
        omitted = item["omitted_prefectures"]
        omitted_text = ", ".join(omitted) if omitted else "none"
        print(
            f"{key}: coverage={_format_percent(item['coverage_ratio'])}, "
            f"top-share={_format_percent(item['top_prefecture_share'])}, "
            f"omitted={omitted_text}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare current and prefecture-balanced v1 map marker sampling."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="SQLite snapshot path")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Maximum map markers")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.limit < 1:
        raise SystemExit("--limit must be at least 1")
    try:
        report = evaluate_database(args.db, args.limit)
    except (OSError, sqlite3.Error) as exc:
        raise SystemExit(f"Could not evaluate {args.db}: {exc}") from exc
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
