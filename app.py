"""
toilet-map/app.py
Streamlit版トイレきれい度マップ
ui/ モジュールのオーケストレーションのみ担当
"""
import streamlit as st
import pandas as pd
from streamlit_folium import st_folium
from app_config import FILTER_CONFIG, TILE_OPTIONS
from ui.styles import MOBILE_CSS
from ui.components import render_score_legend, render_toilet_card
from ui.data_loader import load_toilet_data, toilets_to_dataframe, get_prefectures
from ui.filters import filter_toilets, search_toilets
from ui.stats import render_stats
from ui.map_builder import build_map, calc_map_center
from ui.pagination import (
    PER_PAGE,
    init_page_state,
    reset_page,
    render_pagination,
    render_csv_export,
)


def main():
    st.set_page_config(
        page_title="🚽 トイレきれい度マップ",
        page_icon="🚽",
        layout="wide",
        initial_sidebar_state="collapsed",
        menu_items={
            "About": "トイレきれい度マップ - Googleレビューからトイレのきれい度を可視化",
        },
    )
    st.markdown(MOBILE_CSS, unsafe_allow_html=True)

    data = load_toilet_data()
    meta = data["metadata"]
    toilets = data["toilets"]
    pref_stats = data.get("pref_stats", {})

    st.title("🚽 トイレきれい度マップ")

    df = toilets_to_dataframe(toilets)
    prefectures = get_prefectures(df)

    st.caption(
        f"{meta['area_name']} - Googleレビューからトイレのきれい度を可視化 | "
        f"トイレ口コミあり{len(df)}件 | データ更新日: {meta.get('last_updated', '-')}"
    )

    render_stats(meta, toilets)

    col_pref, col_filter, col_search = st.columns([1, 1, 2])
    with col_pref:
        selected_pref = st.selectbox("都道府県", prefectures, label_visibility="collapsed", key="pref_select")
    with col_filter:
        filter_type = st.selectbox("フィルタ", list(FILTER_CONFIG.keys()), label_visibility="collapsed", key="filter_select")
    with col_search:
        search_query = st.text_input("検索（名前・住所）", "", placeholder="🔍 名前・住所で検索…", label_visibility="collapsed", key="search_input")

    tile_name = st.selectbox("地図スタイル", list(TILE_OPTIONS.keys()), label_visibility="collapsed", key="tile_select")
    tile = TILE_OPTIONS[tile_name]

    filtered = filter_toilets(df, filter_type, selected_pref)
    filtered = search_toilets(filtered, search_query)
    filtered = filtered.sort_values("toilet_score", ascending=False)

    map_lat, map_lng, map_zoom = calc_map_center(selected_pref, meta, pref_stats)

    init_page_state()
    reset_page(f"{selected_pref}|{filter_type}|{search_query}")

    total_items = len(filtered)
    total_pages = max(1, (total_items + PER_PAGE - 1) // PER_PAGE)
    page = st.session_state.page

    render_csv_export(filtered, selected_pref, filter_type)

    render_pagination(total_items, page, total_pages)

    start_idx = (page - 1) * PER_PAGE
    end_idx = min(start_idx + PER_PAGE, total_items)
    page_items = filtered.iloc[start_idx:end_idx]

    st.markdown(f"**{total_items}件** 表示中　（きれい度順）")
    render_score_legend()

    st.markdown(
        '<div class="back-to-top"><button class="back-btn" onclick="window.scrollTo({top:0,behavior:\'smooth\'})">⬆️</button></div>',
        unsafe_allow_html=True
    )

    m = build_map(filtered.to_dict("records"), map_lat, map_lng, map_zoom, tile=tile)
    st_folium(m, height=500, returned_objects=[], use_container_width=True)

    st.divider()
    st.subheader(f"📍 トイレランキング ({total_items}件中 {start_idx+1}-{end_idx}件)")

    for i, (_, row) in enumerate(page_items.iterrows()):
        render_toilet_card(row.to_dict(), rank=start_idx + i + 1)


if __name__ == "__main__":
    main()