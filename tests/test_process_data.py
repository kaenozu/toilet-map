"""
tests/test_process_data.py
process_data.py + scoring.py のユニットテスト
"""
import pytest
import scoring
import process_data as pd_module


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

    def test_display_score_is_clamped_to_upper_bound(self, monkeypatch):
        monkeypatch.setattr(pd_module, "compute_toilet_score", lambda place: {
            "score": 5.0,
            "confidence": 1.0,
            "toilet_review_count": 1,
            "toilet_reviews": [],
            "top_keywords": [],
        })
        place = {
            "title": "上限確認", "category": "公園",
            "address": "東京都渋谷区", "latitude": 35.68, "longitude": 139.69,
        }

        result = pd_module.process_place(place)

        assert result is not None
        assert result["toilet_score"] == 100.0

    def test_longtitude_fallback(self):
        place = {
            "title": "テスト施設", "category": "カフェ",
            "address": "東京都渋谷区", "latitude": 35.68, "longtitude": 139.69,
            "phone": "03-1234-5678", "review_rating": 4.0, "review_count": 50,
            "link": "https://maps.google.com/",
        }

        result = pd_module.process_place(place)

        assert result is not None
        assert result["lng"] == pytest.approx(139.69)
    def test_display_score_is_clamped_to_lower_bound(self, monkeypatch):
        monkeypatch.setattr(pd_module, "compute_toilet_score", lambda place: {
            "score": -5.0,
            "confidence": 1.0,
            "toilet_review_count": 1,
            "toilet_reviews": [],
            "top_keywords": [],
        })
        place = {
            "title": "下限確認", "category": "公園",
            "address": "東京都渋谷区", "latitude": 35.68, "longitude": 139.69,
        }

        result = pd_module.process_place(place)

        assert result is not None
        assert result["toilet_score"] == 0.0
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

    def test_dedup_by_coordinates_even_with_different_titles(self):
        places = [
            {"title": "A", "latitude": 35.0, "longitude": 139.0},
            {"title": "B", "latitude": 35.0, "longitude": 139.0},
        ]
        result = pd_module.deduplicate(places)
        assert len(result) == 1


class TestBuildToiletResult:
    def test_excluded_when_no_toilet_reviews_and_not_public(self):
        from batch.process_data import _build_toilet_result
        place = {"title": "ラーメン屋", "category": "ラーメン"}
        info = {"score": 0.0, "confidence": 0.1, "toilet_review_count": 0,
                "toilet_reviews": [], "top_keywords": []}
        assert _build_toilet_result(place, info, 35.0, 139.0) is None

    def test_rescued_when_eligible_category(self):
        from batch.process_data import _build_toilet_result
        place = {"title": "上野公園", "category": "公園"}
        info = {"score": 0.0, "confidence": 0.1, "toilet_review_count": 0,
                "toilet_reviews": [], "top_keywords": []}
        result = _build_toilet_result(place, info, 35.0, 139.0)
        assert result is not None
        assert result["confidence"] == 0.1

    def test_confidence_zero_gives_default_score(self):
        from batch.process_data import _build_toilet_result
        place = {"title": "駅前トイレ", "category": "駅"}
        info = {"score": -5.0, "confidence": 0.0, "toilet_review_count": 1,
                "toilet_reviews": [], "top_keywords": []}
        result = _build_toilet_result(place, info, 35.0, 139.0)
        assert result is not None
        assert result["toilet_score"] == 50.0

    def test_rescued_when_title_matches_cafe(self):
        from batch.process_data import _build_toilet_result
        place = {"title": "ドトールコーヒー", "category": "飲食店"}
        info = {"score": 0.0, "confidence": 0.1, "toilet_review_count": 0,
                "toilet_reviews": [], "top_keywords": []}
        result = _build_toilet_result(place, info, 35.0, 139.0)
        assert result is not None

    def test_public_toilet_passed_through_even_without_reviews(self):
        from batch.process_data import _build_toilet_result
        place = {"title": "公衆トイレ", "category": "公衆トイレ"}
        info = {"score": 0.0, "confidence": 0.1, "toilet_review_count": 0,
                "toilet_reviews": [], "top_keywords": []}
        result = _build_toilet_result(place, info, 35.0, 139.0)
        assert result is not None


class TestMakePlaceKey:
    def test_place_id_used_when_present(self):
        place = {"place_id": "ChIJ", "data_id": "0x111", "title": "A"}
        assert pd_module.make_place_key(place) == "place_id:ChIJ"

    def test_data_id_fallback(self):
        place = {"data_id": "0x222", "title": "A", "address": "東京"}
        assert pd_module.make_place_key(place) == "data_id:0x222"

    def test_coordinates_fallback(self):
        place = {"title": "A", "latitude": 35.0, "longitude": 139.0}
        assert pd_module.make_place_key(place).startswith("coords:")

    def test_title_address_fallback(self):
        place = {"title": "  Test  ", "address": "  東京  "}
        result = pd_module.make_place_key(place)
        assert result.startswith("title_address:")
        assert "test" in result
        assert "東京" in result


