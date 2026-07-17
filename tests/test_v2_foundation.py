import pytest

from toilet_map_v2.domain import ScoreStatus, ToiletRecord
from toilet_map_v2.identifiers import build_place_id, build_review_id


def test_place_id_prefers_upstream_id() -> None:
    first = build_place_id(
        source="google",
        source_place_id="abc",
        title="A",
        address=None,
        latitude=1,
        longitude=2,
    )
    second = build_place_id(
        source="google",
        source_place_id="abc",
        title="B",
        address="changed",
        latitude=3,
        longitude=4,
    )
    assert first == second


def test_place_id_fallback_is_deterministic() -> None:
    first = build_place_id(
        source="google",
        source_place_id=None,
        title=" 公園 ",
        address="埼玉県",
        latitude=36.1,
        longitude=139.3,
    )
    second = build_place_id(
        source="google",
        source_place_id=None,
        title="公園",
        address="埼玉県",
        latitude=36.1,
        longitude=139.3,
    )
    assert first == second


def test_review_id_prefers_source_id() -> None:
    first = build_review_id(
        "place",
        source_review_id="review-1",
        content_hash="old-content",
    )
    second = build_review_id(
        "place",
        source_review_id="review-1",
        content_hash="new-content",
    )
    assert first == second


def test_unrated_record_cannot_have_score() -> None:
    with pytest.raises(ValueError):
        ToiletRecord(
            id="t",
            place_id="p",
            title="x",
            category=None,
            address=None,
            latitude=35,
            longitude=139,
            score=50,
            confidence=0,
            review_count=0,
            score_status=ScoreStatus.UNRATED,
            scoring_version="v1",
        )
