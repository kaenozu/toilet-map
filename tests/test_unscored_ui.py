"""Regression coverage for nullable score and confidence values in the v1 UI."""

import math

from ui.components import build_toilet_card_html
from ui.helpers import format_score, get_confidence_percentage, get_score_style
from ui.popups import build_popup_html


def _unscored_toilet() -> dict:
    return {
        "title": "未採点施設",
        "category": "公園",
        "address": "埼玉県熊谷市",
        "toilet_score": None,
        "confidence": None,
        "toilet_review_count": 0,
        "is_public_toilet": True,
        "rating": None,
        "review_count": 0,
        "top_keywords": [],
        "sample_reviews": [],
    }


def test_nullable_numeric_helpers_use_neutral_display():
    assert format_score(None) == "—"
    assert format_score(float("nan")) == "—"
    assert get_confidence_percentage(None) is None
    assert get_confidence_percentage(math.inf) is None
    assert get_confidence_percentage(1.5) == 100
    assert get_score_style(None) == ("#6b7280", "○", "未採点 / Unscored")


def test_unscored_list_card_is_rendered_without_numeric_formatting():
    html = build_toilet_card_html(_unscored_toilet())

    assert 'aria-label="未採点施設 - 未採点"' in html
    assert "信頼度 —" in html
    assert "未採点施設" in html


def test_unscored_map_popup_explains_missing_score():
    html = build_popup_html(_unscored_toilet())

    assert "未採点 / Unscored" in html
    assert "信頼度 —" in html
    assert "採点結果なし" in html
    assert "現在は未採点です" in html
