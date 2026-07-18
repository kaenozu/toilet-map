"""Streamlit toilet cleanliness map."""

from time import perf_counter
from typing import cast

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from app_config import TILE_OPTIONS
from ui.components import build_data_freshness_text, build_result_context_text, render_score_legend, render_toilet_card
from ui.data_loader import get_data_cache_token, get_prefectures, load_toilet_data, toilets_to_dataframe
from ui.data_quality import render_data_quality
from ui.filters import filter_toilets, search_toilets
from ui.i18n import APP_TITLE, DEFAULT_LANGUAGE, get_language_strings
from ui.map_builder import build_map, calc_map_center
from ui.pagination import calc_pagination, init_page_state, render_pagination, reset_page
from ui.query_params import (
    apply_language_query_param,
    build_query_params_from_state,
    read_query_params,
    write_query_params,
)
from ui.sidebar import render_sidebar
from ui.stats import render_stats
from ui.styles import DARK_MODE_CSS, MOBILE_CSS
from ui.types import ToiletDict


def _load_and_prepare() -> tuple[dict, pd.DataFrame, list[str], dict, dict, dict, list]:
    query_params = read_query_params()
    apply_language_query_param(query_params)
    current_lang = st.session_state.get("lang_select", DEFAULT_LANGUAGE)
    translations = get_language_strings(current_lang)
    data = load_toilet_data(get_data_cache_token())
    metadata = data["metadata"]
    toilets = data["toilets"]
    dataframe = toilets_to_dataframe(toilets)
    return metadata, dataframe, get_prefectures(dataframe), data.get("pref_stats", {}), translations, query_params, toilets


def _process_filters(
    dataframe: pd.DataFrame,
    selected_prefecture: str,
    internal_filter: str,
    search_query: str,
    sort_order: str,
    user_location: tuple | None,
    translations: dict,
) -> tuple[pd.DataFrame, float]:
    user_lat, user_lng = user_location if user_location else (None, None)
    started_at = perf_counter()
    filtered = filter_toilets(dataframe, internal_filter, selected_prefecture, user_lat, user_lng)
    filtered = search_toilets(filtered, search_query)
    if sort_order == translations["sort_near"] and user_location:
        filtered = filtered.sort_values("distance", ascending=True)
    else:
        filtered = filtered.sort_values("toilet_score", ascending=False)
    return filtered, (perf_counter() - started_at) * 1000


def _render_main_content(
    filtered: pd.DataFrame,
    map_items: list[ToiletDict],
    metadata: dict,
    translations: dict,
    selected_prefecture: str,
    sort_order: str,
    dark_mode: bool,
    selected_tile: str,
    toilets: list,
    filter_elapsed_ms: float,
    prefecture_stats: dict,
    internal_filter: str,
    search_query: str,
) -> tuple[bool, int, pd.DataFrame]:
    del sort_order
    map_lat, map_lng, map_zoom = calc_map_center(selected_prefecture, metadata, prefecture_stats)
    total_items = len(filtered)
    init_page_state()
    reset_page(f"{selected_prefecture}|{internal_filter}|{search_query}")
    page = st.session_state.get("page", 1)
    total_pages, start_index, end_index, page = calc_pagination(total_items, page)
    display_items = filtered.iloc[start_index:end_index] if total_items else filtered

    st.markdown(f"**{total_items}{translations['showing']}**")
    render_score_legend()

    try:
        map_started_at = perf_counter()
        map_object = build_map(map_items, map_lat, map_lng, map_zoom, tile=TILE_OPTIONS[selected_tile])
        map_elapsed_ms = (perf_counter() - map_started_at) * 1000
        st.caption(
            build_result_context_text(
                len(display_items), len(map_items), filter_elapsed_ms, map_elapsed_ms, translations
            )
        )
        st_folium(map_object, height=500, returned_objects=[], use_container_width=True)
    except Exception as exc:
        st.error(f"Map rendering failed: {exc}")

    render_stats(metadata, map_items, translations)
    render_data_quality(metadata, toilets, translations)
    if total_items:
        render_pagination(total_items, page, total_pages, translations)
    if display_items.empty:
        st.info(translations["no_results"])
    else:
        st.divider()
        st.markdown('<div role="list">', unsafe_allow_html=True)
        for rank, (_, row) in enumerate(display_items.iterrows(), 1):
            render_toilet_card(row.to_dict(), rank=rank, meta=metadata)
        st.markdown("</div>", unsafe_allow_html=True)
    return dark_mode, page, display_items


def _inject_html() -> None:
    st.markdown(
        """
        <style>[data-testid="stSidebarNav"] { display:none!important; }</style>
        <link rel="manifest" href="/app/static/manifest.json">
        <meta name="theme-color" content="#1a73e8">
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <script>
        document.addEventListener('keydown', function(e) {
          if (['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)) return;
          if (e.key === 'g' && !e.ctrlKey && !e.metaKey) {
            const gps = document.querySelector('input[aria-label*="GPS" i]');
            if (gps) { gps.click(); e.preventDefault(); }
          }
          if (e.key === '/' && !e.ctrlKey && !e.metaKey) {
            const search = document.querySelector('input[aria-label*="検索" i],input[aria-label*="search" i]');
            if (search) { search.focus(); e.preventDefault(); }
          }
        });
        </script>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(MOBILE_CSS, unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="🚽", layout="wide")
    _inject_html()
    metadata, dataframe, prefectures, prefecture_stats, translations, query_params, toilets = _load_and_prepare()
    sidebar = render_sidebar(translations, prefectures, query_params)
    translations = sidebar.t
    internal_filter = sidebar.translated_to_internal[sidebar.filter_type]
    filtered, filter_elapsed_ms = _process_filters(
        dataframe,
        sidebar.selected_pref,
        internal_filter,
        sidebar.search_query,
        sidebar.sort_order,
        sidebar.user_location,
        translations,
    )
    st.title(translations["title"])
    st.caption(build_data_freshness_text(metadata, translations))
    dark_mode, page, display_items = _render_main_content(
        filtered,
        cast(list[ToiletDict], filtered.to_dict("records")),
        metadata,
        translations,
        sidebar.selected_pref,
        sidebar.sort_order,
        sidebar.dark_mode,
        sidebar.selected_tile,
        toilets,
        filter_elapsed_ms,
        prefecture_stats,
        internal_filter,
        sidebar.search_query,
    )
    if dark_mode:
        st.markdown(DARK_MODE_CSS, unsafe_allow_html=True)
    if st.session_state.get("_show_shortcuts", False):
        st.info(translations["shortcut_info"])
    if not display_items.empty:
        csv_data = filtered.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            translations.get("csv_download", "📥 CSVダウンロード"),
            csv_data,
            f"toilets_{sidebar.selected_pref}.csv",
            "text/csv",
            use_container_width=True,
        )
    write_query_params(
        build_query_params_from_state(
            sidebar.lang,
            sidebar.selected_pref,
            internal_filter,
            sidebar.search_query,
            sidebar.sort_order,
            sidebar.gps_enabled,
            page,
            translations,
            dark_mode=dark_mode,
        )
    )


if __name__ == "__main__":
    main()
