from app.cli import _parser
from app.providers import OSM_REGIONS


def test_parser_has_ingest_osm_all() -> None:
    parsed = _parser().parse_args(["ingest-osm-all"])
    assert parsed.command == "ingest-osm-all"


def test_parser_accepts_delay() -> None:
    parsed = _parser().parse_args(["ingest-osm-all", "--delay", "2.5"])
    assert parsed.delay == 2.5


def test_parser_accepts_from_region() -> None:
    parsed = _parser().parse_args(["ingest-osm-all", "--from-region", "tokyo"])
    assert parsed.from_region == "tokyo"


def test_parser_rejects_invalid_from_region() -> None:
    parser = _parser()
    try:
        parser.parse_args(["ingest-osm-all", "--from-region", "nonexistent"])
        assert False, "should have raised SystemExit"
    except SystemExit:
        pass


def test_ingest_osm_all_from_region_matches_key() -> None:
    first = sorted(OSM_REGIONS)[0]
    assert first in OSM_REGIONS
    parsed = _parser().parse_args(["ingest-osm-all", "--from-region", first])
    assert parsed.from_region == first
