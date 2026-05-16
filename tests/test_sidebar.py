"""
tests/test_sidebar.py
ui/sidebar.py のユニットテスト
"""
import streamlit as st
from unittest.mock import MagicMock

from ui.sidebar import get_translated_filters, build_geolocation_js, render_sidebar, SidebarResult


class TestGetTranslatedFilters:
    def test_japanese_returns_correct_mapping(self):
        display_to_value, display_to_internal = get_translated_filters("日本語")
        assert "すべて" in display_to_value
        assert display_to_value["すべて"] is None
        assert "公共トイレ" in display_to_value
        assert display_to_internal["すべて"] == "すべて"
        assert display_to_internal["公共トイレ"] == "公共トイレ"

    def test_english_returns_correct_mapping(self):
        display_to_value, display_to_internal = get_translated_filters("English")
        assert "All" in display_to_value
        assert "Public toilets" in display_to_value
        assert display_to_internal["All"] == "すべて"
        assert display_to_internal["Public toilets"] == "公共トイレ"

    def test_both_languages_have_same_number_of_filters(self):
        ja_v, ja_i = get_translated_filters("日本語")
        en_v, en_i = get_translated_filters("English")
        assert len(ja_v) == len(en_v)
        assert len(ja_i) == len(en_i)

    def test_internal_values_match_filter_config(self):
        from app_config import FILTER_CONFIG
        _, display_to_internal = get_translated_filters("日本語")
        for display_name, ja_key in display_to_internal.items():
            assert ja_key in FILTER_CONFIG


class TestBuildGeolocationJs:
    def test_contains_promise_pattern(self):
        js = build_geolocation_js()
        assert "new Promise" in js
        assert "navigator.geolocation.getCurrentPosition" in js

    def test_resolves_with_latitude_longitude_on_success(self):
        js = build_geolocation_js()
        assert "latitude: pos.coords.latitude" in js
        assert "longitude: pos.coords.longitude" in js

    def test_resolves_with_error_on_failure(self):
        js = build_geolocation_js()
        assert "error: err.message" in js

    def test_does_not_contain_script_tag(self):
        js = build_geolocation_js()
        assert "<script" not in js
        assert "</script" not in js


class TestRenderSidebar:
    def test_returns_sidebar_result_type(self, monkeypatch):
        _mock_streamlit(monkeypatch)
        t = _make_minimal_t_dict()
        result = render_sidebar(t, ["全て", "東京都"], {})
        assert isinstance(result, SidebarResult)
        assert result.lang == "日本語"
        assert result.gps_enabled is False
        assert result.user_location is None

    def test_gps_disabled_clears_session_state(self, monkeypatch):
        _mock_streamlit(monkeypatch)
        monkeypatch.setattr("streamlit.session_state", {"_user_location": (35.0, 139.0), "lang_select": "日本語"})
        t = _make_minimal_t_dict()
        result = render_sidebar(t, ["全て"], {})
        assert result.gps_enabled is False
        assert "_user_location" not in st.session_state

    def test_resolves_query_params_to_session_state(self, monkeypatch):
        _mock_streamlit(monkeypatch)
        t = _make_minimal_t_dict()
        query_params = {"lang": "ja"}
        render_sidebar(t, ["全て", "東京都"], query_params)
        assert st.session_state.get("lang_select") == "日本語"

    def test_gps_enabled_and_location_acquired(self, monkeypatch):
        _mock_streamlit(monkeypatch)
        monkeypatch.setattr(st, "checkbox", lambda *a, **kw: True)
        monkeypatch.setattr("streamlit.session_state", {"lang_select": "日本語", "gps_enabled": True})
        monkeypatch.setattr("ui.sidebar.streamlit_js_eval", lambda **kw: {"latitude": 35.68, "longitude": 139.69})
        t = _make_minimal_t_dict()
        result = render_sidebar(t, ["全て"], {})
        assert result.user_location == (35.68, 139.69)

    def test_gps_enabled_with_error(self, monkeypatch):
        _mock_streamlit(monkeypatch)
        monkeypatch.setattr(st, "checkbox", lambda *a, **kw: True)
        monkeypatch.setattr("streamlit.session_state", {"lang_select": "日本語", "gps_enabled": True})
        monkeypatch.setattr("ui.sidebar.streamlit_js_eval", lambda **kw: {"error": "User denied geolocation"})
        t = _make_minimal_t_dict()
        render_sidebar(t, ["全て"], {})

    def test_query_params_skipped_when_already_in_session(self, monkeypatch):
        _mock_streamlit(monkeypatch)
        monkeypatch.setattr("streamlit.session_state", {"lang_select": "English", "gps_enabled": False})
        t = _make_minimal_t_dict()
        query_params = {"lang": "ja"}
        render_sidebar(t, ["全て"], query_params)
        assert st.session_state.get("lang_select") == "English"


class TestHandleGpsSection:
    def test_gps_enabled_acquires_location(self, monkeypatch):
        from ui.sidebar import _handle_gps_section
        monkeypatch.setattr(st, "checkbox", lambda *a, **kw: True)
        monkeypatch.setattr(st, "caption", lambda *a: None)
        monkeypatch.setattr(st, "info", lambda *a: None)
        monkeypatch.setattr("streamlit.session_state", {"lang_select": "日本語", "gps_enabled": True})
        monkeypatch.setattr("ui.sidebar.streamlit_js_eval", lambda **kw: {"latitude": 35.68, "longitude": 139.69})
        t = _make_minimal_t_dict()
        loc, enabled = _handle_gps_section(t)
        assert loc == (35.68, 139.69)
        assert enabled is True


_SELECTBOX_VALUES = {
    "lang_select": "日本語",
    "pref_select": "全て",
    "filter_select": "すべて",
    "sort_select": "きれい度順",
    "tile_select": "OpenStreetMap（標準）",
}


def _mock_streamlit(monkeypatch):
    monkeypatch.setattr(st, "sidebar", MagicMock())
    monkeypatch.setattr(st, "selectbox", lambda *a, **kw: _SELECTBOX_VALUES.get(kw.get("key", ""), ""))
    monkeypatch.setattr(st, "checkbox", lambda *a, **kw: False)
    monkeypatch.setattr(st, "text_input", lambda *a, **kw: "")
    monkeypatch.setattr(st, "radio", lambda *a, **kw: "きれい度順")
    monkeypatch.setattr(st, "divider", lambda: None)
    monkeypatch.setattr(st, "caption", lambda *a: None)
    monkeypatch.setattr(st, "info", lambda *a: None)
    monkeypatch.setattr(st, "warning", lambda *a: None)
    monkeypatch.setattr(st, "markdown", lambda *a, **kw: None)
    monkeypatch.setattr("streamlit.session_state", {"lang_select": "日本語"})


def _make_minimal_t_dict():
    return {
        "language_label": "🌐 言語", "gps": "📍 GPS", "gps_hint": "",
        "prefecture": "Pref", "filter": "Filter", "search_label": "Search",
        "search_placeholder": "", "sort_label": "Sort", "sort_clean": "Clean",
        "sort_near": "Near", "dark_mode": "🌙", "tile_select": "Tile",
        "shortcut_info": "", "location_acquired": "", "stats": "",
        "stats_all": "", "total": "", "scored": "", "public": "",
        "avg_score": "",
    }
