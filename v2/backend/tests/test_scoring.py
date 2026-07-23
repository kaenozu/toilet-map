from app.importer import normalized_records
from app.scoring import ScoreDimension, score_review_dimensions, score_reviews


def test_scoring_keeps_unrelated_reviews_unscored() -> None:
    result = score_reviews(["駅から近いです"])
    assert result.score is None
    assert result.confidence == 0.0


def test_scoring_detects_cleanliness_signal() -> None:
    result = score_reviews(["トイレがとても清潔で綺麗", "清掃されている"])
    assert result.score is not None
    assert result.score > 50
    assert result.matched_reviews == 2


def test_multidimensional_scoring_keeps_evidence_separate() -> None:
    results = score_review_dimensions(["清潔で、おむつ台と車椅子用の手すりがあります"])
    assert results[ScoreDimension.CLEANLINESS].score is not None
    assert results[ScoreDimension.ACCESSIBILITY].score is not None
    assert results[ScoreDimension.CHILD_FRIENDLINESS].score is not None
    assert results[ScoreDimension.CONGESTION].score is None


def test_legacy_normalization_rejects_missing_coordinates() -> None:
    records = list(normalized_records([{"name": "invalid"}]))
    assert records == []


def test_legacy_normalization_accepts_common_keys() -> None:
    records = list(
        normalized_records(
            [{"place_id": "abc", "name": "公園", "lat": 35.0, "lng": 139.0, "score": 80}]
        )
    )
    assert records[0]["stable_key"] == "abc"
    assert records[0]["toilet_score"] == 80
