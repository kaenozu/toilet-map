"""OSM adapter contract tests without network access."""

from __future__ import annotations

import json

from app.osm_provider import OsmOverpassProvider
from app.providers import OSM_REGIONS, FetchRequest, SourceType, VerificationStatus


def test_osm_provider_discovers_and_normalizes_bounded_records() -> None:
    payload = {
        "elements": [
            {
                "type": "node",
                "id": 42,
                "lat": 36.14,
                "lon": 139.39,
                "tags": {
                    "amenity": "toilets",
                    "name": "熊谷中央公園トイレ",
                    "wheelchair": "yes",
                    "changing_table": "yes",
                    "opening_hours": "24/7",
                },
            }
        ]
    }
    provider = OsmOverpassProvider(opener=lambda request, timeout: json.dumps(payload).encode())
    region = OSM_REGIONS["saitama"]
    records = list(provider.discover(FetchRequest(bbox=region.bbox)))
    assert records[0].external_id == "node/42"
    observation = provider.normalize(records[0])
    assert observation is not None
    assert observation.name == "熊谷中央公園トイレ"
    assert observation.attributes["wheelchair"] == "yes"
    assert observation.verification_status is VerificationStatus.AUTOMATICALLY_VERIFIED
    assert provider.provenance().source_type is SourceType.OPENSTREETMAP


def test_osm_provider_requires_a_bbox() -> None:
    provider = OsmOverpassProvider(opener=lambda request, timeout: b"{}")
    try:
        list(provider.discover(FetchRequest()))
    except ValueError as exc:
        assert "bbox" in str(exc)
    else:
        raise AssertionError("unbounded Overpass discovery must be rejected")
