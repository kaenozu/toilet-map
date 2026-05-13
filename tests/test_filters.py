"""
tests/test_filters.py
ui/filters.py のユニットテスト
"""
import pytest
import pandas as pd
from ui.filters import (
    filter_toilets, search_toilets, haversine_distance,
    filter_by_viewport, get_underserved_areas_in_viewport,
    _extract_bounds_coordinates, _apply_equipment_filter,
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


class TestExtractBoundsCoordinates:
    def test_valid_bounds(self):
        bounds = {
            "_southWest": {"lat": 35.6, "lng": 139.5},
            "_northEast": {"lat": 35.8, "lng": 139.8},
        }
        result = _extract_bounds_coordinates(bounds)
        assert result == (35.6, 139.5, 35.8, 139.8)

    def test_missing_southwest(self):
        bounds = {"_northEast": {"lat": 35.8, "lng": 139.8}}
        assert _extract_bounds_coordinates(bounds) is None

    def test_missing_northeast(self):
        bounds = {"_southWest": {"lat": 35.6, "lng": 139.5}}
        assert _extract_bounds_coordinates(bounds) is None

    def test_none_coordinates(self):
        bounds = {"_southWest": {"lat": None, "lng": None}, "_northEast": {"lat": None, "lng": None}}
        assert _extract_bounds_coordinates(bounds) is None

    def test_type_error_in_coordinates(self):
        bounds = {"_southWest": {"lat": "invalid", "lng": 139.5}, "_northEast": {"lat": 35.8, "lng": 139.8}}
        assert _extract_bounds_coordinates(bounds) is None

    def test_empty_dict(self):
        assert _extract_bounds_coordinates({}) is None


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


class TestViewportFilters:
    def test_filter_by_viewport_ignores_incomplete_bounds(self):
        df = _make_df()
        bounds = {"_southWest": {"lat": None, "lng": None}, "_northEast": {"lat": None, "lng": None}}

        result = filter_by_viewport(df, bounds)

        assert len(result) == len(df)

    def test_filter_by_viewport_ignores_none_bounds(self):
        df = _make_df()
        result = filter_by_viewport(df, None)
        assert len(result) == len(df)

    def test_filter_by_viewport_ignores_empty_dict(self):
        df = _make_df()
        result = filter_by_viewport(df, {})
        assert len(result) == len(df)

    def test_filter_by_viewport_filters_by_tokyo_bounds(self):
        df = _make_df()
        bounds = {
            "_southWest": {"lat": 35.6, "lng": 139.5},
            "_northEast": {"lat": 35.8, "lng": 139.8},
        }
        result = filter_by_viewport(df, bounds)
        assert len(result) == 2
        assert "カフェA" in result["title"].values
        assert "コンビニC" in result["title"].values

    def test_filter_by_viewport_excludes_outside_bounds(self):
        df = _make_df()
        bounds = {
            "_southWest": {"lat": 34.0, "lng": 135.0},
            "_northEast": {"lat": 35.0, "lng": 136.0},
        }
        result = filter_by_viewport(df, bounds)
        assert len(result) == 1
        assert result.iloc[0]["title"] == "公共トイレB"

    def test_get_underserved_areas_ignores_incomplete_bounds(self):
        stats = {"東京都": {"渋谷区": 5}}
        bounds = {"_southWest": {"lat": None, "lng": None}, "_northEast": {"lat": None, "lng": None}}

        result = get_underserved_areas_in_viewport(bounds, stats)

        assert result == []

    def test_get_underserved_areas_returns_empty_for_sufficient_stats(self):
        stats = {"東京都": {"渋谷区": 10, "新宿区": 15}}
        bounds = {
            "_southWest": {"lat": 35.0, "lng": 138.0},
            "_northEast": {"lat": 37.0, "lng": 141.0},
        }
        result = get_underserved_areas_in_viewport(bounds, stats)
        assert result == []

    def test_get_underserved_areas_includes_below_threshold(self):
        stats = {"東京都": {"渋谷区": 3, "新宿区": 50}}
        bounds = {
            "_southWest": {"lat": 35.0, "lng": 138.0},
            "_northEast": {"lat": 37.0, "lng": 141.0},
        }
        result = get_underserved_areas_in_viewport(bounds, stats)
        assert len(result) == 1
        assert result[0]["city"] == "渋谷区"
        assert result[0]["count"] == 3

    def test_get_underserved_areas_limits_to_max_suggestions(self):
        stats = {
            "東京都": {f"区{i}": 1 for i in range(10)},
        }
        bounds = {
            "_southWest": {"lat": 35.0, "lng": 138.0},
            "_northEast": {"lat": 37.0, "lng": 141.0},
        }
        result = get_underserved_areas_in_viewport(bounds, stats)
        assert len(result) <= 5

    def test_get_underserved_areas_falls_back_to_nearest_when_none_in_bounds(self):
        stats = {"東京都": {"千代田区": 2}}
        # bounds that don't include any prefecture center
        bounds = {
            "_southWest": {"lat": 30.0, "lng": 130.0},
            "_northEast": {"lat": 31.0, "lng": 131.0},
        }
        result = get_underserved_areas_in_viewport(bounds, stats)
        # should find underserved via nearest prefecture fallback
        assert len(result) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
