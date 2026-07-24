"""Focused tests for the concise data-quality summary."""

from ui.data_quality import build_data_quality_summary


def test_empty_summary_is_omitted():
    assert build_data_quality_summary({}, {"scored": "Scored"}) is None


def test_complete_dataset_reports_full_coverage():
    summary = build_data_quality_summary(
        {"total": 4, "no_score": 0, "no_address": 0, "no_prefecture": 0},
        {"scored": "Scored"},
    )

    assert summary == "Scored: 4/4 (100%) · 未採点 / Unscored: 0."


def test_unscored_records_are_explained_as_neutral():
    summary = build_data_quality_summary(
        {"total": 3, "no_score": 1, "no_address": 0, "no_prefecture": 0},
        {"scored": "スコア算出"},
    )

    assert summary is not None
    assert "スコア算出: 2/3 (67%)" in summary
    assert "未採点 / Unscored: 1" in summary
    assert "未採点は低評価ではありません" in summary


def test_location_gaps_warn_about_search_accuracy():
    summary = build_data_quality_summary(
        {"total": 10, "no_score": 2, "no_address": 1, "no_prefecture": 3},
        {"scored": "Scored"},
    )

    assert summary is not None
    assert "Missing address: 1" in summary
    assert "Missing prefecture: 3" in summary
    assert "Missing location fields may affect search and aggregation accuracy" in summary


def test_inconsistent_or_invalid_counts_are_safely_clamped():
    summary = build_data_quality_summary(
        {"total": "2", "no_score": 99, "no_address": -1, "no_prefecture": "invalid"},
        {"scored": "Scored"},
    )

    assert summary == (
        "Scored: 0/2 (0%) · 未採点 / Unscored: 2. "
        "未採点は低評価ではありません / Unscored does not mean a low rating."
    )
