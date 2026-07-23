"""
ui/sidebar.py
StreamlitのサイドバーUIを描画する

存在理由: app.pyからサイドバーUIを分離し責務を明確にするため
関連ファイル: app.py, ui/i18n.py, ui/query_params.py, ui/data_loader.py
"""

import time
from typing import NamedTuple

import streamlit as st
from streamlit_js_eval import streamlit_js_eval

from app_config import FILTER_CONFIG, FILTER_I18N_KEYS, TILE_OPTIONS
from ui.i18n import LANGUAGE_OPTIONS, LANGUAGES, get_language_strings
from ui.query_params import resolve_ui_state_from_query_params


class SidebarResult(NamedTuple):
    t: dict
    lang: str
    selected_pref: str
    filter_type: str
    search_query: str
    sort_order: str
    user_location: tuple | None
    gps_enabled: bool
    dark_mode: bool
    selected_tile: str
    translated_to_internal: dict


def get_translated_filters(
    lang: str,
) -> tuple[dict[str, str | None], dict[str, str]]:
    """
    フィルタ表示名と内部値のマッピングを生成する
    """
    t = LANGUAGES[lang]
    display_to_value = {}
    display_to_internal = {}
    for ja_key, i18n_key in FILTER_I18N_KEYS.items():
        display_to_value[t[i18n_key]] = FILTER_CONFIG[ja_key]
        display_to_internal[t[i18n_key]] = ja_key
    return display_to_value, display_to_internal


def build_geolocation_js() -> str:
    """位置情報取得のJavaScript式を生成する"""
    return (
        "new Promise(resolve => navigator.geolocation.getCurrentPosition("
        "pos => resolve({latitude: pos.coords.latitude, longitude: pos.coords.longitude}), "
        "err => resolve({error: err.message})"
        "))"
    )


def _handle_gps_section(t: dict) -> tuple[tuple | None, bool]:
    user_location = None
    gps_enabled = st.checkbox(t["gps"], key="gps_enabled")
    st.caption(t["gps_hint"])
    if not gps_enabled:
        st.session_state.pop("_user_location", None)
        st.session_state.pop("_gps_error", None)
        st.session_state.pop("_gps_attempt", None)
    elif "_user_location" not in st.session_state and "_gps_error" not in st.session_state:
        max_attempts = 2
        attempt = st.session_state.get("_gps_attempt", 0)
        loc = None
        while attempt < max_attempts:
            loc = streamlit_js_eval(
                js_expressions=build_geolocation_js(), key=f"location_{attempt}"
            )
            if isinstance(loc, dict):
                if "latitude" in loc and "longitude" in loc:
                    break
                if "error" in loc:
                    attempt += 1
                    st.session_state["_gps_attempt"] = attempt
                    if attempt < max_attempts:
                        time.sleep(2 ** attempt)
                    continue
            break
        if isinstance(loc, dict):
            if "latitude" in loc and "longitude" in loc:
                st.session_state["_user_location"] = (
                    loc["latitude"],
                    loc["longitude"],
                )
            elif "error" in loc:
                st.session_state["_gps_error"] = loc["error"]

    if "_user_location" in st.session_state:
        user_location = st.session_state["_user_location"]
        st.info(
            f"{t['location_acquired']}: {user_location[0]:.4f}, {user_location[1]:.4f}"
        )
    elif "_gps_error" in st.session_state:
        st.warning(
            f"⚠️ {t['gps']}: {st.session_state['_gps_error']}. {t['gps_error_hint']}"
        )
    return user_location, gps_enabled


def _render_query_state_section(
    query_params: dict,
    prefectures: list[str],
    translated_to_internal: dict[str, str],
    t: dict,
) -> None:
    ui_state = resolve_ui_state_from_query_params(
        query_params, prefectures, translated_to_internal, t
    )
    for key, value in ui_state.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _render_filter_section(
    t: dict,
    prefectures: list[str],
    translated_filters: dict[str, str | None],
) -> tuple[str, str, str, str]:
    selected_pref = st.selectbox(t["prefecture"], prefectures, key="pref_select")
    filter_type = st.selectbox(
        t["filter"], list(translated_filters.keys()), key="filter_select"
    )
    search_query = st.text_input(
        t["search_label"],
        "",
        placeholder=t["search_placeholder"],
        key="search_input",
    )
    sort_order = st.radio(
        t["sort_label"],
        [t["sort_clean"], t["sort_near"]],
        horizontal=True,
        key="sort_select",
    )
    return selected_pref, filter_type, search_query, sort_order


def _render_settings_section(t: dict) -> tuple[bool, str]:
    dark_mode = st.checkbox(t["dark_mode"], key="dark_mode")
    selected_tile = st.selectbox(
        t["tile_select"], list(TILE_OPTIONS.keys()), key="tile_select"
    )
    return dark_mode, selected_tile


def render_sidebar(
    t: dict,
    prefectures: list[str],
    query_params: dict,
) -> SidebarResult:
    with st.sidebar:
        lang = st.selectbox(t["language_label"], LANGUAGE_OPTIONS, key="lang_select")
        t = get_language_strings(lang)
        translated_filters, translated_to_internal = get_translated_filters(lang)

        st.divider()
        _render_query_state_section(
            query_params, prefectures, translated_to_internal, t
        )

        st.divider()
        user_location, gps_enabled = _handle_gps_section(t)

        st.divider()
        selected_pref, filter_type, search_query, sort_order = _render_filter_section(
            t, prefectures, translated_filters
        )

        st.divider()
        dark_mode, selected_tile = _render_settings_section(t)

        st.caption(t["shortcut_info"])

    return SidebarResult(
        t=t,
        lang=lang,
        selected_pref=selected_pref,
        filter_type=filter_type,
        search_query=search_query,
        sort_order=sort_order,
        user_location=user_location,
        gps_enabled=gps_enabled,
        dark_mode=dark_mode,
        selected_tile=selected_tile,
        translated_to_internal=translated_to_internal,
    )
