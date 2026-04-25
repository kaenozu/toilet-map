"""
tests/test_ui_components.py
ui/components.py のユニットテスト
"""
import pytest
from app_config import get_score_style, esc


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])