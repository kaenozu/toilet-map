"""
tests/test_scoring_module.py
scoring_config.py の定数・設定・キーワード定義のユニットテスト
batch/scoring.py の主要関数の網羅テスト（境界値・エッジケース）

関連: batch/scoring.py, batch/scoring_config.py, tests/test_process_data.py
"""

import scoring
import scoring_config

SCORING_CLAMP_MIN = -5.0
SCORING_CLAMP_MAX = 5.0


class TestScoreClamp:
    def test_clamp_min_value(self):
        assert scoring_config.SCORE_CLAMP_MIN == -5.0

    def test_clamp_max_value(self):
        assert scoring_config.SCORE_CLAMP_MAX == 5.0

    def test_display_conversion_constants(self):
        assert scoring_config.DISPLAY_SCORE_OFFSET == 5
        assert scoring_config.DISPLAY_SCORE_MULTIPLIER == 10


class TestConfidenceConstants:
    def test_review_factor(self):
        assert scoring_config.CONFIDENCE_REVIEW_FACTOR == 5.0

    def test_confidence_min(self):
        assert scoring_config.CONFIDENCE_MIN == 0.1


class TestRatingThresholds:
    def test_high_threshold(self):
        assert scoring_config.RATING_THRESHOLD_HIGH == 4

    def test_low_threshold(self):
        assert scoring_config.RATING_THRESHOLD_LOW == 2

    def boost_factors_symmetric(self):
        assert scoring_config.POSITIVE_BOOST_HIGH == 1.2
        assert scoring_config.NEGATIVE_BOOST_LOW == 1.2

    def dampen_factors_symmetric(self):
        assert scoring_config.NEGATIVE_DAMPEN_HIGH == 0.4
        assert scoring_config.POSITIVE_DAMPEN_LOW == 0.4


class TestNegationConfig:
    def test_window_size(self):
        assert scoring_config.NEGATION_WINDOW == 30

    def test_negation_words_not_empty(self):
        assert len(scoring_config.NEGATION_WORDS) > 0
        assert "ない" in scoring_config.NEGATION_WORDS
        assert "なし" in scoring_config.NEGATION_WORDS


class TestPositiveKeywords:
    def test_not_empty(self):
        assert len(scoring_config.POSITIVE_KEYWORDS) > 0

    def test_all_values_positive(self):
        for kw, val in scoring_config.POSITIVE_KEYWORDS.items():
            assert val > 0, f"Keyword '{kw}' has non-positive value {val}"

    def test_strongest_keyword(self):
        assert scoring_config.POSITIVE_KEYWORDS["清潔"] == 4
        assert scoring_config.POSITIVE_KEYWORDS["ピカピカ"] == 4


class TestNegativeKeywords:
    def test_not_empty(self):
        assert len(scoring_config.NEGATIVE_KEYWORDS) > 0

    def test_all_values_negative(self):
        for kw, val in scoring_config.NEGATIVE_KEYWORDS.items():
            assert val < 0, f"Keyword '{kw}' has non-negative value {val}"

    def test_strongest_negative_keywords(self):
        assert scoring_config.NEGATIVE_KEYWORDS["こびりつき"] == -4
        assert scoring_config.NEGATIVE_KEYWORDS["汚物"] == -4
        assert scoring_config.NEGATIVE_KEYWORDS["汚い"] == -4
        assert scoring_config.NEGATIVE_KEYWORDS["使えない"] == -4
        assert scoring_config.NEGATIVE_KEYWORDS["使用不可"] == -4
        assert scoring_config.NEGATIVE_KEYWORDS["不潔"] == -4


class TestToiletCategories:
    def test_categories_defined(self):
        assert len(scoring_config.TOILET_CATEGORIES) >= 2
        assert "公共トイレ" in scoring_config.TOILET_CATEGORIES
        assert "トイレ" in scoring_config.TOILET_CATEGORIES


