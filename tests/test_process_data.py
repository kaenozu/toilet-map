"""
tests/test_process_data.py
process_data.py + scoring_config.py のユニットテスト
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "batch"))

import pytest
import process_data as pd_module


class TestToiletDetection:
    def test_mentions_toilet_yes(self):
        assert pd_module.mentions_toilet("トイレがきれいです")
    def test_mentions_toilet_no(self):
        assert not pd_module.mentions_toilet("スタッフの対応が素晴らしい")
    def test_mentions_toilet_english(self):
        assert pd_module.mentions_toilet("clean bathroom")


class TestContextExtraction:
    def test_extract(self):
        text = "店のトイレは清潔です"
        contexts = pd_module.extract_toilet_contexts(text)
        assert len(contexts) > 0
    def test_extract_single(self):
        text = "トイレは汚いです"
        contexts = pd_module.extract_toilet_contexts(text)
        assert any("汚い" in c for c in contexts)


class TestKeywordScoring:
    def test_positive(self):
        text = "トイレがきれいで清潔です"
        score, matched = pd_module._apply_keyword_scoring(text)
        assert score > 0
        assert len(matched) > 0
    def test_negative(self):
        text = "トイレが汚くて臭い"
        score, matched = pd_module._apply_keyword_scoring(text)
        assert score < 0


class TestNegationCorrection:
    def test_negation_reduces(self):
        text = "トイレは清潔ではない"
        score, _ = pd_module._apply_keyword_scoring(text)
        corrected, _ = pd_module._apply_negation_correction(text, score, ["+清潔"])
        assert corrected <= score
    def test_no_negation(self):
        text = "トイレは清潔です"
        score, matched = pd_module._apply_keyword_scoring(text)
        corrected, _ = pd_module._apply_negation_correction(text, score, matched)
        assert corrected == score


class TestOverallScoring:
    def test_positive(self):
        text = "トイレがきれいで清潔です"
        score, matched = pd_module.score_toilet_from_review(text)
        assert isinstance(score, (int, float))
    def test_negative(self):
        text = "トイレ脏而且有异味"
        score, matched = pd_module.score_toilet_from_review(text)
        assert isinstance(score, (int, float))


class TestRatingAdjustment:
    def test_high_rating_boost(self):
        matched = ["+清潔"]
        adjusted, _ = pd_module._adjust_by_rating(2.0, matched, 5.0)
        assert adjusted > 2.0
    def test_low_rating_boost(self):
        matched = ["-汚い"]
        adjusted, _ = pd_module._adjust_by_rating(-2.0, matched, 1.0)
        assert adjusted < -2.0


class TestConfidence:
    def test_zero_reviews(self):
        place = {"name": "test", "user_reviews": [], "user_reviews_extended": [], "review_rating": 4.5}
        result = pd_module.compute_toilet_score(place)
        assert result["confidence"] == 0.1


class TestPlaceDetection:
    def test_is_toilet_place(self):
        place = {"name": "store", "category": "公園"}
        result = pd_module.is_toilet_place(place)
        assert isinstance(result, bool)


class TestDynamicZoom:
    def test_single_point(self):
        results = [{"lat": 35.5, "lng": 139.5}]
        assert pd_module.calc_dynamic_zoom(results) == 13
    def test_local_area(self):
        results = [{"lat": 35.7, "lng": 139.7}, {"lat": 35.71, "lng": 139.71}]
        z = pd_module.calc_dynamic_zoom(results)
        assert isinstance(z, int) and 10 <= z <= 15
    def test_wide_area(self):
        results = [{"lat": 35.0, "lng": 135.0}, {"lat": 43.0, "lng": 142.0}]
        assert pd_module.calc_dynamic_zoom(results) <= 7


class TestExtractPrefecture:
    def test_basic(self):
        result = pd_module.extract_prefecture("東京都渋谷区")
        assert result == "東京都"
    def test_empty(self):
        assert pd_module.extract_prefecture("") == ""
    def test_not_found(self):
        assert pd_module.extract_prefecture("xyz") == ""


class TestProcessPlace:
    def test_valid(self):
        place = {
            "title": "テスト施設", "category": "カフェ",
            "address": "東京都渋谷区", "latitude": 35.68, "longitude": 139.69,
            "phone": "03-1234-5678", "review_rating": 4.0, "review_count": 50,
            "link": "https://maps.google.com/",
        }
        result = pd_module.process_place(place)
        assert result is not None
        assert result["title"] == "テスト施設"
        assert result["prefecture"] == "東京都"
    def test_missing_coords(self):
        place = {"title": "テスト", "address": "東京都"}
        assert pd_module.process_place(place) is None
    def test_missing_title(self):
        place = {"latitude": 35.0, "longitude": 139.0}
        assert pd_module.process_place(place) is None


class TestDeduplicate:
    def test_dedup(self):
        places = [
            {"title": "A", "latitude": 35.0, "longitude": 139.0},
            {"title": "A", "latitude": 35.0, "longitude": 139.0},
            {"title": "B", "latitude": 35.1, "longitude": 139.1},
        ]
        result = pd_module.deduplicate(places)
        assert len(result) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])