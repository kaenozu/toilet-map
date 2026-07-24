"""Regression tests for full-source-review findings."""

from __future__ import annotations

import gzip
import json
import sqlite3

import app
from batch import pipeline, scoring
from ui.data_loader import toilets_to_dataframe
from ui.map_builder import MAX_MAP_MARKERS, _select_map_toilets
from ui.sidebar import SidebarResult


def test_empty_toilet_dataframe_has_required_columns():
    dataframe = toilets_to_dataframe([])

    assert dataframe.empty
    assert {
        "toilet_score",
        "prefecture",
        "title",
        "address",
        "category",
    }.issubset(dataframe.columns)


def test_build_filters_preserves_empty_optional_values():
    sidebar = SidebarResult(
        t={},
        lang="ja",
        selected_pref="全て",
        filter_type="すべて",
        search_query="",
        sort_order="score",
        user_location=None,
        gps_enabled=False,
        dark_mode=False,
        selected_tile="OpenStreetMap（標準）",
        translated_to_internal={},
    )

    assert app._build_filters(sidebar, "すべて") == {
        "prefecture": "全て",
        "filter_type": "すべて",
        "search_query": "",
        "user_location": None,
    }


def test_map_items_are_bounded_and_prioritize_confidence():
    toilets = [
        {
            "title": str(index),
            "confidence": index / (MAX_MAP_MARKERS + 10),
            "toilet_review_count": index,
            "toilet_score": 50,
        }
        for index in range(MAX_MAP_MARKERS + 10)
    ]

    selected = _select_map_toilets(toilets)

    assert len(selected) == MAX_MAP_MARKERS
    assert selected[0]["title"] == str(MAX_MAP_MARKERS + 9)


def test_mixed_absence_and_cleanliness_clause_is_scored():
    text = "駅にはトイレがないが、隣の公園のトイレはとても清潔だった。"

    assert scoring.mentions_toilet(text)
    score, matched = scoring.score_toilet_from_review(text)
    assert score > 0
    assert any(keyword.startswith("+") for keyword in matched)


def test_absence_only_review_is_rejected():
    assert not scoring.mentions_toilet("この駅にはトイレがありません。")


def test_tag_staged_snapshot_writes_matching_ids(tmp_path):
    json_path = tmp_path / "toilets.json.gz"
    db_path = tmp_path / "toilets.db"

    with gzip.open(json_path, "wt", encoding="utf-8") as file:
        json.dump({"metadata": {}, "toilets": []}, file)
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")

    pipeline._tag_staged_snapshot(str(json_path), str(db_path), "snapshot-1")

    with gzip.open(json_path, "rt", encoding="utf-8") as file:
        assert json.load(file)["metadata"]["snapshot_id"] == "snapshot-1"
    with sqlite3.connect(db_path) as connection:
        value = connection.execute("SELECT value FROM metadata WHERE key = 'snapshot_id'").fetchone()[0]
    assert value == "snapshot-1"


def test_map_error_message_does_not_include_exception(monkeypatch):
    messages: list[str] = []
    monkeypatch.setattr(
        app,
        "build_map",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("secret/path")),
    )
    monkeypatch.setattr(app.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(app.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(app.st, "error", messages.append)
    monkeypatch.setattr(app.st, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(app, "render_score_legend", lambda: None)
    monkeypatch.setattr(app, "render_stats", lambda *args, **kwargs: None)
    monkeypatch.setattr(app, "render_data_quality", lambda *args, **kwargs: None)
    monkeypatch.setattr(app, "calc_map_center", lambda *args: (35.0, 139.0, 10))

    app._render_main_content(
        total_items=0,
        total_pages=0,
        page=1,
        list_items=[],
        map_items=[],
        metadata={"center_lat": 35.0, "center_lng": 139.0, "zoom": 10},
        data_quality_summary={},
        translations={
            "showing": "件",
            "no_results": "none",
            "map_render_failed": "safe message",
        },
        selected_prefecture="全て",
        dark_mode=False,
        selected_tile="OpenStreetMap（標準）",
        query_elapsed_ms=0.0,
        prefecture_stats={},
    )

    assert messages == ["safe message"]
    assert "secret/path" not in messages[0]
