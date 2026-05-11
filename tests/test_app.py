"""
tests/test_app.py
app.py モジュールのユニットテスト
"""
import pytest
import pandas as pd
from ui.filters import filter_toilets, search_toilets


class TestFilterToilets:
    def test_filter_all(self):
        df = pd.DataFrame([
            {"title": "トイレA", "category": "レストラン", "is_public_toilet": False},
            {"title": "トイレB", "category": "コンビニ", "is_public_toilet": False},
            {"title": "トイレC", "category": "公園", "is_public_toilet": True},
        ])
        result = filter_toilets(df, "すべて")
        assert len(result) == 3

    def test_filter_public(self):
        df = pd.DataFrame([
            {"title": "トイレA", "category": "レストラン", "is_public_toilet": False},
            {"title": "トイレB", "category": "公園", "is_public_toilet": True},
        ])
        result = filter_toilets(df, "公共トイレ")
        assert len(result) == 1
        assert result.iloc[0]["is_public_toilet"]

    def test_filter_cafe(self):
        df = pd.DataFrame([
            {"title": "トイレA", "category": "カフェ", "is_public_toilet": False},
            {"title": "トイレB", "category": "喫茶店", "is_public_toilet": False},
        ])
        result = filter_toilets(df, "カフェ・飲食")
        assert len(result) == 2

    def test_filter_by_prefecture(self):
        df = pd.DataFrame([
            {"title": "トイレA", "category": "公園", "is_public_toilet": False, "prefecture": "東京都"},
            {"title": "トイレB", "category": "公園", "is_public_toilet": False, "prefecture": "神奈川県"},
        ])
        result = filter_toilets(df, "すべて", prefecture="東京都")
        assert len(result) == 1
        assert result.iloc[0]["prefecture"] == "東京都"


class TestSearchToilets:
    def test_search_name(self):
        df = pd.DataFrame([
            {"title": "マクドナルド前トイレ", "address": "東京都", "category": "快餐"},
            {"title": "ケンタッキー前トイレ", "address": "大阪府", "category": "快餐"},
        ])
        result = search_toilets(df, "マクドナルド")
        assert len(result) == 1

    def test_search_address(self):
        df = pd.DataFrame([
            {"title": "トイレA", "address": "東京都渋谷区", "category": "公園"},
            {"title": "トイレB", "address": "大阪府大阪市", "category": "公園"},
        ])
        result = search_toilets(df, "東京")
        assert len(result) == 1

    def test_search_empty(self):
        df = pd.DataFrame([{"title": "トイレA", "address": "東京", "category": "公園"}])
        assert len(search_toilets(df, "")) == 1

    def test_search_no_match(self):
        df = pd.DataFrame([{"title": "トイレA", "address": "東京", "category": "公園"}])
        assert len(search_toilets(df, "存在的しない")) == 0


class TestGetScoreStyle:
    def test_very_clean(self):
        from app_config import get_score_style
        color, emoji, label = get_score_style(90)
        assert emoji == "✨"
        assert label == "とてもきれい"

    def test_dirty(self):
        from app_config import get_score_style
        color, emoji, label = get_score_style(20)
        assert emoji == "💩"


class TestEscaping:
    def test_esc(self):
        from app_config import esc
        assert esc("<test>") == "&lt;test&gt;"
    def test_esc_none(self):
        from app_config import esc
        assert esc(None) == ""

    def test_safe_href_blocks_javascript(self):
        from app_config import safe_href
        assert safe_href("javascript:alert(1)") == ""

    def test_safe_href_allows_https(self):
        from app_config import safe_href
        assert safe_href("https://maps.google.com/?q=test") == "https://maps.google.com/?q=test"


class TestGeolocationScript:
    def test_build_geolocation_js_returns_plain_object(self):
        from app import build_geolocation_js

        js = build_geolocation_js()
        assert "resolve(pos.coords)" not in js
        assert "latitude: pos.coords.latitude" in js
        assert "longitude: pos.coords.longitude" in js


class TestBuildPopupHtml:
    def test_build_popup_basic(self):
        from ui.popups import build_popup_html
        toilet = {
            "title": "テストトイレ",
            "category": "公園",
            "toilet_score": 85.0,
            "toilet_review_count": 5,
            "confidence": 0.8,
            "is_public_toilet": True,
            "address": "東京都渋谷区",
            "rating": 4.5,
            "review_count": 100,
        }
        html = build_popup_html(toilet)
        assert "テストトイレ" in html
        assert "85" in html

    def test_build_popup_blocks_dangerous_link(self):
        from ui.popups import build_popup_html
        toilet = {
            "title": "テストトイレ",
            "category": "公園",
            "toilet_score": 85.0,
            "toilet_review_count": 5,
            "confidence": 0.8,
            "is_public_toilet": True,
            "address": "東京都渋谷区",
            "rating": 4.5,
            "review_count": 100,
            "link": 'javascript:alert(1)" onclick="alert(2)',
        }
        html = build_popup_html(toilet)
        assert "javascript:" not in html
        assert "onclick=" not in html

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
