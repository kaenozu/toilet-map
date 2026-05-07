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
from ui.components import render_score_legend, render_toilet_card, build_result_context_text
from ui.data_loader import load_toilet_data, toilets_to_dataframe, get_prefectures
from ui.filters import filter_toilets, search_toilets
from ui.stats import render_stats
from ui.map_builder import build_map, calc_map_center
from ui.pagination import render_csv_export
from ui.i18n import LANGUAGES

FILTER_LABEL_MAP = {
    "すべて": "filter_all",
    "公共トイレ": "filter_public",
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


def main():
    st.set_page_config(
        page_title="🚽 トイレきれい度マップ",
        page_icon="🚽",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(MOBILE_CSS, unsafe_allow_html=True)
    st.markdown('<link rel="manifest" href="/static/manifest.json">', unsafe_allow_html=True)

    lang = st.selectbox("🌐 Language", list(LANGUAGES.keys()), key="lang_select")
    t = LANGUAGES[lang]
    translated_filters, translated_to_internal = get_translated_filters(lang)

    user_location = None
    if st.checkbox(t["gps"]):
        loc = streamlit_js_eval(js_expressions="new Promise(resolve => navigator.geolocation.getCurrentPosition(pos => resolve(pos.coords)))", key="location")
        if loc:
            user_location = (loc["latitude"], loc["longitude"])
            st.info(f"{t['location_acquired']}: {user_location[0]:.4f}, {user_location[1]:.4f}")

    data = load_toilet_data()
    meta = data["metadata"]
    toilets = data["toilets"]
    prefecture_stats = data.get("pref_stats", {})

    st.title(t["title"])

    df = toilets_to_dataframe(toilets)
    prefectures = get_prefectures(df)

    render_stats(meta, toilets, t)

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

    render_csv_export(filtered, selected_pref, filter_type, t)
    map_items = filtered.to_dict("records")
    page_items = filtered

    st.markdown(f"**{total_items}{t['showing']}**")
    render_score_legend()

    map_started_at = perf_counter()
    m = build_map(map_items, map_lat, map_lng, map_zoom)
    map_elapsed_ms = (perf_counter() - map_started_at) * 1000
    st.caption(
        build_result_context_text(
            len(page_items),
            total_items,
            len(map_items),
            filter_elapsed_ms,
            map_elapsed_ms,
        )
    )
    st_folium(m, height=500, returned_objects=[], use_container_width=True)

    st.divider()
    for i, (_, row) in enumerate(page_items.iterrows()):
        render_toilet_card(row.to_dict(), rank=i + 1)


if __name__ == "__main__":
    main()
