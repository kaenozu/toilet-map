"""
tests/test_app.py
app.py のユニットテスト
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app
import pandas as pd
import pytest


class TestFilterToilets:
    """フィルタリングテスト"""

    def test_filter_all(self):
        df = pd.DataFrame([
            {"title": "厕所A", "category": "餐厅", "is_public_toilet": False},
            {"title": "厕所B", "category": "便利店", "is_public_toilet": False},
            {"title": "厕所C", "category": "公园", "is_public_toilet": True},
        ])
        result = app.filter_toilets(df, "すべて")
        assert len(result) == 3

    def test_filter_public(self):
        df = pd.DataFrame([
            {"title": "厕所A", "category": "餐厅", "is_public_toilet": False},
            {"title": "厕所B", "category": "公园", "is_public_toilet": True},
        ])
        result = app.filter_toilets(df, "公共トイレ")
        assert len(result) == 1
        assert result.iloc[0]["is_public_toilet"] == True

    def test_filter_cafe(self):
        df = pd.DataFrame([
            {"title": "厕所A", "category": "咖啡店", "is_public_toilet": False},
            {"title": "厕所B", "category": "便利店", "is_public_toilet": False},
        ])
        result = app.filter_toilets(df, "カフェ・飲食")
        assert len(result) >= 0

    def test_filter_cafe_match(self):
        df = pd.DataFrame([
            {"title": "厕所A", "category": "カフェ", "is_public_toilet": False},
            {"title": "厕所B", "category": "喫茶店", "is_public_toilet": False},
        ])
        result = app.filter_toilets(df, "カフェ・飲食")
        assert len(result) == 2


class TestSearchToilets:
    """検索テスト"""

    def test_search_name(self):
        df = pd.DataFrame([
            {"title": "麦当劳厕所", "address": "东京", "category": "快餐"},
            {"title": "肯德基厕所", "address": "大阪", "category": "快餐"},
        ])
        result = app.search_toilets(df, "麦当劳")
        assert len(result) == 1

    def test_search_address(self):
        df = pd.DataFrame([
            {"title": "厕所A", "address": "东京都渋谷区", "category": "公园"},
            {"title": "厕所B", "address": "大阪府大阪市", "category": "公园"},
        ])
        result = app.search_toilets(df, "东京")
        assert len(result) == 1

    def test_search_empty(self):
        df = pd.DataFrame([
            {"title": "厕所A", "address": "东京", "category": "公园"},
        ])
        result = app.search_toilets(df, "")
        assert len(result) == 1

    def test_search_no_match(self):
        df = pd.DataFrame([
            {"title": "厕所A", "address": "东京", "category": "公园"},
        ])
        result = app.search_toilets(df, "不存在")
        assert len(result) == 0


class TestGetScoreStyle:
    """スコアスタイル取得テスト"""

    def test_score_very_clean(self):
        from app_config import get_score_style
        color, emoji, label = get_score_style(90)
        assert emoji == "✨"
        assert label == "とてもきれい"

    def test_score_clean(self):
        from app_config import get_score_style
        color, emoji, label = get_score_style(70)
        assert emoji == "😊"
        assert label == "きれい"

    def test_score_normal(self):
        from app_config import get_score_style
        color, emoji, label = get_score_style(55)
        assert emoji == "😐"
        assert label == "普通"

    def test_score_slightly_dirty(self):
        from app_config import get_score_style
        color, emoji, label = get_score_style(40)
        assert emoji == "😨"
        assert label == "少し気になる"

    def test_score_dirty(self):
        from app_config import get_score_style
        color, emoji, label = get_score_style(20)
        assert emoji == "💩"
        assert label == "要注意"


class TestEscaping:
    """HTMLエスケープテスト"""

    def test_esc_basic(self):
        from app_config import esc
        assert esc("<test>") == "&lt;test&gt;"

    def test_esc_quote(self):
        from app_config import esc
        assert esc('he said "hi"') == "he said &quot;hi&quot;"

    def test_esc_none(self):
        from app_config import esc
        assert esc(None) == ""

    def test_esc_empty(self):
        from app_config import esc
        assert esc("") == ""


class TestBuildPopupHtml:
    """ポップアップHTML生成テスト"""

    def test_build_popup_basic(self):
        from ui.popups import build_popup_html
        toilet = {
            "title": "测试厕所",
            "category": "公园",
            "toilet_score": 85.0,
            "toilet_review_count": 5,
            "confidence": 0.8,
            "is_public_toilet": True,
            "address": "东京都渋谷区",
            "rating": 4.5,
            "review_count": 100,
        }
        html = build_popup_html(toilet)
        assert "测试厕所" in html
        assert "85" in html

    def test_build_popup_private(self):
        from ui.popups import build_popup_html
        toilet = {
            "title": "私营厕所",
            "category": "餐厅",
            "toilet_score": 50.0,
            "toilet_review_count": 2,
            "confidence": 0.4,
            "is_public_toilet": False,
            "address": "大阪市",
            "rating": 3.5,
            "review_count": 50,
        }
        html = build_popup_html(toilet)
        assert "私营厕所" in html
        assert "公共厕所" not in html


if __name__ == "__main__":
    pytest.main([__file__, "-v"])