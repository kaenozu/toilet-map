"""Integration-style coverage for the bounded SQL Streamlit flow."""

from __future__ import annotations

import app
from ui.sidebar import SidebarResult


def test_main_runs_bounded_sql_flow_without_loading_all_rows(monkeypatch):
    translations = {
        "title": "Toilet Map",
        "sort_near": "Near",
        "showing": "件",
        "no_results": "none",
        "csv_download": "CSV",
    }
    metadata = {"center_lat": 35.0, "center_lng": 139.0, "zoom": 10}
    item = {
        "id": 1,
        "title": "Test Toilet",
        "category": "公園",
        "address": "東京都",
        "lat": 35.0,
        "lng": 139.0,
        "is_public_toilet": True,
        "toilet_score": 80,
        "confidence": 0.9,
        "toilet_review_count": 3,
        "prefecture": "東京都",
        "sample_reviews": [],
        "top_keywords": [["多目的", 1]],
        "distance": 0.0,
    }
    session_state = {"page": 1}
    streamlit_calls: list[str] = []
    written_params: list[dict] = []

    monkeypatch.setattr(app.st, "session_state", session_state)
    for name in (
        "set_page_config",
        "markdown",
        "caption",
        "title",
        "divider",
        "info",
        "download_button",
    ):
        monkeypatch.setattr(
            app.st,
            name,
            lambda *args, _name=name, **kwargs: streamlit_calls.append(_name),
        )

    monkeypatch.setattr(app, "read_query_params", lambda: {})
    monkeypatch.setattr(app, "apply_language_query_param", lambda params: None)
    monkeypatch.setattr(app, "get_language_strings", lambda lang: translations)
    monkeypatch.setattr(app, "load_metadata", lambda: metadata)
    monkeypatch.setattr(app, "load_prefectures", lambda: ["全て", "東京都"])
    monkeypatch.setattr(app, "load_prefecture_stats", lambda: {"東京都": {"count": 1}})
    monkeypatch.setattr(app, "load_data_quality_summary", lambda: {"missing": {}})
    monkeypatch.setattr(
        app,
        "render_sidebar",
        lambda *args: SidebarResult(
            t=translations,
            lang="日本語",
            selected_pref="東京都",
            filter_type="すべて",
            search_query="",
            sort_order="score",
            user_location=(35.0, 139.0),
            gps_enabled=True,
            dark_mode=False,
            selected_tile=next(iter(app.TILE_OPTIONS)),
            translated_to_internal={"すべて": "すべて"},
        ),
    )
    monkeypatch.setattr(app, "count_items", lambda filters: 1)
    monkeypatch.setattr(app, "load_list_items", lambda *args, **kwargs: [item])
    monkeypatch.setattr(app, "load_map_items", lambda *args, **kwargs: [item])
    monkeypatch.setattr(app, "init_page_state", lambda: None)
    monkeypatch.setattr(app, "reset_page", lambda key: None)
    monkeypatch.setattr(app, "calc_pagination", lambda total, page, per_page: (1, 0, 1, 1))
    monkeypatch.setattr(app, "normalize_page", lambda page, total_pages: page)
    monkeypatch.setattr(app, "calc_map_center", lambda *args: (35.0, 139.0, 10))
    monkeypatch.setattr(app, "build_map", lambda *args, **kwargs: object())
    monkeypatch.setattr(
        app,
        "st_folium",
        lambda *args, **kwargs: {
            "bounds": {
                "_southWest": {"lat": 34.9, "lng": 138.9},
                "_northEast": {"lat": 35.1, "lng": 139.1},
            }
        },
    )
    monkeypatch.setattr(app, "build_result_context_text", lambda *args: "context")
    monkeypatch.setattr(app, "build_data_freshness_text", lambda *args: "fresh")
    monkeypatch.setattr(app, "render_score_legend", lambda: None)
    monkeypatch.setattr(app, "render_stats", lambda *args: None)
    monkeypatch.setattr(app, "render_data_quality", lambda *args: None)
    monkeypatch.setattr(app, "render_pagination", lambda *args: None)
    monkeypatch.setattr(app, "render_toilet_card", lambda *args, **kwargs: None)
    monkeypatch.setattr(app, "build_query_params_from_state", lambda *args, **kwargs: {"page": "1"})
    monkeypatch.setattr(app, "write_query_params", written_params.append)

    app.main()

    assert session_state["map_bounds"]["_southWest"]["lat"] == 34.9
    assert "download_button" in streamlit_calls
    assert written_params == [{"page": "1"}]
