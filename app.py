"""Streamlit toilet cleanliness map backed by bounded SQLite queries."""

from __future__ import annotations

import csv
import io
import json
import logging
from time import perf_counter

import streamlit as st
from streamlit_folium import st_folium

from app_config import TILE_OPTIONS
from ui.components import build_data_freshness_text, build_result_context_text, render_score_legend, render_toilet_card
from ui.data_quality import render_data_quality
from ui.filters import _extract_bounds_coordinates
from ui.i18n import APP_TITLE, DEFAULT_LANGUAGE, get_language_strings
from ui.map_builder import MAX_MAP_MARKERS, build_map, calc_map_center
from ui.pagination import PER_PAGE, calc_pagination, init_page_state, normalize_page, render_pagination, reset_page
from ui.query_params import (
    apply_language_query_param,
    build_query_params_from_state,
    read_query_params,
    write_query_params,
)
from ui.sidebar import SidebarResult, render_sidebar
from ui.sql_data_loader import (
    TOILET_COLUMNS,
    count_items,
    load_data_quality_summary,
    load_list_items,
    load_map_items,
    load_metadata,
    load_prefecture_stats,
    load_prefectures,
)
from ui.stats import render_stats
from ui.styles import DARK_MODE_CSS, MOBILE_CSS
from ui.types import ToiletDict

logger = logging.getLogger(__name__)


def _load_base_data() -> tuple[dict, list[str], dict, dict, dict, dict]:
    query_params = read_query_params()
    apply_language_query_param(query_params)
    current_lang = st.session_state.get("lang_select", DEFAULT_LANGUAGE)
    translations = get_language_strings(current_lang)
    return (
        load_metadata(),
        load_prefectures(),
        load_prefecture_stats(),
        load_data_quality_summary(),
        translations,
        query_params,
    )


def _build_filters(sidebar: SidebarResult, internal_filter: str) -> dict[str, object]:
    return {
        "prefecture": sidebar.selected_pref,
        "filter_type": internal_filter,
        "search_query": sidebar.search_query,
        "user_location": sidebar.user_location,
    }


def _filter_key(filters: dict[str, object], sort_key: str) -> str:
    location = filters.get("user_location")
    location_key = ""
    if isinstance(location, tuple) and len(location) >= 2:
        location_key = f"{float(location[0]):.5f},{float(location[1]):.5f}"
    return "|".join(
        [
            str(filters.get("prefecture") or "全て"),
            str(filters.get("filter_type") or "すべて"),
            str(filters.get("search_query") or ""),
            sort_key,
            location_key,
        ]
    )


def _prepare_page(filter_key: str, total_items: int) -> tuple[int, int]:
    init_page_state()
    reset_page(filter_key)
    requested_page = int(st.session_state.get("page", 1))
    total_pages, _, _, _ = calc_pagination(total_items, requested_page, PER_PAGE)
    page = normalize_page(requested_page, total_pages)
    if page != requested_page:
        st.session_state.page = page
    return page, total_pages


def _current_map_bounds(filter_key: str) -> dict | None:
    if st.session_state.get("map_filter_key") != filter_key:
        st.session_state["map_filter_key"] = filter_key
        st.session_state.pop("map_bounds", None)
    bounds = st.session_state.get("map_bounds")
    return bounds if isinstance(bounds, dict) else None


def _remember_map_bounds(map_state: object) -> None:
    if not isinstance(map_state, dict):
        return
    bounds = map_state.get("bounds")
    if isinstance(bounds, dict) and _extract_bounds_coordinates(bounds):
        st.session_state["map_bounds"] = bounds


def _items_to_csv(items: list[ToiletDict]) -> bytes:
    output = io.StringIO(newline="")
    fieldnames = [column for column in TOILET_COLUMNS if column not in {"sample_reviews_json"}]
    if any("distance" in item for item in items):
        fieldnames.append("distance")
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for item in items:
        row = dict(item)
        if "top_keywords" in row:
            row["top_keywords"] = json.dumps(row["top_keywords"], ensure_ascii=False)
        writer.writerow(row)
    return output.getvalue().encode("utf-8-sig")