class TestToiletMentionKeywords:
    def test_keywords_include_basic_terms(self):
        assert "トイレ" in scoring_config.TOILET_MENTION_KEYWORDS
        assert "お手洗い" in scoring_config.TOILET_MENTION_KEYWORDS
        assert " restroom" in scoring_config.TOILET_MENTION_KEYWORDS

    def test_mention_re_matches_basic_japanese(self):
        assert scoring_config.TOILET_MENTION_RE.search("トイレ")

    def test_mention_re_matches_english_with_space(self):
        assert scoring_config.TOILET_MENTION_RE.search(" restroom")

    def test_mention_re_case_insensitive(self):
        assert scoring_config.TOILET_MENTION_RE.search(" Restroom")


class TestSentenceSplitRe:
    def test_splits_on_period(self):
        result = scoring_config.SENTENCE_SPLIT_RE.split("文A。文B")
        assert result == ["文A", "文B"]

    def test_splits_on_newline(self):
        result = scoring_config.SENTENCE_SPLIT_RE.split("文A\n文B")
        assert result == ["文A", "文B"]

    def test_handles_consecutive_delimiters(self):
        result = scoring_config.SENTENCE_SPLIT_RE.split("文A。。文B")
        assert result == ["文A", "", "文B"]


class TestAreaNameRe:
    def test_matches_standard_address(self):
        m = scoring_config.AREA_NAME_RE.search("東京都渋谷区")
        assert m is not None

    def test_no_match_for_short_text(self):
        m = scoring_config.AREA_NAME_RE.search("abc")
        assert m is None


class TestPrefectures:
    def test_all_47_prefectures(self):
        assert len(scoring_config.PREFECTURES) == 47

    def test_contains_major_prefectures(self):
        assert "東京都" in scoring_config.PREFECTURES
        assert "大阪府" in scoring_config.PREFECTURES
        assert "北海道" in scoring_config.PREFECTURES
        assert "沖縄県" in scoring_config.PREFECTURES

    def test_no_duplicates(self):
        assert len(scoring_config.PREFECTURES) == len(set(scoring_config.PREFECTURES))


class TestMentionsToilet:
    def test_empty_text_returns_false(self):
        assert not scoring.mentions_toilet("")
        assert not scoring.mentions_toilet(None)

    def test_no_keyword_returns_false(self):
        assert not scoring.mentions_toilet("ラーメンが美味しい")

    def test_english_keyword(self):
        assert scoring.mentions_toilet("This place has a clean restroom")

    def test_absence_pattern_returns_false(self):
        assert not scoring.mentions_toilet("トイレがありません")
        assert not scoring.mentions_toilet("no toilet available")
        assert not scoring.mentions_toilet("トイレなし")

    def test_toilet_with_absence_word_in_different_context(self):
        assert scoring.mentions_toilet("トイレはあります")


class TestGetLongitude:
    def test_returns_longitude(self):
        assert scoring._get_longitude({"longitude": 139.69}) == 139.69

    def test_falls_back_to_longtitude(self):
        assert scoring._get_longitude({"longtitude": 139.69}) == 139.69

    def test_prefers_longitude_over_longtitude(self):
        assert scoring._get_longitude({"longitude": 140.0, "longtitude": 139.0}) == 140.0

    def test_none_values(self):
        assert scoring._get_longitude({"longitude": None}) == 0.0

    def test_empty_dict(self):
        assert scoring._get_longitude({}) == 0.0


class TestExtractToiletContexts:
    def test_no_toilet_mention_returns_empty(self):
        assert scoring.extract_toilet_contexts("ラーメンが美味しい") == []

    def test_single_sentence_with_toilet(self):
        result = scoring.extract_toilet_contexts("トイレがきれいです")
        assert len(result) >= 1
        assert "きれい" in result[0]

    def test_context_spans_adjacent_sentences(self):
        text = "店の雰囲気は良い。トイレがとてもきれい。また来たい。"
        result = scoring.extract_toilet_contexts(text)
        assert len(result) >= 2
        assert any("雰囲気" in s for s in result)
        assert any("また来たい" in s for s in result)

    def test_empty_text(self):
        assert scoring.extract_toilet_contexts("") == []

    def test_absence_pattern_does_not_extract(self):
        assert scoring.extract_toilet_contexts("トイレはありません") == []


