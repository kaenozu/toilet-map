"""
tests/test_popups.py
ui/popups.py のユニットテスト
"""
import pytest

from ui.popups import (
    _build_keyword_tags,
    _build_link_html,
    _build_public_badge,
    _build_review_html,
    build_popup_html,
)


class TestPublicBadge:
    def test_public_true(self):
        html = _build_public_badge(True)
        assert "公共トイレ" in html
    def test_public_false(self):
        assert _build_public_badge(False) == ""


class TestKeywordTags:
    def test_positive(self):
        html = _build_keyword_tags([("+清潔", 3)])
        assert "👍" in html and "清潔" in html and "×3" in html
    def test_negative(self):
        html = _build_keyword_tags([("-汚い", 2)])
        assert "👎" in html and "汚い" in html
    def test_neutral(self):
        html = _build_keyword_tags([("広い", 1)])
        assert "広い" in html
    def test_empty(self):
        assert _build_keyword_tags([]) == ""
    def test_limit_5(self):
        tags = [(f"kw{i}", 1) for i in range(10)]
        html = _build_keyword_tags(tags)
        assert html.count("×1") == 5


class TestReviewHtml:
    def test_basic(self):
        reviews = [{"text": "きれいです。清潔でよかった。", "name": "ユーザーA", "rating": 5, "score": 2}]
        html = _build_review_html(reviews)
        assert "👍" in html and "ユーザーA" in html and "★5" in html
    def test_negative(self):
        reviews = [{"text": "汚い。臭かった。", "name": "ユーザーB", "rating": 2, "score": -2}]
        html = _build_review_html(reviews)
        assert "👎" in html
    def test_empty(self):
        assert _build_review_html([]) == ""
    def test_duplicate_skip(self):
        reviews = [
            {"text": "同じテキストです。", "name": "A", "rating": 4, "score": 0},
            {"text": "同じテキストです。", "name": "B", "rating": 4, "score": 0},
        ]
        html = _build_review_html(reviews)
        assert html.count("同じテキストです") == 1


class TestLinkHtml:
    def test_with_link(self):
        html = _build_link_html("https://maps.google.com/")
        assert "Google Maps" in html and "href=" in html
    def test_empty(self):
        assert _build_link_html("") == ""
    def test_rel_attack(self):
        html = _build_link_html("https://evil.com")
        assert 'rel="noopener noreferrer"' in html


class TestBuildPopupHtml:
    def test_basic_fields(self):
        toilet = {
            "title": "テストトイレ", "category": "公園", "toilet_score": 85.0,
            "toilet_review_count": 5, "confidence": 0.8, "is_public_toilet": True,
            "address": "東京都渋谷区", "rating": 4.5, "review_count": 100,
            "phone": "03-1234-5678", "link": "https://maps.google.com/",
            "top_keywords": [("+清潔", 3), ("+広い", 2)],
            "sample_reviews": [{"text": "きれいです", "name": "A", "rating": 5, "score": 2}],
        }
        html = build_popup_html(toilet)
        assert "テストトイレ" in html and "85" in html
        assert "東京都渋谷区" in html and "公共トイレ" in html and "信頼度" in html

    def test_private_no_badge(self):
        toilet = {
            "title": "カフェのトイレ", "category": "カフェ", "toilet_score": 55.0,
            "toilet_review_count": 2, "confidence": 0.4, "is_public_toilet": False,
            "address": "大阪市", "rating": 3.5, "review_count": 50,
        }
        html = build_popup_html(toilet)
        assert "公共トイレ" not in html

    def test_clean_none_returns_empty(self):
        from ui.popups import clean
        assert clean(None) == ""

    def test_low_confidence_shows_reference_note(self):
        toilet = {
            "title": "信頼度確認トイレ", "category": "公園", "toilet_score": 58.0,
            "toilet_review_count": 1, "confidence": 0.2, "is_public_toilet": False,
            "address": "東京都", "rating": 4.0, "review_count": 3,
            "sample_reviews": [], "top_keywords": [],
        }
        html = build_popup_html(toilet)
        assert "参考値" in html


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
