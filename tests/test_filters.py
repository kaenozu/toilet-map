"""
tests/test_filters.py
ui/filters.py のユニットテスト
"""
import pandas as pd
import pytest

from ui.filters import (
    _apply_equipment_filter,
    filter_toilets,
    haversine_distance,
    search_toilets,
)


def _make_df(rows=None):
    if rows is None:
        rows = [
            {"title": "カフェA", "address": "東京都渋谷区", "prefecture": "東京都",
             "category": "カフェ", "lat": 35.68, "lng": 139.69,
             "toilet_score": 80, "is_public_toilet": False},
            {"title": "公共トイレB", "address": "大阪府大阪市", "prefecture": "大阪府",
             "category": "公共施設", "lat": 34.69, "lng": 135.50,
             "toilet_score": 60, "is_public_toilet": True},
            {"title": "コンビニC", "address": "東京都新宿区", "prefecture": "東京都",
             "category": "コンビニ", "lat": 35.70, "lng": 139.70,
             "toilet_score": 45, "is_public_toilet": False},
        ]
    return pd.DataFrame(rows)


class TestFilterToilets:
    def test_no_filter(self):
        df = _make_df()
        result = filter_toilets(df, "すべて")
        assert len(result) == 3

    def test_prefecture_filter(self):
        df = _make_df()
        result = filter_toilets(df, "すべて", prefecture="東京都")
        assert len(result) == 2
        assert all(result["prefecture"] == "東京都")

    def test_public_filter(self):
        df = _make_df()
        result = filter_toilets(df, "公共トイレ")
        assert len(result) == 1
        assert result.iloc[0]["is_public_toilet"]

    def test_category_filter(self):
        df = _make_df()
        result = filter_toilets(df, "カフェ・飲食")
        assert len(result) == 1
        assert result.iloc[0]["title"] == "カフェA"

    def test_store_filter(self):
        df = _make_df()
        result = filter_toilets(df, "コンビニ・店舗")
        assert len(result) == 1
        assert result.iloc[0]["title"] == "コンビニC"

    def test_user_location_adds_distance(self):
        df = _make_df()
        result = filter_toilets(df, "すべて", user_lat=35.68, user_lng=139.69)
        assert "distance" in result.columns
        assert result.iloc[0]["distance"] < 1.0

    def test_empty_result(self):
        df = _make_df()
        result = filter_toilets(df, "すべて", prefecture="沖縄県")
        assert len(result) == 0


class TestSearchToilets:
    def test_title_search(self):
        df = _make_df()
        result = search_toilets(df, "カフェ")
        assert len(result) == 1
        assert result.iloc[0]["title"] == "カフェA"

    def test_address_search(self):
        df = _make_df()
        result = search_toilets(df, "渋谷")
        assert len(result) == 1

    def test_category_search(self):
        df = _make_df()
        result = search_toilets(df, "コンビニ")
        assert len(result) == 1

    def test_no_query(self):
        df = _make_df()
        result = search_toilets(df, "")
        assert len(result) == 3

    def test_none_query(self):
        df = _make_df()
        result = search_toilets(df, None)
        assert len(result) == 3

    def test_no_match(self):
        df = _make_df()
        result = search_toilets(df, "存在しない場所")
        assert len(result) == 0

    def test_case_insensitive(self):
        df = _make_df()
        result = search_toilets(df, "カフェa")
        assert len(result) == 1


class TestHaversineDistance:
    def test_same_point(self):
        d = haversine_distance(35.68, 139.69, 35.68, 139.69)
        assert d == pytest.approx(0.0, abs=0.01)

    def test_tokyo_osaka(self):
        d = haversine_distance(35.6762, 139.6503, 34.6863, 135.5197)
        assert 390 < d < 420

    def test_series_input(self):
        lat2 = pd.Series([35.70, 34.69], index=["tokyo", "osaka"])
        lng2 = pd.Series([139.70, 135.50], index=["tokyo", "osaka"])
        result = haversine_distance(35.68, 139.69, lat2, lng2)
        assert isinstance(result, pd.Series)
        assert list(result.index) == ["tokyo", "osaka"]
        assert len(result) == 2
        assert result["tokyo"] < 5.0


