import json

from app.score_storage import encode_score_basis, score_basis
from app.scoring import DimensionScore, ScoreDimension


def test_score_basis_returns_dict_with_all_keys() -> None:
    result = DimensionScore(ScoreDimension.CLEANLINESS, 75.0, 0.8, 3, 2, 0)
    basis = score_basis(result)
    assert basis == {
        "score": 75.0,
        "confidence": 0.8,
        "evidence_count": 3,
        "positive_matches": 2,
        "negative_matches": 0,
    }


def test_score_basis_handles_none_score() -> None:
    result = DimensionScore(ScoreDimension.ODOR, None, 0.0, 0, 0, 0)
    basis = score_basis(result)
    assert basis["score"] is None
    assert basis["evidence_count"] == 0


def test_score_basis_handles_negative_matches() -> None:
    result = DimensionScore(ScoreDimension.CONGESTION, 30.0, 0.6, 2, 0, 3)
    basis = score_basis(result)
    assert basis["negative_matches"] == 3
    assert basis["score"] == 30.0


def test_encode_score_basis_is_json() -> None:
    result = DimensionScore(ScoreDimension.EQUIPMENT, 60.0, 0.5, 2, 1, 1)
    encoded = encode_score_basis(result)
    parsed = json.loads(encoded)
    assert parsed == {"confidence": 0.5, "evidence_count": 2,
                      "negative_matches": 1, "positive_matches": 1, "score": 60.0}


def test_encode_score_basis_sorts_keys() -> None:
    result = DimensionScore(ScoreDimension.FRESHNESS, 50.0, 0.3, 1, 1, 0)
    encoded = encode_score_basis(result)
    assert encoded.index("confidence") < encoded.index("evidence_count")
