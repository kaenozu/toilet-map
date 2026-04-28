"""
tests/test_stats.py
ui/stats.py のユニットテスト
"""
import pytest
from ui.stats import calc_avg_score


class TestCalcAvgScore:
    def test_empty_list(self):
        assert calc_avg_score([]) == 0.0

    def test_all_positive(self):
        toilets = [
            {"toilet_score": 80},
            {"toilet_score": 70},
            {"toilet_score": 90},
        ]
        assert calc_avg_score(toilets) == pytest.approx(80.0)

    def test_zero_score_excluded(self):
        toilets = [
            {"toilet_score": 80},
            {"toilet_score": 0},
        ]
        assert calc_avg_score(toilets) == pytest.approx(80.0)

    def test_missing_key(self):
        toilets = [
            {"toilet_score": 60},
            {},
        ]
        assert calc_avg_score(toilets) == pytest.approx(60.0)

    def test_all_zero(self):
        toilets = [{"toilet_score": 0}, {"toilet_score": 0}]
        assert calc_avg_score(toilets) == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
