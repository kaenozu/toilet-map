"""
toilet-map/app.py
Streamlit版トイレきれい度マップ
"""

import json
import logging
import os
from time import perf_counter

import pandas as pd
import sentry_sdk
import streamlit as st
from streamlit_folium import st_folium

from app_config import TILE_OPTIONS
from batch.ai_scoring import analyze_reviews
from batch.ai_scoring import is_available as ai_available
from batch.logging_config import configure_logging
from ui.components import build_data_freshness_text, build_result_context_text, render_score_legend, render_toilet_card
from ui.data_loader import get_data_cache_token, get_prefectures, load_toilet_data, toilets_to_dataframe
from ui.exporter import render_export_ui
from ui.filters import filter_toilets, search_toilets
from ui.helpers import get_toilet_identity_key
from ui.i18n import APP_TITLE, DEFAULT_LANGUAGE, get_language_strings
from ui.map_builder import build_map, calc_map_center
from ui.metrics import get_metrics, render_metrics_dashboard
from ui.pagination import calc_pagination, init_page_state, render_pagination, reset_page
from ui.pipeline_status import render_pipeline_status
from ui.plugin_api import render_plugins
from ui.quality_dashboard import render_quality_dashboard
from ui.query_params import (
    apply_language_query_param,
    build_query_params_from_state,
    read_query_params,
    write_query_params,
)
from ui.sidebar import render_sidebar
from ui.stats import render_stats
from ui.styles import inject_pwa_assets, inject_theme_styles

sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN", ""),
    enable_tracing=True,
    traces_sample_rate=0.1,
    environment=os.environ.get("SENTRY_ENVIRONMENT", "development"),
)

logger = logging.getLogger(__name__)


def _load_and_prepare() -> tuple[dict, pd.DataFrame, list[str], dict, dict, dict, list]:
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
    return meta, df, prefectures, prefecture_stats, t, query_params, toilets


def _process_filters(df: pd.DataFrame, selected_pref: str, internal_filter: str, search_query: str, sort_order: str, user_location: tuple | None, t: dict) -> tuple[pd.DataFrame, float]:
    user_lat, user_lng = user_location if user_location else (None, None)
    filter_started_at = perf_counter()
    filtered = filter_toilets(df, internal_filter, selected_pref, user_lat, user_lng)
    filtered = search_toilets(filtered, search_query)
    if sort_order == t["sort_near"] and user_location:
        filtered = filtered.sort_values("distance", ascending=True)
    else:
        filtered = filtered.sort_values("toilet_score", ascending=False)
    filter_elapsed_ms = (perf_counter() - filter_started_at) * 1000
    get_metrics().record("filter", filter_elapsed_ms)
    return filtered, filter_elapsed_ms


def _render_main_content(filtered: pd.DataFrame, map_items: list[dict], meta: dict, t: dict, selected_pref: str, sort_order: str, dark_mode: bool, selected_tile: str, toilets: list, filter_elapsed_ms: float, prefecture_stats: dict, internal_filter: str, search_query: str, compact: bool = False, show_heatmap: bool = False) -> tuple[bool, int, pd.DataFrame]:
    map_lat, map_lng, map_zoom = calc_map_center(selected_pref, meta, prefecture_stats)
    total_items = len(filtered)
    init_page_state()
    page_filter_key = f"{selected_pref}|{internal_filter}|{search_query}"
    reset_page(page_filter_key)
    page = st.session_state.get("page", 1)
    total_pages, start_idx, end_idx, page = calc_pagination(total_items, page)
    display_items = filtered.iloc[start_idx:end_idx] if total_items > 0 else filtered

    st.markdown(f"**{total_items}{t['showing']}**")
    render_score_legend()

    map_started_at = perf_counter()
    m = build_map(map_items, map_lat, map_lng, map_zoom, tile=TILE_OPTIONS[selected_tile], show_heatmap=show_heatmap)
    map_elapsed_ms = (perf_counter() - map_started_at) * 1000
    get_metrics().record("map", map_elapsed_ms)

    st.caption(
        build_result_context_text(
            len(display_items),
            len(map_items),
            filter_elapsed_ms,
            map_elapsed_ms,
            t,
        )
    )
    try:
        st_folium(m, height=500, returned_objects=[], use_container_width=True)
    except Exception as e:
        st.error(f"Map rendering failed: {e}")

    render_metrics_dashboard()
    render_stats(meta, map_items, t)
    render_quality_dashboard(meta, toilets, t)
    render_pipeline_status()
    render_plugins(toilets, t)

    if total_items > 0:
        render_pagination(total_items, page, total_pages, t)

    if len(display_items) == 0:
        st.info(t["no_results"])
    else:
        st.divider()
        st.markdown('<div role="list">', unsafe_allow_html=True)
        for i, (_, row) in enumerate(display_items.iterrows()):
            render_toilet_card(row.to_dict(), rank=i + 1, meta=meta, compact=compact)
        st.markdown('</div>', unsafe_allow_html=True)

    return dark_mode, page, display_items


