"""Trust-score behavior tests."""

from datetime import UTC, datetime, timedelta

from app.read_model import TrustInputs, calculate_trust_score

NOW = datetime(2026, 7, 23, tzinfo=UTC)


def test_human_verified_recent_source_has_high_trust() -> None:
    score = calculate_trust_score(
        TrustInputs(0.9, "human_verified", NOW - timedelta(days=2)),
        now=NOW,
    )
    assert score == 90.0


def test_expired_unverified_source_is_heavily_discounted() -> None:
    score = calculate_trust_score(
        TrustInputs(0.8, "unverified", NOW - timedelta(days=200), NOW - timedelta(days=1)),
        now=NOW,
    )
    assert score == 10.4
