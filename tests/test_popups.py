"""
tests/test_popups.py
ui/popups.py のユニットテスト
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from ui.popups import (
    build_popup_html,
    _build_public_badge,
    _build_keyword_tags,
    _build_review_html,
    _build_link_html,
)


class TestBuildPublicBadge:
    def test_public_true(self):
        html = _build_public_badge(True)
        assert "公共トイレ" in html

    def test_public_false(self):
        html = _build_public_badge(False)
        assert html == ""


class TestBuildKeywordTags:
    def test_positive_tag(self):
        html = _build_keyword_tags([("+清潔", 3)])
        assert "👍" in html
        assert "清潔" in html
        assert "×3" in html

    def test_negative_tag(self):
        html = _build_keyword_tags([("-汚い", 2)])
        assert "👎" in html
        assert "汚い" in html
        assert "×2" in html

    def test_neutral_tag(self):
        html = _build_keyword_tags([("広い", 1)])
        assert "広い" in html

    def test_empty(self):
        html = _build_keyword_tags([])
        assert html == ""

    def test_limit_5(self):
        tags = [(f"kw{i}", 1) for i in range(10)]
        html = _build_keyword_tags(tags)
        assert html.count("×1") == 5


class TestBuildReviewHtml:
    def test_basic_review(self):
        reviews = [
            {"text": "トイレがきれいです。清潔でよかった。", "name": "ユーザーA", "rating": 5, "score": 2},
        ]
        html = _build_review_html(reviews)
        assert "👍" in html
        assert "ユーザーA" in html
        assert "★5" in html

    def test_negative_review(self):
        reviews = [
            {"text": "トイレが汚い。臭かった。", "name": "ユーザーB", "rating": 2, "score": -2},
        ]
        html = _build_review_html(reviews)
        assert "👎" in html

    def test_empty(self):
        html = _build_review_html([])
        assert html == ""

    def test_duplicate_skip(self):
        reviews = [
            {"text": "同じテキストです。", "name": "A", "rating": 4, "score": 0},
            {"text": "同じテキストです。", "name": "B", "rating": 4, "score": 0},
        ]
        html = _build_review_html(reviews)
        assert html.count("同じテキストです") == 1


class TestBuildLinkHtml:
    def test_with_link(self):
        html = _build_link_html("https://maps.google.com/")
        assert "Google Maps" in html
        assert "href=" in html

    def test_empty(self):
        html = _build_link_html("")
        assert html == ""

    def test_no_rel_attack(self):
        html = _build_link_html("https://evil.com")
        assert 'rel="noopener noreferrer"' in html


class TestBuildPopupHtml:
    def test_basic_fields(self):
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
            "phone": "03-1234-5678",
            "link": "https://maps.google.com/",
            "top_keywords": [("+清潔", 3), ("+広い", 2)],
            "sample_reviews": [
                {"text": "きれいです", "name": "A", "rating": 5, "score": 2}
            ],
        }
        html = build_popup_html(toilet)
        assert "テストトイレ" in html
        assert "85" in html
        assert "東京都渋谷区" in html
        assert "公共トイレ" in html
        assert "信頼度" in html

    def test_private_toilet_no_badge(self):
        toilet = {
            "title": "カフェのトイレ",
            "category": "カフェ",
            "toilet_score": 55.0,
            "toilet_review_count": 2,
            "confidence": 0.4,
            "is_public_toilet": False,
            "address": "大阪市",
            "rating": 3.5,
            "review_count": 50,
        }
        html = build_popup_html(toilet)
        assert "公共トイレ" not in html


if __name__ == "__main__":
    pytest.main([__file__, "-v"])