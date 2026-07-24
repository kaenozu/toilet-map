"""
tests/test_data_quality.py
ui/data_quality.py のユニットテスト
"""
from ui.data_quality import _calc_missing_stats, _format_missing_metric, render_data_quality


class TestCalcMissingStats:
    def test_empty_list(self):
        result = _calc_missing_stats([])
        assert result == {"total": 0, "no_score": 0, "no_address": 0, "no_prefecture": 0, "no_reviews": 0}

    def test_all_missing(self):
        toilets = [
            {"toilet_score": None, "address": "", "prefecture": "", "toilet_review_count": 0},
            {"toilet_score": None, "address": "  ", "prefecture": None, "toilet_review_count": 0},
        ]
        result = _calc_missing_stats(toilets)
        assert result["total"] == 2
        assert result["no_score"] == 2
        assert result["no_address"] == 2
        assert result["no_prefecture"] == 2
        assert result["no_reviews"] == 2

    def test_all_valid(self):
        toilets = [
            {"toilet_score": 80, "address": "東京都", "prefecture": "東京都", "toilet_review_count": 5},
            {"toilet_score": 60, "address": "大阪府", "prefecture": "大阪府", "toilet_review_count": 3},
        ]
        result = _calc_missing_stats(toilets)
        assert result["total"] == 2
        assert result["no_score"] == 0
        assert result["no_address"] == 0
        assert result["no_prefecture"] == 0
        assert result["no_reviews"] == 0

    def test_mixed(self):
        toilets = [
            {"toilet_score": 80, "address": "東京都", "prefecture": "東京都", "toilet_review_count": 5},
            {"toilet_score": None, "address": "", "prefecture": "東京都", "toilet_review_count": 0},
            {"toilet_score": 60, "address": "大阪府", "prefecture": "", "toilet_review_count": 1},
        ]
        result = _calc_missing_stats(toilets)
        assert result["total"] == 3
        assert result["no_score"] == 1
        assert result["no_address"] == 1
        assert result["no_prefecture"] == 1
        assert result["no_reviews"] == 1

    def test_missing_keys_in_dict(self):
        toilets = [{}, {"toilet_score": 80}]
        result = _calc_missing_stats(toilets)
        assert result["total"] == 2
        assert result["no_score"] == 1
        assert result["no_address"] >= 1


class TestFormatMissingMetric:
    def test_formats_count_and_rate(self):
        assert _format_missing_metric(1, 4) == "1 (25.0%)"

    def test_zero_total_marks_rate_unavailable(self):
        assert _format_missing_metric(0, 0) == "0 (—)"

    def test_invalid_or_negative_values_are_safe(self):
        assert _format_missing_metric("invalid", -1) == "0 (—)"


class TestRenderDataQuality:
    def test_empty_toilets(self, monkeypatch):
        _mock_streamlit(monkeypatch)
        render_data_quality({}, [], _t_dict())

    def test_with_valid_toilets(self, monkeypatch):
        _mock_streamlit(monkeypatch)
        toilets = [
            {"toilet_score": 80, "address": "東京都渋谷区", "prefecture": "東京都", "toilet_review_count": 5},
            {"toilet_score": 60, "address": "大阪府大阪市", "prefecture": "大阪府", "toilet_review_count": 3},
        ]
        render_data_quality({"total": 2}, toilets, _t_dict())

    def test_with_missing_data(self, monkeypatch):
        _mock_streamlit(monkeypatch)
        toilets = [
            {"toilet_score": None, "address": "", "prefecture": "", "toilet_review_count": 0},
        ]
        render_data_quality({}, toilets, _t_dict())

    def test_with_meta_freshness(self, monkeypatch):
        _mock_streamlit(monkeypatch)
        meta = {"last_updated": "2024-01-15", "db_synced_at": "2024-01-15 12:00"}
        render_data_quality(meta, [], _t_dict())

    def test_prefecture_counts_generates_bar_chart(self, monkeypatch):
        _mock_streamlit(monkeypatch)
        toilets = [
            {"toilet_score": 80, "address": "A", "prefecture": "東京都", "toilet_review_count": 1},
            {"toilet_score": 70, "address": "B", "prefecture": "大阪府", "toilet_review_count": 1},
            {"toilet_score": 90, "address": "C", "prefecture": "東京都", "toilet_review_count": 1},
        ]
        render_data_quality({}, toilets, _t_dict())

    def test_score_distribution_generates_bar_chart(self, monkeypatch):
        _mock_streamlit(monkeypatch)
        toilets = [
            {"toilet_score": 85, "address": "A", "prefecture": "東京都", "toilet_review_count": 1},
            {"toilet_score": 55, "address": "B", "prefecture": "大阪府", "toilet_review_count": 1},
            {"toilet_score": 25, "address": "C", "prefecture": "埼玉県", "toilet_review_count": 1},
        ]
        render_data_quality({}, toilets, _t_dict())

    def test_uses_provided_translations(self, monkeypatch):
        _mock_streamlit(monkeypatch)
        t = {"data_quality": "DQ", "dq_total": "Tot", "dq_missing_score": "NoScore",
             "dq_missing_address": "NoAddr", "dq_missing_prefecture": "NoPref", "dq_missing_reviews": "NoRev",
             "dq_score_dist": "Dist", "freshness": "Fresh"}
        render_data_quality({"db_synced_at": "now"}, [], t)

    def test_renders_prefecture_missing_count_and_rate(self, monkeypatch):
        metric_calls = _mock_streamlit(monkeypatch)
        summary = {
            "missing": {"total": 4, "no_score": 2, "no_address": 1, "no_prefecture": 1, "no_reviews": 3},
            "pref_counts": {},
            "score_bins": [],
        }

        render_data_quality({}, summary, _t_dict())

        assert ("No Pref", "1 (25.0%)") in metric_calls
        assert ("No Score", "2 (50.0%)") in metric_calls

    def test_meta_freshness_falls_back_to_db_synced_at(self, monkeypatch):
        _mock_streamlit(monkeypatch)
        render_data_quality({"db_synced_at": "2024-06-01"}, [], _t_dict())

    def test_meta_freshness_na_when_both_missing(self, monkeypatch):
        _mock_streamlit(monkeypatch)
        render_data_quality({}, [], _t_dict())


def _t_dict():
    return {"data_quality": "📊", "dq_total": "Total", "dq_missing_score": "No Score",
            "dq_missing_address": "No Addr", "dq_missing_prefecture": "No Pref", "dq_missing_reviews": "No Rev",
            "dq_score_dist": "Dist", "freshness": "Fresh"}


class _NullContext:
    def __enter__(self): return self
    def __exit__(self, *a): pass


def _mock_streamlit(monkeypatch):
    import streamlit as st
    metric_calls = []
    monkeypatch.setattr(st, "expander", lambda *a, **kw: _NullContext())
    monkeypatch.setattr(st, "columns", lambda n: [_NullContext() for _ in range(n)])
    monkeypatch.setattr(st, "metric", lambda label, value, *a, **kw: metric_calls.append((label, value)))
    monkeypatch.setattr(st, "bar_chart", lambda *a, **kw: None)
    monkeypatch.setattr(st, "subheader", lambda *a: None)
    monkeypatch.setattr(st, "caption", lambda *a: None)
    return metric_calls