class TestApplyScoringAndNegation:
    def test_positive_keyword_scores(self):
        score, matched = scoring._apply_scoring_and_negation("きれい")
        assert score > 0
        assert "+きれい" in matched

    def test_negative_keyword_scores(self):
        score, matched = scoring._apply_scoring_and_negation("汚い")
        assert score < 0
        assert "-汚い" in matched

    def test_multiple_keywords_summed(self):
        score, matched = scoring._apply_scoring_and_negation("きれいで清潔")
        assert score >= 6

    def test_negation_cancels_positive(self):
        score, matched = scoring._apply_scoring_and_negation("きれいではない")
        assert "+きれい" not in matched

    def test_negated_negative_becomes_neutral(self):
        score, matched = scoring._apply_scoring_and_negation("汚いではない")
        assert "-汚い" not in matched

    def test_no_keywords_returns_zero(self):
        score, matched = scoring._apply_scoring_and_negation("特に問題なし")
        assert score == 0
        assert matched == []


class TestScoreToiletFromReview:
    def test_positive_review(self):
        score, matched = scoring.score_toilet_from_review("トイレがきれいで清潔です")
        assert isinstance(score, float)
        assert SCORING_CLAMP_MIN <= score <= SCORING_CLAMP_MAX

    def test_negative_review(self):
        score, matched = scoring.score_toilet_from_review("トイレが汚くて臭い")
        assert score < 0

    def test_empty_text_returns_zero(self):
        score, matched = scoring.score_toilet_from_review("")
        assert score == 0

    def test_no_toilet_mention_scores_review_text(self):
        score, matched = scoring.score_toilet_from_review("清潔な店内")
        assert isinstance(score, float)


class TestAdjustByRating:
    def test_high_rating_dampens_negative(self):
        score, matched = scoring._adjust_by_rating(-4.0, ["-汚い"], 5.0)
        assert score > -4.0

    def test_high_rating_boosts_positive(self):
        score, matched = scoring._adjust_by_rating(2.0, ["+清潔"], 5.0)
        assert score > 2.0

    def test_low_rating_boosts_negative(self):
        score, matched = scoring._adjust_by_rating(-2.0, ["-汚い"], 1.0)
        assert score < -2.0

    def test_low_rating_dampens_positive(self):
        score, matched = scoring._adjust_by_rating(2.0, ["+清潔"], 1.0)
        assert score < 2.0

    def test_mid_rating_no_change(self):
        score, matched = scoring._adjust_by_rating(2.0, ["+清潔"], 3.0)
        assert score == 2.0

    def test_zero_score_no_change(self):
        score, matched = scoring._adjust_by_rating(0.0, [], 5.0)
        assert score == 0.0


class TestCalculateFinalScore:
    def test_no_reviews_no_rating(self):
        score, confidence = scoring._calculate_final_score([], 0.0, 0.0)
        assert score == 0.0
        assert confidence == 0.0

    def test_no_reviews_with_rating(self):
        score, confidence = scoring._calculate_final_score([], 4.0, 0.0)
        assert score > 0
        assert confidence == 0.1

    def test_with_reviews(self):
        reviews = [{"score": 3.0}, {"score": 4.0}]
        score, confidence = scoring._calculate_final_score(reviews, 4.0, 7.0)
        assert isinstance(score, float)
        assert confidence == 0.4

    def test_score_clamped(self):
        reviews = [{"score": 10.0}] * 10
        score, confidence = scoring._calculate_final_score(reviews, 5.0, 100.0)
        assert SCORING_CLAMP_MIN <= score <= SCORING_CLAMP_MAX