class TestApplyEquipmentFilter:
    def test_multi_keyword_maps_to_has_multi(self):
        df = pd.DataFrame({"has_multi": [True, False, True], "title": ["A", "B", "C"]})
        result = _apply_equipment_filter(df, "__keyword__multi")
        assert len(result) == 2
        assert list(result["title"]) == ["A", "C"]

    def test_diaper_keyword_maps_to_has_diaper(self):
        df = pd.DataFrame({"has_diaper": [True, False], "title": ["A", "B"]})
        result = _apply_equipment_filter(df, "__keyword__diaper")
        assert len(result) == 1
        assert result.iloc[0]["title"] == "A"

    def test_wheelchair_keyword_maps_to_has_wheelchair(self):
        df = pd.DataFrame({"has_wheelchair": [True, False], "title": ["A", "B"]})
        result = _apply_equipment_filter(df, "__keyword__wheelchair")
        assert len(result) == 1
        assert result.iloc[0]["title"] == "A"

    def test_unknown_keyword_returns_unchanged(self):
        df = pd.DataFrame({"title": ["A", "B"]})
        result = _apply_equipment_filter(df, "__keyword__unknown")
        assert len(result) == 2

    def test_missing_column_returns_unchanged(self):
        df = pd.DataFrame({"title": ["A", "B"]})
        result = _apply_equipment_filter(df, "__keyword__multi")
        assert len(result) == 2

    def test_non_keyword_pattern_returns_unchanged(self):
        df = pd.DataFrame({"title": ["A", "B"]})
        result = _apply_equipment_filter(df, "カフェ|喫茶")
        assert len(result) == 2


class TestSearchToiletsEdgeCases:
    def test_score_range_search(self):
        df = pd.DataFrame([
            {"title": "A", "address": "X", "category": "C", "toilet_score": 80},
            {"title": "B", "address": "X", "category": "C", "toilet_score": 50},
            {"title": "C", "address": "X", "category": "C", "toilet_score": 30},
        ])
        result = search_toilets(df, "40-90")
        assert len(result) == 2
        assert list(result["toilet_score"]) == [80, 50]

    def test_whitespace_only_query_returns_all(self):
        df = pd.DataFrame([{"title": "A", "address": "B", "category": "C"}])
        result = search_toilets(df, "  ")
        assert len(result) == 1

    def test_empty_after_split_returns_all(self):
        df = pd.DataFrame([{"title": "A", "address": "B", "category": "C"}])
        result = search_toilets(df, ",")
        assert len(result) == 1

    def test_multi_word_search(self):
        df = pd.DataFrame([
            {"title": "東京タワートイレ", "address": "東京都港区", "category": "公園"},
            {"title": "大阪城トイレ", "address": "大阪市", "category": "公園"},
        ])
        result = search_toilets(df, "東京 港区")
        assert len(result) == 1
        assert result.iloc[0]["title"] == "東京タワートイレ"


class TestFilterToiletsEdgeCases:
    def test_equipment_filter(self):
        df = pd.DataFrame([
            {"title": "A", "category": "公園", "is_public_toilet": False,
             "prefecture": "東京都", "has_multi": True, "has_diaper": False},
            {"title": "B", "category": "公園", "is_public_toilet": False,
             "prefecture": "東京都", "has_multi": False, "has_diaper": False},
        ])
        result = filter_toilets(df, "多目的トイレ")
        assert len(result) == 1
        assert result.iloc[0]["title"] == "A"

    def test_barrier_free_no_equip_columns_returns_all(self):
        df = pd.DataFrame({"title": ["A", "B"], "category": "公園", "is_public_toilet": False, "prefecture": "東京都"})
        result = _apply_equipment_filter(df, "__keyword__barrier_free")
        assert len(result) == 2

    def test_barrier_free_or_combines_multiple_columns(self):
        df = pd.DataFrame({
            "title": ["A", "B", "C"],
            "has_multi": [True, False, False],
            "has_diaper": [False, True, False],
            "has_wheelchair": [False, False, False],
        })
        result = _apply_equipment_filter(df, "__keyword__barrier_free")
        assert len(result) == 2
        assert list(result["title"]) == ["A", "B"]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
