"""Entity-resolution candidate scoring tests."""

from app.resolution import CandidateMetrics, candidate_score


def test_candidate_score_rewards_name_address_and_distance() -> None:
    strong = candidate_score(CandidateMetrics(20, 0.95, 0.8))
    weak = candidate_score(CandidateMetrics(280, 0.2, 0.1))
    assert strong > 0.85
    assert weak < 0.25


def test_candidate_score_is_bounded() -> None:
    assert candidate_score(CandidateMetrics(0, 2, 2)) == 1.0
    assert candidate_score(CandidateMetrics(1000, -1, -1)) == 0.0
