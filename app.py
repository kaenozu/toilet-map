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
from ui.data_quality import render_data_quality
from ui.map_builder import build_map, calc_map_center
from ui.i18n import APP_TITLE, DEFAULT_LANGUAGE, get_language_strings
from ui.pagination import init_page_state, reset_page, calc_pagination, render_pagination
from ui.query_params import (
    read_query_params, write_query_params, apply_language_query_param,
    build_query_params_from_state,
)
from ui.sidebar import render_sidebar


def main():
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="🚽",
        layout="wide",
    )
    st.markdown(
        """
        <style>
        [data-testid="stSidebarNav"] {
            display: none !important;
        }
        </style>
        <link rel="manifest" href="/static/manifest.json">
        <meta name="theme-color" content="#1a73e8">
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <script>
        document.addEventListener('keydown', function(e) {
          if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
          if (e.key === 'g' && !e.ctrlKey && !e.metaKey) {
            var gps = document.querySelector('input[aria-label*="GPS" i]');
            if (gps) { gps.click(); e.preventDefault(); }
          }
          if (e.key === '/' && !e.ctrlKey && !e.metaKey) {
            var search = document.querySelector('input[aria-label*="検索" i]');
            if (search) { search.focus(); e.preventDefault(); }
          }
        });
        </script>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(MOBILE_CSS, unsafe_allow_html=True)

    query_params = read_query_params()
    apply_language_query_param(query_params)

    current_lang = st.session_state.get("lang_select", DEFAULT_LANGUAGE)
    t = get_language_strings(current_lang)

    data = load_toilet_data(get_data_cache_token())
    meta = data["metadata"]
    toilets = data["toilets"]
    prefecture_stats = data.get("pref_stats", {})

    df = toilets_to_dataframe(toilets)
    prefectures = get_prefectures(df)

    sidebar_result = render_sidebar(t, prefectures, query_params)
    t = sidebar_result.t
    lang = sidebar_result.lang
    selected_pref = sidebar_result.selected_pref
    filter_type = sidebar_result.filter_type
    search_query = sidebar_result.search_query
    sort_order = sidebar_result.sort_order
    user_location = sidebar_result.user_location
    gps_enabled = sidebar_result.gps_enabled
    translated_to_internal = sidebar_result.translated_to_internal

    internal_filter = translated_to_internal[filter_type]
    user_lat, user_lng = user_location if user_location else (None, None)
    filter_started_at = perf_counter()
    filtered = filter_toilets(df, internal_filter, selected_pref, user_lat, user_lng)
    filtered = search_toilets(filtered, search_query)

    if sort_order == t["sort_near"] and user_location:
        filtered = filtered.sort_values("distance", ascending=True)
    else:
        filtered = filtered.sort_values("toilet_score", ascending=False)
    filter_elapsed_ms = (perf_counter() - filter_started_at) * 1000

    st.title(t["title"])
    st.caption(build_data_freshness_text(meta, t))

    map_lat, map_lng, map_zoom = calc_map_center(selected_pref, meta, prefecture_stats)
    total_items = len(filtered)

    map_items = filtered.to_dict("records")

    init_page_state()
    page_filter_key = f"{selected_pref}|{internal_filter}|{search_query}"
    reset_page(page_filter_key)
    page = st.session_state.get("page", 1)
    total_pages, start_idx, end_idx, page = calc_pagination(total_items, page)
    display_items = filtered.iloc[start_idx:end_idx] if total_items > 0 else filtered

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

    render_stats(meta, map_items, t)
    render_data_quality(meta, toilets, t)

    if total_items > 0:
        render_pagination(total_items, page, total_pages, t)

    if len(display_items) == 0:
        st.info(t["no_results"])
    else:
        st.divider()
        st.markdown('<div role="list">', unsafe_allow_html=True)
        for i, (_, row) in enumerate(display_items.iterrows()):
            render_toilet_card(row.to_dict(), rank=i + 1, meta=meta)
        st.markdown('</div>', unsafe_allow_html=True)

    write_query_params(
        build_query_params_from_state(
            lang, selected_pref, internal_filter, search_query,
            sort_order, gps_enabled, page, t,
        )
    )


if __name__ == "__main__":
    main()
