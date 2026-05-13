"""
toilet-map/app.py
Streamlit版トイレきれい度マップ
"""

from time import perf_counter

import streamlit as st
from streamlit_folium import st_folium
from ui.styles import MOBILE_CSS
from ui.components import build_data_freshness_text, build_result_context_text, render_score_legend, render_toilet_card
from ui.data_loader import load_toilet_data, toilets_to_dataframe, get_prefectures, get_data_cache_token
from ui.filters import filter_toilets, search_toilets
from ui.stats import render_stats
from ui.map_builder import build_map, calc_map_center
from ui.i18n import APP_TITLE, DEFAULT_LANGUAGE, get_language_strings
from ui.pagination import init_page_state, reset_page, calc_pagination, render_pagination
from ui.query_params import (
    read_query_params, write_query_params, apply_language_query_param,
    build_query_params_from_state,
)
from ui.sidebar import render_sidebar, get_translated_filters


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
        """,
        unsafe_allow_html=True,
    )
    st.markdown(MOBILE_CSS, unsafe_allow_html=True)

    query_params = read_query_params()
    apply_language_query_param(query_params)

    current_lang = st.session_state.get("lang_select", DEFAULT_LANGUAGE)
    t = get_language_strings(current_lang)
    translated_filters, translated_to_internal = get_translated_filters(current_lang)

    data = load_toilet_data(get_data_cache_token())
    meta = data["metadata"]
    toilets = data["toilets"]
    prefecture_stats = data.get("pref_stats", {})

    df = toilets_to_dataframe(toilets)
    prefectures = get_prefectures(df)

    t, lang, selected_pref, filter_type, search_query, sort_order, user_location, gps_enabled = render_sidebar(
        t, prefectures, translated_filters, translated_to_internal, query_params
    )
    translated_filters, translated_to_internal = get_translated_filters(lang)

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

    if total_items > 0:
        render_pagination(total_items, page, total_pages, t)

    if len(display_items) == 0:
        st.info(t["no_results"])
    else:
        st.divider()
        for _, row in display_items.iterrows():
            render_toilet_card(row.to_dict(), meta)

    write_query_params(
        build_query_params_from_state(
            lang, selected_pref, internal_filter, search_query,
            sort_order, gps_enabled, page, t,
        )
    )


if __name__ == "__main__":
    main()
