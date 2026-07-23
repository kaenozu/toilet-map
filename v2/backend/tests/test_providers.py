import json
from pathlib import Path

from app.providers import FetchRequest, JsonlProvider, SourceType, VerificationStatus


def test_jsonl_provider_separates_discovery_and_normalization(tmp_path: Path) -> None:
    fixture = tmp_path / "places.jsonl"
    fixture.write_text(
        json.dumps(
            {
                "place_id": "abc",
                "title": "中央公園トイレ",
                "address": "埼玉県熊谷市中央",
                "latitude": 36.1,
                "longitude": 139.4,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    provider = JsonlProvider(fixture)

    records = list(provider.discover(FetchRequest(prefecture="埼玉県")))
    assert len(records) == 1
    observation = provider.normalize(records[0])
    assert observation is not None
    assert observation.external_id == "abc"
    assert observation.name == "中央公園トイレ"
    assert observation.confidence == 0.6


def test_jsonl_provider_declares_provenance(tmp_path: Path) -> None:
    provider = JsonlProvider(tmp_path / "unused.jsonl")
    provenance = provider.provenance()
    assert provenance.source_type is SourceType.GOOGLE_MAPS
    assert provenance.verification_status is VerificationStatus.UNVERIFIED
