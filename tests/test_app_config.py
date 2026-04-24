"""
tests/test_app_config.py
app_config.py のユニットテスト
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app_config import (
    get_score_style,
    esc,
    SCORE_RANGES,
    FILTER_CONFIG,
    PREFECTURE_CENTERS,
)


class TestGetScoreStyle:
    def test_very_clean(self):
        color, emoji, label = get_score_style(95)
        assert emoji == "✨"
        assert label == "とてもきれい"
        assert color == "#27ae60"

    def test_clean(self):
        color, emoji, label = get_score_style(70)
        assert emoji == "😊"
        assert label == "きれい"

    def test_normal(self):
        color, emoji, label = get_score_style(55)
        assert emoji == "😐"
        assert label == "普通"

    def test_slightly_dirty(self):
        color, emoji, label = get_score_style(40)
        assert emoji == "😨"
        assert label == "少し気になる"

    def test_dirty(self):
        color, emoji, label = get_score_style(20)
        assert emoji == "💩"
        assert label == "要注意"

    def test_boundary_80(self):
        color, emoji, label = get_score_style(80)
        assert emoji == "✨"

    def test_boundary_65(self):
        color, emoji, label = get_score_style(65)
        assert emoji == "😊"

    def test_boundary_50(self):
        color, emoji, label = get_score_style(50)
        assert emoji == "😐"

    def test_boundary_35(self):
        color, emoji, label = get_score_style(35)
        assert emoji == "😨"

    def test_boundary_0(self):
        color, emoji, label = get_score_style(0)
        assert emoji == "💩"


class TestEsc:
    def test_esc_html_chars(self):
        assert esc("<script>") == "&lt;script&gt;"

    def test_esc_quote(self):
        assert esc('say "hi"') == "say &quot;hi&quot;"

    def test_esc_amp(self):
        assert esc("A & B") == "A &amp; B"

    def test_esc_none(self):
        assert esc(None) == ""

    def test_esc_empty(self):
        assert esc("") == ""

    def test_esc_number(self):
        assert esc(123) == "123"


class TestFilterConfig:
    def test_has_all_key(self):
        assert "すべて" in FILTER_CONFIG
        assert FILTER_CONFIG["すべて"] is None

    def test_has_public_key(self):
        assert "公共トイレ" in FILTER_CONFIG
        assert FILTER_CONFIG["公共トイレ"] == "__public__"

    def test_cafe_pattern(self):
        assert "カフェ・飲食" in FILTER_CONFIG
        pat = FILTER_CONFIG["カフェ・飲食"]
        assert "カフェ" in pat and "レストラン" in pat

    def test_store_pattern(self):
        assert "コンビニ・店舗" in FILTER_CONFIG
        pat = FILTER_CONFIG["コンビニ・店舗"]
        assert "コンビニ" in pat and "スーパー" in pat


class TestPrefectureCenters:
    def test_all_kanto(self):
        expected = {
            "東京都": (35.6762, 139.6503),
            "神奈川県": (35.4475, 139.6423),
            "埼玉県": (35.8574, 139.6489),
            "千葉県": (35.6050, 140.1233),
            "茨城県": (36.3414, 140.4468),
            "栃木県": (36.5657, 139.8836),
            "群馬県": (36.3907, 139.0604),
        }
        for pref, coords in expected.items():
            assert pref in PREFECTURE_CENTERS
            lat, lng = PREFECTURE_CENTERS[pref]
            assert isinstance(lat, float)
            assert isinstance(lng, float)
            assert 30 < lat < 44
            assert 127 < lng < 146


class TestScoreRanges:
    def test_all_ranges_defined(self):
        assert len(SCORE_RANGES) == 5
        thresholds = [r[0] for r in SCORE_RANGES]
        assert thresholds == [80, 65, 50, 35, 0]

    def test_ranges_have_4_elements(self):
        for r in SCORE_RANGES:
            assert len(r) == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])