def _render_main_content(
    total_items: int,
    total_pages: int,
    page: int,
    list_items: list[ToiletDict],
    map_items: list[ToiletDict],
    metadata: dict,
    data_quality_summary: dict,
    translations: dict,
    selected_prefecture: str,
    dark_mode: bool,
    selected_tile: str,
    query_elapsed_ms: float,
    prefecture_stats: dict,
) -> bool:
    map_lat, map_lng, map_zoom = calc_map_center(selected_prefecture, metadata, prefecture_stats)
    st.markdown(f"**{total_items}{translations['showing']}**")
    render_score_legend()

    try:
        map_started_at = perf_counter()
        map_object = build_map(map_items, map_lat, map_lng, map_zoom, tile=TILE_OPTIONS[selected_tile])
        map_elapsed_ms = (perf_counter() - map_started_at) * 1000
        st.caption(
            build_result_context_text(
                len(list_items), len(map_items), query_elapsed_ms, map_elapsed_ms, translations
            )
        )
        map_state = st_folium(
            map_object,
            height=500,
            returned_objects=["bounds"],
            use_container_width=True,
        )
        _remember_map_bounds(map_state)
    except Exception:
        logger.exception("Map rendering failed")
        st.error(translations.get("map_render_failed", "地図を表示できませんでした。条件を変更して再試行してください。"))

    render_stats(metadata, map_items, translations)
    render_data_quality(metadata, data_quality_summary, translations)
    if total_items:
        render_pagination(total_items, page, total_pages, translations)
    if not list_items:
        st.info(translations["no_results"])
    else:
        st.divider()
        st.markdown('<div role="list">', unsafe_allow_html=True)
        rank_offset = (page - 1) * PER_PAGE
        for rank, item in enumerate(list_items, rank_offset + 1):
            render_toilet_card(item, rank=rank, meta=metadata)
        st.markdown("</div>", unsafe_allow_html=True)
    return dark_mode


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
    metadata, prefectures, prefecture_stats, data_quality_summary, translations, query_params = _load_base_data()
    sidebar = render_sidebar(translations, prefectures, query_params)
    translations = sidebar.t
    internal_filter = sidebar.translated_to_internal[sidebar.filter_type]
    filters = _build_filters(sidebar, internal_filter)
    sort_key = "near" if sidebar.sort_order == translations["sort_near"] else "score"
    filter_key = _filter_key(filters, sort_key)

    query_started_at = perf_counter()
    total_items = count_items(filters)
    page, total_pages = _prepare_page(filter_key, total_items)
    map_bounds = _current_map_bounds(filter_key)
    list_items = load_list_items(filters, sort_key, page=page, per_page=PER_PAGE)
    map_items = load_map_items(map_bounds, filters, limit=MAX_MAP_MARKERS)
    query_elapsed_ms = (perf_counter() - query_started_at) * 1000

    st.title(translations["title"])
    st.caption(build_data_freshness_text(metadata, translations))
    dark_mode = _render_main_content(
        total_items,
        total_pages,
        page,
        list_items,
        map_items,
        metadata,
        data_quality_summary,
        translations,
        sidebar.selected_pref,
        sidebar.dark_mode,
        sidebar.selected_tile,
        query_elapsed_ms,
        prefecture_stats,
    )
    if dark_mode:
        st.markdown(DARK_MODE_CSS, unsafe_allow_html=True)
    if st.session_state.get("_show_shortcuts", False):
        st.info(translations["shortcut_info"])
    if list_items:
        st.download_button(
            f"{translations.get('csv_download', '📥 CSVダウンロード')}（このページ）",
            _items_to_csv(list_items),
            f"toilets_{sidebar.selected_pref}_page_{page}.csv",
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
