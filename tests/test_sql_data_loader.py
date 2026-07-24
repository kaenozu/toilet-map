"""Regression tests for bounded SQLite map/list/count loading."""

from __future__ import annotations

import json
import sqlite3

import pytest

from ui.filters import build_where_clause


@pytest.fixture()
def sql_db(tmp_path, monkeypatch):
    import ui.sql_data_loader as data_loader

    db_path = tmp_path / "toilets.db"
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE toilets (
            id INTEGER PRIMARY KEY,
            source_id TEXT,
            title TEXT,
            category TEXT,
            address TEXT,
            lat REAL,
            lng REAL,
            phone TEXT,
            rating REAL,
            review_count INTEGER,
            link TEXT,
            is_public_toilet INTEGER,
            toilet_score REAL,
            confidence REAL,
            toilet_review_count INTEGER,
            prefecture TEXT,
            sample_reviews_json TEXT,
            top_keywords TEXT
        )
        """
    )
    connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
    for key, value in {
        "total": "5",
        "scored": "5",
        "public_toilets": "2",
        "center_lat": "35.5",
        "center_lng": "139.5",
        "zoom": "10",
    }.items():
        connection.execute("INSERT INTO metadata VALUES (?, ?)", (key, value))
    rows = [
        (1, "a", "東京 カフェ", "カフェ", "東京都港区", 35.65, 139.75, "", 4.2, 30, "", 0, 80, 0.7, 5, "東京都", "[]", json.dumps([["多目的", 2]], ensure_ascii=False)),
        (2, "b", "東京 公園", "公園", "東京都新宿区", 35.69, 139.70, "", 4.0, 20, "", 1, 65, 0.9, 10, "東京都", "[]", json.dumps([["車椅子", 1]], ensure_ascii=False)),
        (3, "c", "大阪 喫茶", "喫茶", "大阪府大阪市", 34.69, 135.50, "", 3.8, 10, "", 0, 90, 0.8, 8, "大阪府", "[]", json.dumps([["おむつ", 1]], ensure_ascii=False)),
        (4, "d", "東京 レストラン", "レストラン", "東京都渋谷区", 35.66, 139.71, "", 3.5, 5, "", 1, 50, 0.2, 1, "東京都", "[]", "[]"),
        (5, "e", "100% 店", "店舗", "東京都中央区", 35.68, 139.76, "", 4.8, 50, "", 0, 70, 0.95, 20, "東京都", "[]", "[]"),
    ]
    connection.executemany(
        "INSERT INTO toilets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    connection.commit()
    connection.close()

    monkeypatch.setattr(data_loader, "DB_PATH", str(db_path))
    monkeypatch.setattr(data_loader, "DATA_PATH", str(tmp_path / "unused.json.gz"))
    monkeypatch.setattr(data_loader, "ensure_snapshot_current", lambda *_: None)
    data_loader.clear_query_caches()
    yield data_loader
    data_loader.clear_query_caches()


def _filters(**overrides):
    values = {
        "prefecture": "全て",
        "filter_type": "すべて",
        "search_query": "",
        "user_location": None,
    }
    values.update(overrides)
    return values


def test_map_query_applies_confidence_order_limit_and_bounds(sql_db):
    assert [item["id"] for item in sql_db.load_map_items(None, _filters(), limit=3)] == [5, 2, 3]

    bounds = {
        "_southWest": {"lat": 35.64, "lng": 139.69},
        "_northEast": {"lat": 35.70, "lng": 139.72},
    }
    assert [item["id"] for item in sql_db.load_map_items(bounds, _filters())] == [2, 4]


def test_list_and_count_queries_apply_filters_search_and_pagination(sql_db):
    assert sql_db.count_items(_filters()) == 5
    assert [item["id"] for item in sql_db.load_list_items(_filters(), "score", page=1, per_page=2)] == [3, 1]
    assert [item["id"] for item in sql_db.load_list_items(_filters(), "score", page=2, per_page=2)] == [5, 2]

    assert sql_db.count_items(_filters(prefecture="東京都", search_query="東京 港区")) == 1
    assert sql_db.count_items(_filters(filter_type="公共トイレ")) == 2
    assert sql_db.count_items(_filters(filter_type="多目的トイレ")) == 1
    assert sql_db.count_items(_filters(search_query="60-85")) == 3


def test_literal_like_characters_and_near_sort_are_safe(sql_db):
    percent_items = sql_db.load_list_items(_filters(search_query="100%"), "score")
    assert [item["id"] for item in percent_items] == [5]

    nearby = sql_db.load_list_items(
        _filters(user_location=(35.69, 139.70)),
        "near",
        page=1,
        per_page=3,
    )
    assert nearby[0]["id"] == 2
    assert nearby[0]["distance"] == pytest.approx(0.0)


def test_aggregate_loaders_do_not_require_full_rows(sql_db):
    assert sql_db.load_prefectures() == ["全て", "大阪府", "東京都"]
    assert sql_db.load_metadata()["total"] == 5
    assert sql_db.load_prefecture_stats()["東京都"]["count"] == 4
    assert sql_db.load_data_quality_summary()["missing"]["total"] == 5


def test_sql_builder_uses_parameters_for_and_search():
    where_sql, params = build_where_clause(
        _filters(prefecture="東京都", filter_type="カフェ・飲食", search_query="東京 港区")
    )
    assert "prefecture = ?" in where_sql
    assert "東京" not in where_sql
    assert "港区" not in where_sql
    assert params[0] == "東京都"
    assert where_sql.count("LIKE ?") >= 5
