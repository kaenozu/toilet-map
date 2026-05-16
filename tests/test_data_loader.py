"""
tests/test_data_loader.py
ui/data_loader.py のユニットテスト
"""
import json
import sqlite3
import pytest
import pandas as pd
from unittest.mock import MagicMock

from app_config import ERROR_METADATA


class TestGetDataCacheToken:
    def test_returns_stat_values(self, monkeypatch):
        import ui.data_loader as dl
        monkeypatch.setattr("os.stat", lambda _: type("s", (), {"st_mtime_ns": 123, "st_size": 456})())
        assert dl.get_data_cache_token() == (123, 456)

    def test_returns_zero_on_filenotfound(self, monkeypatch):
        import ui.data_loader as dl

        def raise_fnf(_):
            raise FileNotFoundError()

        monkeypatch.setattr("os.stat", raise_fnf)
        assert dl.get_data_cache_token() == (0, 0)


class TestLoadToiletData:
    def make_mock_df(self, toilets, metadata):
        toilets_df = pd.DataFrame(toilets) if toilets else pd.DataFrame()
        meta_df = pd.DataFrame(
            [{"key": k, "value": v} for k, v in metadata.items()]
        ) if metadata else pd.DataFrame(columns=["key", "value"])
        return toilets_df, meta_df

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        import ui.data_loader as dl
        dl.load_toilet_data.clear()
        yield

    def test_loads_normal_data(self, monkeypatch):
        import ui.data_loader as dl

        mock_conn = MagicMock()
        monkeypatch.setattr(sqlite3, "connect", lambda _: mock_conn)
        toilets_df, meta_df = self.make_mock_df(
            [{"title": "A", "prefecture": "東京都", "lat": 35.0, "lng": 139.0, "sample_reviews_json": "[]"}],
            {"total": "1", "scored": "1", "public_toilets": "0"},
        )

        def mock_read_sql(sql, conn):
            return toilets_df if "toilets" in sql.lower() else meta_df

        monkeypatch.setattr(pd, "read_sql", mock_read_sql)

        result = dl.load_toilet_data()
        assert result["metadata"]["total"] == 1
        assert len(result["toilets"]) == 1
        assert result["toilets"][0]["sample_reviews"] == []
        assert "東京都" in result["pref_stats"]

    def test_empty_toilets_table(self, monkeypatch):
        import ui.data_loader as dl

        mock_conn = MagicMock()
        monkeypatch.setattr(sqlite3, "connect", lambda _: mock_conn)
        toilets_df, meta_df = self.make_mock_df([], {"total": "0"})

        def mock_read_sql(sql, conn):
            return toilets_df if "toilets" in sql.lower() else meta_df

        monkeypatch.setattr(pd, "read_sql", mock_read_sql)

        result = dl.load_toilet_data()
        assert result["metadata"]["total"] == 0
        assert result["toilets"] == []
        assert result["pref_stats"] == {}

    def test_loads_sample_reviews_from_json(self, monkeypatch):
        import ui.data_loader as dl

        mock_conn = MagicMock()
        monkeypatch.setattr(sqlite3, "connect", lambda _: mock_conn)
        reviews = [{"text": "きれい", "rating": 5}]
        toilets_df, meta_df = self.make_mock_df(
            [{"title": "B", "prefecture": "大阪府", "lat": 34.0, "lng": 135.0, "sample_reviews_json": json.dumps(reviews)}],
            {"total": "1"},
        )

        def mock_read_sql(sql, conn):
            return toilets_df if "toilets" in sql.lower() else meta_df

        monkeypatch.setattr(pd, "read_sql", mock_read_sql)

        result = dl.load_toilet_data()
        assert result["toilets"][0]["sample_reviews"] == reviews

    def test_handles_null_sample_reviews(self, monkeypatch):
        import ui.data_loader as dl

        mock_conn = MagicMock()
        monkeypatch.setattr(sqlite3, "connect", lambda _: mock_conn)
        toilets_df, meta_df = self.make_mock_df(
            [{"title": "C", "prefecture": "東京都", "lat": 35.0, "lng": 139.0, "sample_reviews_json": None}],
            {"total": "1"},
        )

        def mock_read_sql(sql, conn):
            return toilets_df if "toilets" in sql.lower() else meta_df

        monkeypatch.setattr(pd, "read_sql", mock_read_sql)

        result = dl.load_toilet_data()
        assert result["toilets"][0]["sample_reviews"] == []

    def test_invalid_top_keywords_json_falls_back_to_empty_list(self, monkeypatch):
        import ui.data_loader as dl

        mock_conn = MagicMock()
        monkeypatch.setattr(sqlite3, "connect", lambda _: mock_conn)
        toilets_df, meta_df = self.make_mock_df(
            [{"title": "E", "prefecture": "東京都", "lat": 35.0, "lng": 139.0, "sample_reviews_json": "[]", "top_keywords": "not-json"}],
            {"total": "1"},
        )

        def mock_read_sql(sql, conn):
            return toilets_df if "toilets" in sql.lower() else meta_df

        monkeypatch.setattr(pd, "read_sql", mock_read_sql)

        result = dl.load_toilet_data()
        assert result["toilets"][0]["top_keywords"] == []

    def test_invalid_sample_reviews_json_falls_back_to_empty_list(self, monkeypatch):
        import ui.data_loader as dl

        mock_conn = MagicMock()
        monkeypatch.setattr(sqlite3, "connect", lambda _: mock_conn)
        toilets_df, meta_df = self.make_mock_df(
            [{"title": "D", "prefecture": "東京都", "lat": 35.0, "lng": 139.0, "sample_reviews_json": "not-json"}],
            {"total": "1"},
        )

        def mock_read_sql(sql, conn):
            return toilets_df if "toilets" in sql.lower() else meta_df

        monkeypatch.setattr(pd, "read_sql", mock_read_sql)
        monkeypatch.setattr(dl.st, "warning", lambda msg: None)

        result = dl.load_toilet_data()
        assert result["toilets"][0]["sample_reviews"] == []

    def test_returns_error_metadata_on_exception(self, monkeypatch):
        import ui.data_loader as dl

        monkeypatch.setattr(sqlite3, "connect", lambda _: (_ for _ in ()).throw(sqlite3.OperationalError("DB error")))
        monkeypatch.setattr(dl.st, "error", lambda msg: None)

        result = dl.load_toilet_data()
        assert result["metadata"] == ERROR_METADATA
        assert result["toilets"] == []
        assert result["pref_stats"] == {}

    def test_prefecture_stats_ignores_empty_prefecture(self, monkeypatch):
        import ui.data_loader as dl

        mock_conn = MagicMock()
        monkeypatch.setattr(sqlite3, "connect", lambda _: mock_conn)
        toilets_df, meta_df = self.make_mock_df(
            [
                {"title": "A", "prefecture": "東京都", "lat": 35.0, "lng": 139.0, "sample_reviews_json": "[]"},
                {"title": "B", "prefecture": "", "lat": 36.0, "lng": 140.0, "sample_reviews_json": "[]"},
                {"title": "C", "prefecture": None, "lat": 37.0, "lng": 141.0, "sample_reviews_json": "[]"},
            ],
            {"total": "3"},
        )

        def mock_read_sql(sql, conn):
            return toilets_df if "toilets" in sql.lower() else meta_df

        monkeypatch.setattr(pd, "read_sql", mock_read_sql)

        result = dl.load_toilet_data()
        assert len(result["pref_stats"]) == 1
        assert "東京都" in result["pref_stats"]

    def test_metadata_type_conversion(self, monkeypatch):
        import ui.data_loader as dl

        mock_conn = MagicMock()
        monkeypatch.setattr(sqlite3, "connect", lambda _: mock_conn)
        toilets_df, meta_df = self.make_mock_df(
            [{"title": "A", "prefecture": "東京都", "lat": 35.0, "lng": 139.0, "sample_reviews_json": "[]"}],
            {"total": "5", "scored": "3", "public_toilets": "2", "zoom": "12", "center_lat": "35.5", "center_lng": "139.5"},
        )

        def mock_read_sql(sql, conn):
            return toilets_df if "toilets" in sql.lower() else meta_df

        monkeypatch.setattr(pd, "read_sql", mock_read_sql)

        result = dl.load_toilet_data()
        assert result["metadata"]["total"] == 5
        assert isinstance(result["metadata"]["total"], int)
        assert isinstance(result["metadata"]["center_lat"], float)


