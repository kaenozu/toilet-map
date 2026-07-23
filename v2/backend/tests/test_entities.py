from app.entities import canonical_facility_key, payload_hash, source_type_from_provider
from app.providers import SourceType


def test_payload_hash_is_stable_across_key_order() -> None:
    assert payload_hash({"name": "A", "lat": 35}) == payload_hash({"lat": 35, "name": "A"})


def test_legacy_facility_key_preserves_existing_stable_key() -> None:
    assert canonical_facility_key(SourceType.LEGACY, "legacy-json", "abc") == "legacy:abc"


def test_source_type_classification() -> None:
    assert source_type_from_provider("openstreetmap-overpass") is SourceType.OPENSTREETMAP
    assert source_type_from_provider("google-maps-jsonl") is SourceType.GOOGLE_MAPS
    assert source_type_from_provider("city-open-data") is SourceType.MUNICIPALITY_OPEN_DATA
