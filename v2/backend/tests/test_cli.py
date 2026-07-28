import pytest

from app.cli import _parser, _summarize_ingest_results
from app.providers import OSM_REGIONS


def test_parser_has_ingest_osm_all() -> None:
    parsed = _parser().parse_args(["ingest-osm-all"])
    assert parsed.command == "ingest-osm-all"


def test_parser_accepts_delay() -> None:
    parsed = _parser().parse_args(["ingest-osm-all", "--delay", "2.5"])
    assert parsed.delay == 2.5


def test_parser_rejects_negative_delay() -> None:
    with pytest.raises(SystemExit):
        _parser().parse_args(["ingest-osm-all", "--delay", "-0.1"])


def test_parser_accepts_from_region() -> None:
    parsed = _parser().parse_args(["ingest-osm-all", "--from-region", "tokyo"])
    assert parsed.from_region == "tokyo"


def test_parser_rejects_invalid_from_region() -> None:
    with pytest.raises(SystemExit):
        _parser().parse_args(["ingest-osm-all", "--from-region", "nonexistent"])


def test_ingest_osm_all_from_region_matches_key() -> None:
    first = sorted(OSM_REGIONS)[0]
    assert first in OSM_REGIONS
    parsed = _parser().parse_args(["ingest-osm-all", "--from-region", first])
    assert parsed.from_region == first


def test_ingest_summary_counts_skipped_separately_from_failed() -> None:
    summary = _summarize_ingest_results(
        {
            "aichi": {"status": "skipped"},
            "akita": {"status": "succeeded", "inserted": 12, "reused": 3},
            "aomori": {"status": "failed", "error": "timeout"},
        }
    )

    assert summary == {
        "total_inserted": 12,
        "total_reused": 3,
        "regions_succeeded": 1,
        "regions_failed": 1,
        "regions_skipped": 1,
    }