class TestLoadExisting:
    def test_loads_gz(self, tmp_path):
        data = {"metadata": {"total": 1}, "toilets": []}
        import gzip
        import json
        path = tmp_path / "out.json.gz"
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump(data, f)
        result = pd_module.load_existing(str(path))
        assert result["metadata"]["total"] == 1

    def test_loads_json(self, tmp_path):
        data = {"metadata": {"total": 2}, "toilets": []}
        path = tmp_path / "out.json"
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        result = pd_module.load_existing(str(path))
        assert result["metadata"]["total"] == 2

    def test_falls_back_to_gz_when_json_missing(self, tmp_path):
        data = {"metadata": {"total": 3}, "toilets": []}
        import gzip
        import json
        path = tmp_path / "out.json"
        with gzip.open(f"{path}.gz", "wt", encoding="utf-8") as f:
            json.dump(data, f)
        result = pd_module.load_existing(str(path))
        assert result["metadata"]["total"] == 3

    def test_returns_empty_on_not_found(self, tmp_path):
        result = pd_module.load_existing(str(tmp_path / "nonexistent.json"))
        assert result == {"metadata": None, "toilets": []}

    def test_returns_empty_on_json_decode_error(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not valid json", encoding="utf-8")
        result = pd_module.load_existing(str(path))
        assert result == {"metadata": None, "toilets": []}


class TestBuildMetadata:
    def test_with_results(self):
        results = [
            {"lat": 35.68, "lng": 139.69, "address": "東京都渋谷区", "toilet_score": 80.0, "confidence": 0.8, "is_public_toilet": True},
            {"lat": 35.70, "lng": 139.71, "address": "東京都新宿区", "toilet_score": 60.0, "confidence": 0.5, "is_public_toilet": False},
        ]
        meta = pd_module.build_metadata(results)
        assert meta["total"] == 2
        assert meta["scored"] == 2
        assert meta["public_toilets"] == 1
        assert isinstance(meta["last_updated"], str)

    def test_without_results(self):
        meta = pd_module.build_metadata([])
        assert meta["total"] == 0
        assert meta["center_lat"] == 36.2231
        assert meta["center_lng"] == 139.3772
        assert meta["area_name"] == "検索エリア"

    def test_area_name_extracted_from_address(self):
        results = [
            {"lat": 35.0, "lng": 139.0, "address": "東京都渋谷区", "toilet_score": 80.0, "confidence": 0.8, "is_public_toilet": True},
        ]
        meta = pd_module.build_metadata(results)
        assert "渋谷区" in meta["area_name"]

    def test_area_name_fallback_when_no_address_match(self):
        results = [
            {"lat": 35.0, "lng": 139.0, "address": "1234567890", "toilet_score": 80.0, "confidence": 0.8, "is_public_toilet": True},
        ]
        meta = pd_module.build_metadata(results)
        assert meta["area_name"] == "検索エリア"


class FakeResult:
    """process_place のモック戻り値"""
    def __init__(self, title, score, lat=35.0, lng=139.0):
        self.title = title
        self.toilet_score = score
        self.lat = lat
        self.lng = lng
        self.confidence = 0.8 if score > 0 else 0.0
        self.is_public_toilet = True


class TestProcessFile:
    def test_full_mode(self, monkeypatch):
        places = [{"title": "A", "latitude": 35.0, "longitude": 139.0}]

        def fake_process(p):
            return {"title": "A", "toilet_score": 80.0, "confidence": 0.8,
                    "is_public_toilet": True, "lat": 35.0, "lng": 139.0,
                    "address": "", "prefecture": ""}

        monkeypatch.setattr(pd_module, "load_jsonl", lambda path: places)
        monkeypatch.setattr(pd_module, "process_place", fake_process)

        saved = {}
        monkeypatch.setattr(pd_module, "save_json", lambda path, data, **kw: saved.update(data))

        pd_module.process_file("in.json", "out.json", "--full")

        assert saved["metadata"]["total"] == 1
        assert len(saved["toilets"]) == 1

    def test_incremental_mode_merges(self, monkeypatch):
        places = [{"title": "B", "latitude": 35.1, "longitude": 139.1}]
        existing = {"metadata": {"total": 1}, "toilets": [
            {"title": "A", "toilet_score": 70.0, "confidence": 0.5,
             "is_public_toilet": False, "lat": 35.0, "lng": 139.0,
             "address": "", "prefecture": ""},
        ]}

        def fake_process(p):
            return {"title": "B", "toilet_score": 80.0, "confidence": 0.8,
                    "is_public_toilet": True, "lat": 35.1, "lng": 139.1,
                    "address": "", "prefecture": ""}

        monkeypatch.setattr(pd_module, "load_jsonl", lambda path: places)
        monkeypatch.setattr(pd_module, "process_place", fake_process)
        monkeypatch.setattr(pd_module, "load_existing", lambda path: existing)

        saved = {}
        monkeypatch.setattr(pd_module, "save_json", lambda path, data, **kw: saved.update(data))

        pd_module.process_file("in.json", "out.json", "--incremental")

        assert saved["metadata"]["total"] == 2

    def test_empty_places(self, monkeypatch):
        monkeypatch.setattr(pd_module, "load_jsonl", lambda path: [])
        saved = {}
        monkeypatch.setattr(pd_module, "save_json", lambda path, data, **kw: saved.update(data))

        pd_module.process_file("in.json", "out.json")

        assert saved["metadata"]["total"] == 0

    def test_process_file_with_logger_messages(self, monkeypatch):
        places = [{"title": "X", "latitude": 35.0, "longitude": 139.0}]
        monkeypatch.setattr(pd_module, "load_jsonl", lambda path: places)
        monkeypatch.setattr(pd_module, "process_place",
                            lambda p: {"title": "X", "toilet_score": 90.0, "confidence": 0.9,
                                       "is_public_toilet": True, "lat": 35.0, "lng": 139.0,
                                       "address": "", "prefecture": ""})
        saved = {}
        monkeypatch.setattr(pd_module, "save_json", lambda path, data, **kw: saved.update(data))

        pd_module.process_file("in.json", "out.json")

        assert saved["toilets"][0]["toilet_score"] == 90.0


class TestProcessDataMain:
    def test_exits_on_too_few_args(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["process_data.py"])
        with pytest.raises(SystemExit):
            pd_module.main()

    def test_calls_process_file_with_default_mode(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["process_data.py", "input.json", "output.json"])
        calls = []
        monkeypatch.setattr(pd_module, "process_file",
                            lambda i, o, m="--full": calls.append((i, o, m)))
        pd_module.main()
        assert calls == [("input.json", "output.json", "--full")]

    def test_calls_process_file_with_incremental(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["process_data.py", "input.json", "output.json", "--incremental"])
        calls = []
        monkeypatch.setattr(pd_module, "process_file",
                            lambda i, o, m="--full": calls.append((i, o, m)))
        pd_module.main()
        assert calls == [("input.json", "output.json", "--incremental")]


class TestGetLongitude:
    def test_returns_longitude_when_present(self):
        assert scoring._get_longitude({"longitude": 139.69}) == 139.69

    def test_falls_back_to_longtitude(self):
        assert scoring._get_longitude({"longtitude": 139.69}) == 139.69

    def test_returns_zero_when_both_missing(self):
        assert scoring._get_longitude({}) == 0.0


class TestAdjustByRatingEdgeCases:
    def test_high_rating_negative_score_dampens(self):
        score, matched = scoring._adjust_by_rating(-2.0, ["-汚い"], 5.0)
        assert score > -2.0
        assert "~汚い" in matched

    def test_low_rating_positive_score_dampens(self):
        score, matched = scoring._adjust_by_rating(2.0, ["+清潔"], 1.0)
        assert score < 2.0
        assert "~清潔" in matched


class TestCollectToiletReviews:
    def test_duplicate_review_hash_skipped(self):
        review = {"Description": "トイレがきれい", "Rating": 5}
        place = {
            "title": "test",
            "review_rating": 4.0,
            "user_reviews": [review, dict(review)],
            "user_reviews_extended": [],
        }
        result, highlights = scoring._collect_toilet_reviews(place)
        assert len(result) == 1


class TestCalculateFinalScore:
    def test_no_reviews_and_no_rating(self):
        score, confidence = scoring._calculate_final_score([], 0.0, 0.0)
        assert score == 0.0
        assert confidence == 0.0


class TestExtractCoordinates:
    def test_longitude_zero_falls_back_to_longtitude(self):
        place = {"latitude": 35.0, "longitude": 0, "longtitude": 139.69}
        lat, lon = scoring._extract_coordinates(place)
        assert lon == 139.69

    def test_no_fallback_when_lat_none(self):
        place = {"longitude": 0, "longtitude": 139.69}
        lat, lon = scoring._extract_coordinates(place)
        assert lat is None
