"""
tests/test_filters.py
ui/filters.py のユニットテスト
"""
import pytest
import pandas as pd
import numpy as np
from ui.filters import filter_toilets, search_toilets, haversine_distance


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
        lat2 = pd.Series([35.70, 34.69])
        lng2 = pd.Series([139.70, 135.50])
        result = haversine_distance(35.68, 139.69, lat2, lng2)
        assert isinstance(result, pd.Series)
        assert len(result) == 2
        assert result.iloc[0] < 5.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