class TestComputeToiletScore:
    def test_no_reviews_no_rating(self):
        place = {
            "title": "test",
            "review_rating": 0.0,
            "user_reviews": [],
            "user_reviews_extended": [],
        }
        result = scoring.compute_toilet_score(place)
        assert result["score"] == 0.0
        assert result["confidence"] == 0.0
        assert result["toilet_review_count"] == 0
        assert result["top_keywords"] == []

    def test_no_toilet_reviews_with_rating(self):
        place = {
            "title": "test",
            "review_rating": 4.5,
            "user_reviews": [{"Description": "美味しかった", "Rating": 5}],
            "user_reviews_extended": [],
        }
        result = scoring.compute_toilet_score(place)
        assert result["confidence"] == 0.1

    def test_single_positive_review(self):
        place = {
            "title": "test",
            "review_rating": 4.0,
            "user_reviews": [{"Description": "トイレがきれいです", "Rating": 5}],
            "user_reviews_extended": [],
        }
        result = scoring.compute_toilet_score(place)
        assert result["toilet_review_count"] == 1
        assert len(result["toilet_reviews"]) == 1
        assert len(result["top_keywords"]) > 0

    def test_review_limit_is_20(self):
        reviews = [
            {"Description": "トイレがきれい", "Rating": 4}
        ] * 30
        place = {
            "title": "test",
            "review_rating": 4.0,
            "user_reviews": reviews,
            "user_reviews_extended": [],
        }
        result = scoring.compute_toilet_score(place)
        assert result["toilet_review_count"] >= 1
        assert len(result["toilet_reviews"]) <= 20

    def test_empty_user_reviews_extended(self):
        place = {
            "title": "test",
            "review_rating": 3.5,
            "user_reviews": [],
            "user_reviews_extended": [],
        }
        result = scoring.compute_toilet_score(place)
        assert result["toilet_review_count"] == 0

    def test_none_review_rating(self):
        place = {
            "title": "test",
            "review_rating": None,
            "user_reviews": [],
            "user_reviews_extended": [],
        }
        result = scoring.compute_toilet_score(place)
        assert result["score"] == 0.0

    def test_none_review_fields(self):
        place = {
            "title": "test",
            "review_rating": 4.0,
            "user_reviews": None,
            "user_reviews_extended": None,
        }
        result = scoring.compute_toilet_score(place)
        assert result["toilet_review_count"] == 0


class TestIsToiletPlace:
    def test_public_toilet_by_category(self):
        assert scoring.is_toilet_place({"category": "公共トイレ", "title": "X"})

    def test_restroom_english(self):
        assert scoring.is_toilet_place({"category": "restroom", "title": "X"})

    def test_toilet_in_title(self):
        assert scoring.is_toilet_place({"category": "その他", "title": "トイレ"})

    def test_regular_place_returns_false(self):
        assert not scoring.is_toilet_place({"category": "カフェ", "title": "スタバ"})

    def test_empty_fields_returns_false(self):
        assert not scoring.is_toilet_place({"category": "", "title": ""})

    def test_none_fields_returns_false(self):
        assert not scoring.is_toilet_place({"category": None, "title": None})

    def test_case_insensitive(self):
        assert scoring.is_toilet_place({"category": "Restroom", "title": "X"})


class TestToiletAbsencePatterns:
    def test_japanese_no_toilet(self):
        assert scoring.TOILET_ABSENCE_RE.search("トイレがない")
        assert scoring.TOILET_ABSENCE_RE.search("トイレはなし")
        assert scoring.TOILET_ABSENCE_RE.search("お手洗いがありません")

    def test_english_no_toilet(self):
        assert scoring.TOILET_ABSENCE_RE.search("no toilet")
        assert scoring.TOILET_ABSENCE_RE.search("no restroom")
        assert scoring.TOILET_ABSENCE_RE.search("not available restroom") is None  # 'not' must be directly followed by toilet term

    def test_non_absence_does_not_match(self):
        assert not scoring.TOILET_ABSENCE_RE.search("トイレがあります")
        assert not scoring.TOILET_ABSENCE_RE.search("トイレきれい")
