"""
tests/test_ui_components.py
ui/components.py のユニットテスト
"""
import pytest
from app_config import get_score_style, esc
from ui.components import build_result_context_text


class TestGetScoreStyle:
    def test_high_score(self):
        color, emoji, label = get_score_style(90)
        assert emoji == "✨"
        assert label == "とてもきれい"

    def test_low_score(self):
        color, emoji, label = get_score_style(10)
        assert emoji == "💩"

    def test_esc_none(self):
        assert esc(None) == ""

    def test_esc_html(self):
        assert esc("<b>test</b>") == "&lt;b&gt;test&lt;/b&gt;"


class TestBuildResultContextText:
    def test_page_limited_results_include_timing(self):
        text = build_result_context_text(120, 120, 120, 3.4, 45.6)
        assert "一覧 120件" in text
        assert "地図 120件" in text
        assert "絞り込み 3ms" in text
        assert "地図 46ms" in text

    def test_full_results_without_timing_stays_compact(self):
        text = build_result_context_text(10, 10, 10)
        assert "一覧 10件" in text
        assert "地図 10件" in text
        assert "絞り込み" not in text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])