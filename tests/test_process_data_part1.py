"""
tests/test_process_data.py
process_data.py + scoring.py のユニットテスト
"""
import process_data as pd_module
import scoring


class TestToiletDetection:
    def test_mentions_toilet_yes(self):
        assert scoring.mentions_toilet("トイレがきれいです")
    def test_mentions_toilet_no(self):
        assert not scoring.mentions_toilet("スタッフの対応が素晴らしい")
    def test_mentions_toilet_english(self):
        assert scoring.mentions_toilet("clean bathroom")
    def test_mentions_toilet_negative_phrase_is_ignored(self):
        assert not scoring.mentions_toilet("トイレはありません")
        assert not scoring.mentions_toilet("no toilet available")



class TestContextExtraction:
    def test_extract(self):
        text = "店のトイレは清潔です"
        contexts = scoring.extract_toilet_contexts(text)
        assert len(contexts) > 0
    def test_extract_single(self):
        text = "トイレは汚いです"
        contexts = scoring.extract_toilet_contexts(text)
        assert any("汚い" in c for c in contexts)



class TestKeywordScoring:
    def test_positive(self):
        text = "トイレがきれいで清潔です"
        score, matched = scoring._apply_scoring_and_negation(text)
        assert score > 0
        assert len(matched) > 0
    def test_negative(self):
        text = "トイレが汚くて臭い"
        score, matched = scoring._apply_scoring_and_negation(text)
        assert score < 0

    def test_empty_keyword_lists_do_not_match_empty_strings(self, monkeypatch):
        monkeypatch.setattr(scoring, "POSITIVE_KEYWORDS", {})
        monkeypatch.setattr(scoring, "NEGATIVE_KEYWORDS", {})
        monkeypatch.setattr(scoring, "NEGATION_WORDS", [])
        monkeypatch.setattr(scoring, "_POS_PATTERN", type("", (), {"finditer": lambda _, t: []})())
        monkeypatch.setattr(scoring, "_NEG_PATTERN", type("", (), {"finditer": lambda _, t: []})())
        monkeypatch.setattr(scoring, "_NEGATION_PATTERN", type("", (), {"finditer": lambda _, t: []})())

        score, matched = scoring._apply_scoring_and_negation("トイレが清潔です")

        assert score == 0
        assert matched == []



class TestNegationCorrection:
    def test_negation_reduces(self):
        text = "トイレは清潔ではない"
        score, matched = scoring._apply_scoring_and_negation(text)
        assert score == 0
        assert "+清潔" not in matched

    def test_no_negation(self):
        text = "トイレは清潔です"
        score, matched = scoring._apply_scoring_and_negation(text)
        assert score > 0
        assert "+清潔" in matched

    def test_negative_keyword_negation(self):
        text = "トイレは汚いではない"
        score, matched = scoring._apply_scoring_and_negation(text)
        assert any(kw.startswith("~汚い") for kw in matched)
        assert score >= 0



class TestOverallScoring:
    def test_positive(self):
        text = "トイレがきれいで清潔です"
        score, matched = scoring.score_toilet_from_review(text)
        assert isinstance(score, (int, float))
    def test_negative(self):
        text = "トイレ脏而且有异味"
        score, matched = scoring.score_toilet_from_review(text)
        assert isinstance(score, (int, float))



class TestRatingAdjustment:
    def test_high_rating_boost(self):
        matched = ["+清潔"]
        adjusted, _ = scoring._adjust_by_rating(2.0, matched, 5.0)
        assert adjusted > 2.0
    def test_low_rating_boost(self):
        matched = ["-汚い"]
        adjusted, _ = scoring._adjust_by_rating(-2.0, matched, 1.0)
        assert adjusted < -2.0



class TestConfidence:
    def test_zero_reviews(self):
        place = {"name": "test", "user_reviews": [], "user_reviews_extended": [], "review_rating": 4.5}
        result = scoring.compute_toilet_score(place)
        assert result["confidence"] == 0.1

    def test_single_toilet_review_has_low_but_nonzero_confidence(self):
        place = {
            "title": "test",
            "review_rating": 4.0,
            "user_reviews": [{"Description": "トイレがきれい", "Rating": 5}],
            "user_reviews_extended": [],
        }
        result = scoring.compute_toilet_score(place)
        assert result["toilet_review_count"] == 1
        assert result["confidence"] == 0.2

    def test_duplicate_reviews_are_counted_once(self):
        review = {"Description": "トイレが清潔で広い", "Rating": 5, "When": "today", "Name": "A"}
        place = {
            "title": "test",
            "review_rating": 4.0,
            "user_reviews": [review],
            "user_reviews_extended": [dict(review)],
        }
        result = scoring.compute_toilet_score(place)
        assert result["toilet_review_count"] == 1
        assert len(result["toilet_reviews"]) == 1



class TestPlaceDetection:
    def test_is_toilet_place(self):
        place = {"name": "store", "category": "公園"}
        result = scoring.is_toilet_place(place)
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



