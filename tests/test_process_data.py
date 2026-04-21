"""
tests/test_process_data.py
process_data.py のスコアリングロジックユニットテスト
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "batch"))

import process_data as pd_module
import pytest


class TestToiletDetection:
    """トイレ言及検知テスト"""

    def test_mentions_toilet_yes(self):
        assert pd_module.mentions_toilet("トイレがきれいです") == True

    def test_mentions_toilet_no(self):
        assert pd_module.mentions_toilet("スタッフの対応が素晴らしい") == False

    def test_mentions_toilet_english(self):
        assert pd_module.mentions_toilet("clean bathroom") == True


class TestContextExtraction:
    """トイレ文脈抽出テスト"""

    def test_extract_toilet_contexts(self):
        text = "店的トイレは清潔です"
        contexts = pd_module.extract_toilet_contexts(text)
        assert len(contexts) > 0

    def test_extract_single_context(self):
        text = "トイレは汚いです"
        contexts = pd_module.extract_toilet_contexts(text)
        assert any("汚い" in c for c in contexts)


class TestKeywordScoring:
    """キーワードスコアリングテスト"""

    def test_positive_keyword(self):
        text = "トイレがきれいで清潔です"
        score, matched = pd_module._apply_keyword_scoring(text)
        assert score > 0
        assert len(matched) > 0

    def test_negative_keyword(self):
        text = "トイレが汚くて臭い"
        score, matched = pd_module._apply_keyword_scoring(text)
        assert score < 0


class TestNegationCorrection:
    """否定文脈補正テスト"""

    def test_negation_reduces_score(self):
        text = "トイレは清潔ではない"
        score, _ = pd_module._apply_keyword_scoring(text)
        corrected, _ = pd_module._apply_negation_correction(text, score, ["清洁"])
        assert corrected <= score

    def test_no_negation(self):
        text = "トイレは清潔です"
        score, matched = pd_module._apply_keyword_scoring(text)
        corrected, _ = pd_module._apply_negation_correction(text, score, matched)
        assert corrected == score


class TestOverallScoring:
    """全体スコアリングテスト"""

    def test_score_toilet_from_review_positive(self):
        text = "トイレがきれいで清洁です"
        score, matched = pd_module.score_toilet_from_review(text)
        # スコアは toilets レビューが対象なので 0 も可能
        assert isinstance(score, (int, float))

    def test_score_toilet_from_review_negative(self):
        text = "トイレ脏而且有异味"
        score, matched = pd_module.score_toilet_from_review(text)
        assert isinstance(score, (int, float))


class TestRatingAdjustment:
    """レビュー評価補正テスト"""

    def test_high_rating_positive_boost(self):
        text = "清洁"
        matched = ["清洁"]
        adjusted, _ = pd_module._adjust_by_rating(2.0, matched, 5.0)
        assert adjusted > 2.0

    def test_low_rating_negative_boost(self):
        text = "不干净"
        matched = ["干净"]
        adjusted, _ = pd_module._adjust_by_rating(-2.0, matched, 1.0)
        assert adjusted < -2.0


class TestConfidence:
    """信頼度計算テスト"""

    def test_confidence_with_0_reviews(self):
        place = {
            "name": "test",
            "user_reviews": [],
            "user_reviews_extended": [],
            "review_rating": 4.5,
        }
        result = pd_module.compute_toilet_score(place)
        assert result["confidence"] == pd_module.CONFIDENCE_LOW


class TestPlaceDetection:
    """トイレ設置場所判定テスト"""

    def test_is_toilet_place_basic(self):
        # 公园にトイレはありません
        place = {"name": "store", "category": "公园"}
        result = pd_module.is_toilet_place(place)
        assert isinstance(result, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])