class TestToiletsToDataFrame:
    def test_basic_conversion(self):
        from ui.data_loader import toilets_to_dataframe

        toilets = [
            {"title": "A", "prefecture": "東京都", "lat": 35.0, "lng": 139.0, "top_keywords": [["きれい", 1]]},
        ]
        df = toilets_to_dataframe(toilets)
        assert len(df) == 1
        assert df.iloc[0]["title"] == "A"

    def test_adds_equipment_columns(self):
        from ui.data_loader import toilets_to_dataframe

        toilets = [
            {
                "title": "A",
                "top_keywords": [["多目的", 1], ["おむつ", 1]],
            },
        ]
        df = toilets_to_dataframe(toilets)
        assert df.iloc[0]["has_multi"]
        assert df.iloc[0]["has_diaper"]
        assert not df.iloc[0]["has_wheelchair"]

    def test_empty_list(self):
        from ui.data_loader import toilets_to_dataframe

        df = toilets_to_dataframe([])
        assert df.empty

    def test_missing_top_keywords(self):
        from ui.data_loader import toilets_to_dataframe

        toilets = [{"title": "B", "prefecture": "大阪府"}]
        df = toilets_to_dataframe(toilets)
        assert not df.iloc[0]["has_multi"]
        assert not df.iloc[0]["has_diaper"]
        assert not df.iloc[0]["has_wheelchair"]

    def test_non_list_top_keywords_returns_false(self):
        from ui.data_loader import toilets_to_dataframe

        toilets = [{"title": "C", "top_keywords": "not_a_list_string", "sample_reviews_json": "[]"}]
        df = toilets_to_dataframe(toilets)
        assert not df.iloc[0]["has_multi"]


class TestGetPrefectures:
    def test_returns_sorted_prefectures(self):
        from ui.data_loader import get_prefectures

        df = pd.DataFrame({"prefecture": ["大阪府", "東京都", "北海道"]})
        result = get_prefectures(df)
        assert result == ["全て", "北海道", "大阪府", "東京都"]

    def test_empty_dataframe(self):
        from ui.data_loader import get_prefectures

        df = pd.DataFrame({"prefecture": []})
        result = get_prefectures(df)
        assert result == ["全て"]

    def test_missing_prefecture_column(self):
        from ui.data_loader import get_prefectures

        df = pd.DataFrame({"name": ["A"]})
        result = get_prefectures(df)
        assert result == ["全て"]

    def test_deduplicates_prefectures(self):
        from ui.data_loader import get_prefectures

        df = pd.DataFrame({"prefecture": ["東京都", "東京都", "大阪府"]})
        result = get_prefectures(df)
        assert result == ["全て", "大阪府", "東京都"]