def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="🚽",
        layout="wide",
    )
    inject_pwa_assets()
    inject_theme_styles()
    configure_logging()

    try:
        with st.spinner("データを読み込み中..."):
            meta, df, prefectures, prefecture_stats, t, query_params, toilets = _load_and_prepare()
        st.session_state["data_loaded"] = True

        sidebar_result = render_sidebar(t, prefectures, query_params)
        t = sidebar_result.t
        lang = sidebar_result.lang
        selected_pref = sidebar_result.selected_pref
        filter_type = sidebar_result.filter_type
        search_query = sidebar_result.search_query
        sort_order = sidebar_result.sort_order
        user_location = sidebar_result.user_location
        gps_enabled = sidebar_result.gps_enabled
        dark_mode = sidebar_result.dark_mode
        selected_tile = sidebar_result.selected_tile
        translated_to_internal = sidebar_result.translated_to_internal

        internal_filter = translated_to_internal[filter_type]

        # AI enhancement: analyze reviews with Gemini
        if st.session_state.get("ai_enhance", False) and "ai_scores" not in st.session_state:
            ai_scores = {}
            if ai_available():
                candidates = [
                    t for t in toilets
                    if t.get("toilet_review_count", 0) >= 3
                    and (t.get("confidence", 0) or 0) < 0.5
                ]
                with st.spinner(t.get("ai_analyzing", "🤖 AI分析中...")):
                    for toilet in candidates:
                        reviews = toilet.get("sample_reviews", [])
                        result = analyze_reviews(reviews, toilet.get("title", ""))
                        if result.get("sentiment_score") is not None:
                            ai_scores[get_toilet_identity_key(toilet)] = result
            st.session_state["ai_scores"] = ai_scores

        filtered, filter_elapsed_ms = _process_filters(
            df, selected_pref, internal_filter, search_query, sort_order, user_location, t
        )

        st.title(t["title"])
        st.caption(build_data_freshness_text(meta, t))

        map_items = filtered.to_dict("records")

        # Merge AI scores into map_items for popup display
        if "ai_scores" in st.session_state:
            ai_scores = st.session_state["ai_scores"]
            for item in map_items:
                identity_key = get_toilet_identity_key(item)
                if identity_key in ai_scores:
                    item.update({f"ai_{k}": v for k, v in ai_scores[identity_key].items()})

        compact = st.session_state.get("compact_mode", False)
        show_heatmap = st.session_state.get("show_heatmap", False)
        dark_mode, page, display_items = _render_main_content(
            filtered, map_items, meta, t, selected_pref,
            sort_order, dark_mode, selected_tile, toilets, filter_elapsed_ms,
            prefecture_stats, internal_filter, search_query,
            compact=compact,
            show_heatmap=show_heatmap,
        )

        if dark_mode:
            st.markdown(
                '<link rel="stylesheet" href="/static/dark_mode.css">',
                unsafe_allow_html=True,
            )

        if st.session_state.get("_show_shortcuts", False):
            st.info(t["shortcut_info"])

        render_export_ui(filtered, map_items, selected_pref, t)

        if toilets:
            cache_data = json.dumps([
                {"place_id": t.get("place_id"), "name": t.get("name"),
                 "toilet_score": t.get("toilet_score"),
                 "lat": t.get("lat"), "lng": t.get("lng")}
                for t in toilets[:200]
            ], ensure_ascii=False)
            st.markdown(
                f"<script>window.cacheToiletData({cache_data});</script>",
                unsafe_allow_html=True,
            )

        write_query_params(
            build_query_params_from_state(
                lang, selected_pref, internal_filter, search_query,
                sort_order, gps_enabled, page, t, dark_mode=dark_mode,
            )
        )
    except Exception as e:
        sentry_sdk.capture_exception(e)
        raise


if __name__ == "__main__":
    main()
