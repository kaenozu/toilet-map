"""
tests/test_stats.py
ui/stats.py のユニットテスト
"""
import pytest

from ui.stats import calc_avg_score, calc_score_distribution, render_score_distribution


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

    def test_mixed_scores(self):
        toilets = [
            {"toilet_score": 100},
            {"toilet_score": 50},
            {"toilet_score": 0},
        ]
        assert calc_avg_score(toilets) == pytest.approx(75.0)


class TestCalcScoreDistribution:
    def test_empty_list(self):
        assert calc_score_distribution([]) == []

    def test_all_zero(self):
        assert calc_score_distribution([{"toilet_score": 0}]) == []

    def test_returns_expected_ranges(self):
        toilets = [
            {"toilet_score": 90},
            {"toilet_score": 70},
            {"toilet_score": 55},
            {"toilet_score": 40},
            {"toilet_score": 20},
        ]
        dist = calc_score_distribution(toilets)
        assert len(dist) == 5
        assert "✨" in dist[0]["label"]
        assert dist[0]["count"] == 1


class TestRenderScoreDistribution:
    def test_empty_list(self):
        render_score_distribution([])

    def test_all_zero_scores(self):
        render_score_distribution([{"toilet_score": 0}, {"toilet_score": 0}])

    def test_mixed_distribution(self):
        toilets = [
            {"toilet_score": 90},
            {"toilet_score": 70},
            {"toilet_score": 55},
            {"toilet_score": 40},
            {"toilet_score": 20},
        ]
        render_score_distribution(toilets)

    def test_boundary_scores(self):
        """スコア境界値の分布テスト"""
        toilets = [
            {"toilet_score": 100},  # 80-100
            {"toilet_score": 80},   # 80-100
            {"toilet_score": 79},   # 65-79
            {"toilet_score": 65},   # 65-79
            {"toilet_score": 64},   # 50-64
            {"toilet_score": 50},   # 50-64
            {"toilet_score": 49},   # 35-49
            {"toilet_score": 35},   # 35-49
            {"toilet_score": 34},   # 0-34
            {"toilet_score": 0},    # 0-34
        ]
        render_score_distribution(toilets)


class TestCalcAvgScoreEdgeCases:
    def test_negative_scores_excluded(self):
        """負のスコアは除外される"""
        toilets = [
            {"toilet_score": 80},
            {"toilet_score": -5},
            {"toilet_score": 0},
        ]
        assert calc_avg_score(toilets) == pytest.approx(80.0)

    def test_large_dataset(self):
        """大規模データセットのテスト"""
        toilets = [{"toilet_score": 50 + i} for i in range(100)]
        avg = calc_avg_score(toilets)
        assert avg > 0
        assert avg < 150


class TestRenderStats:
    def test_empty_data(self, monkeypatch):
        from ui.stats import render_stats
        _mock_streamlit(monkeypatch)
        render_stats({"total": 0, "scored": 0, "public_toilets": 0}, [], {"stats": "📊", "stats_all": "All",
                                                                           "total": "Total", "scored": "Scored",
                                                                           "public": "Public", "avg_score": "Avg"})

    def test_with_data(self, monkeypatch):
        from ui.stats import render_stats
        _mock_streamlit(monkeypatch)
        toilets = [{"toilet_score": 80}, {"toilet_score": 60}, {"toilet_score": 90}]
        render_stats({"total": 3, "scored": 3, "public_toilets": 1}, toilets,
                      {"stats": "📊", "stats_all": "All", "total": "Total",
                       "scored": "Scored", "public": "Public", "avg_score": "Avg"})

    def test_boundary_scores(self, monkeypatch):
        from ui.stats import render_stats
        _mock_streamlit(monkeypatch)
        toilets = [
            {"toilet_score": 100}, {"toilet_score": 80},
            {"toilet_score": 79}, {"toilet_score": 65},
            {"toilet_score": 64}, {"toilet_score": 50},
            {"toilet_score": 49}, {"toilet_score": 35},
            {"toilet_score": 34}, {"toilet_score": 0},
        ]
        render_stats({"total": 10, "scored": 10, "public_toilets": 5}, toilets,
                      {"stats": "📊", "stats_all": "All", "total": "Total",
                       "scored": "Scored", "public": "Public", "avg_score": "Avg"})


def _mock_streamlit(monkeypatch):
    import streamlit as st
    monkeypatch.setattr(st, "expander", lambda *a, **kw: _NullContext())
    monkeypatch.setattr(st, "columns", lambda n: [_NullContext() for _ in range(n)])
    monkeypatch.setattr(st, "metric", lambda *a, **kw: None)
    monkeypatch.setattr(st, "altair_chart", lambda *a, **kw: None)
    monkeypatch.setattr(st, "subheader", lambda *a: None)
    monkeypatch.setattr(st, "bar_chart", lambda *a, **kw: None)


class _NullContext:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
