"""
toilet-map/app.py
Streamlit版トイレきれい度マップ
"""

from time import perf_counter

import streamlit as st
from streamlit_folium import st_folium
from streamlit_js_eval import streamlit_js_eval
from app_config import FILTER_CONFIG
from ui.styles import MOBILE_CSS
from ui.components import build_data_freshness_text, build_result_context_text, render_score_legend, render_toilet_card
from ui.data_loader import load_toilet_data, toilets_to_dataframe, get_prefectures, get_data_cache_token
from ui.filters import filter_toilets, search_toilets
from ui.stats import render_stats
from ui.map_builder import build_map, calc_map_center
from ui.i18n import APP_TITLE, DEFAULT_LANGUAGE, LANGUAGES, LANGUAGE_OPTIONS, get_language_strings

FILTER_LABEL_MAP = {
    "すべて": "filter_all",
    "公共トイレ": "filter_public",
    "多目的トイレ": "filter_multi",
    "おむつ替え": "filter_diaper",
    "車椅子対応": "filter_wheelchair",
    "カフェ・飲食": "filter_cafe",
    "コンビニ・店舗": "filter_convenience",
    "ホテル・旅館": "filter_hotel",
    "道の駅": "filter_roadstation",
    "SA・PA": "filter_sapa",
}

def get_translated_filters(lang: str) -> tuple[dict, dict]:
    t = LANGUAGES[lang]
    display_to_value = {}
    display_to_internal = {}
    for ja_key, i18n_key in FILTER_LABEL_MAP.items():
        display_to_value[t[i18n_key]] = FILTER_CONFIG[ja_key]
        display_to_internal[t[i18n_key]] = ja_key
    return display_to_value, display_to_internal


def build_geolocation_js() -> str:
    """Streamlit へ渡す geolocation Promise を JSON 互換オブジェクトで返す。"""
    return (
        "new Promise(resolve => navigator.geolocation.getCurrentPosition("
        "pos => resolve({latitude: pos.coords.latitude, longitude: pos.coords.longitude}), "
        "err => resolve({error: err.message})"
        "))"
    )


def main():
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="🚽",
        layout="wide",
    )
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"],
        [data-testid="stSidebarNav"],
        [data-testid="collapsedControl"] {
            display: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(MOBILE_CSS, unsafe_allow_html=True)

    current_lang = st.session_state.get("lang_select", DEFAULT_LANGUAGE)
    t = get_language_strings(current_lang)
    lang = st.selectbox(t["language_label"], LANGUAGE_OPTIONS, key="lang_select")
    t = get_language_strings(lang)
    translated_filters, translated_to_internal = get_translated_filters(lang)

    user_location = None
    gps_enabled = st.checkbox(t["gps"], key="gps_enabled")
    if not gps_enabled:
        st.session_state.pop("_user_location", None)
        st.session_state.pop("_gps_error", None)
    elif "_user_location" not in st.session_state and "_gps_error" not in st.session_state:
        loc = streamlit_js_eval(js_expressions=build_geolocation_js(), key="location")
        if isinstance(loc, dict):
            if "latitude" in loc and "longitude" in loc:
                st.session_state["_user_location"] = (loc["latitude"], loc["longitude"])
            elif "error" in loc:
                st.session_state["_gps_error"] = loc["error"]

    if "_user_location" in st.session_state:
        user_location = st.session_state["_user_location"]
        st.info(f"{t['location_acquired']}: {user_location[0]:.4f}, {user_location[1]:.4f}")
    elif "_gps_error" in st.session_state:
        st.warning(f"⚠️ {t['gps']}: {st.session_state['_gps_error']}. {t['gps_error_hint']}")

    data = load_toilet_data(get_data_cache_token())
    meta = data["metadata"]
    toilets = data["toilets"]
    prefecture_stats = data.get("pref_stats", {})

    st.title(t["title"])
    st.caption(build_data_freshness_text(meta, t))

    df = toilets_to_dataframe(toilets)
    prefectures = get_prefectures(df)

    col_pref, col_filter, col_search = st.columns([1, 1, 2])
    with col_pref:
        selected_pref = st.selectbox(t["prefecture"], prefectures, key="pref_select")
    with col_filter:
        filter_type = st.selectbox(t["filter"], list(translated_filters.keys()), key="filter_select")
    with col_search:
        search_query = st.text_input(t["search_label"], "", placeholder=t["search_placeholder"], key="search_input")

    internal_filter = translated_to_internal[filter_type]
    sort_order = st.radio(t["sort_label"], [t["sort_clean"], t["sort_near"]], horizontal=True)

    user_lat, user_lng = user_location if user_location else (None, None)
    filter_started_at = perf_counter()
    filtered = filter_toilets(df, internal_filter, selected_pref, user_lat, user_lng)
    filtered = search_toilets(filtered, search_query)

    if sort_order == t["sort_near"] and user_location:
        filtered = filtered.sort_values("distance", ascending=True)
    else:
        filtered = filtered.sort_values("toilet_score", ascending=False)
    filter_elapsed_ms = (perf_counter() - filter_started_at) * 1000

    map_lat, map_lng, map_zoom = calc_map_center(selected_pref, meta, prefecture_stats)
    total_items = len(filtered)

    map_items = filtered.to_dict("records")
    display_items = filtered

    st.markdown(f"**{total_items}{t['showing']}**")
    render_score_legend()

    map_started_at = perf_counter()
    m = build_map(map_items, map_lat, map_lng, map_zoom)
    map_elapsed_ms = (perf_counter() - map_started_at) * 1000

    st.caption(
        build_result_context_text(
            len(display_items),
            len(map_items),
            filter_elapsed_ms,
            map_elapsed_ms,
            t,
        )
    )
    st_folium(m, height=500, returned_objects=[], use_container_width=True)

    # ===== 統計を地図の下に表示 =====
    render_stats(meta, map_items, t)

    if len(display_items) == 0:
        st.info(t["no_results"])
    else:
        st.divider()
        for i, (_, row) in enumerate(display_items.iterrows()):
            render_toilet_card(row.to_dict(), rank=i + 1)


if __name__ == "__main__":
    main()
