"""
toilet-map/app.py
Streamlit版トイレきれい度マップ
"""
import streamlit as st
from streamlit_folium import st_folium
from streamlit_js_eval import streamlit_js_eval
from app_config import FILTER_CONFIG
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
    )
    st.markdown(MOBILE_CSS, unsafe_allow_html=True)

    # 現在地取得 (GPS)
    user_location = None
    if st.checkbox("📍 現在地を使用する (GPS)"):
        # js_expressions の結果が直接 coords オブジェクトになるよう調整
        loc = streamlit_js_eval(js_expressions="new Promise(resolve => navigator.geolocation.getCurrentPosition(pos => resolve(pos.coords)))", key="location")
        if loc:
            user_location = (loc["latitude"], loc["longitude"])
            st.info(f"現在地を取得しました: {user_location[0]:.4f}, {user_location[1]:.4f}")

    data = load_toilet_data()
    meta = data["metadata"]
    toilets = data["toilets"]
    pref_stats = data.get("pref_stats", {})

    st.title("🚽 トイレきれい度マップ")

    df = toilets_to_dataframe(toilets)
    prefectures = get_prefectures(df)

    render_stats(meta, toilets)

    col_pref, col_filter, col_search = st.columns([1, 1, 2])
    with col_pref:
        selected_pref = st.selectbox("都道府県", prefectures, key="pref_select")
    with col_filter:
        filter_type = st.selectbox("フィルタ", list(FILTER_CONFIG.keys()), key="filter_select")
    with col_search:
        search_query = st.text_input("検索", "", placeholder="🔍 名前・住所で検索…", key="search_input")

    sort_order = st.radio("並び替え", ["きれい度順", "現在地から近い順"], horizontal=True)

    user_lat, user_lng = user_location if user_location else (None, None)
    filtered = filter_toilets(df, filter_type, selected_pref, user_lat, user_lng)
    filtered = search_toilets(filtered, search_query)

    if sort_order == "現在地から近い順" and user_location:
        filtered = filtered.sort_values("distance", ascending=True)
    else:
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
    page_items = filtered.iloc[start_idx : start_idx + PER_PAGE]

    st.markdown(f"**{total_items}件** 表示中")
    render_score_legend()

    m = build_map(page_items.to_dict("records"), map_lat, map_lng, map_zoom)
    st_folium(m, height=500, returned_objects=[], use_container_width=True)

    st.divider()
    for i, (_, row) in enumerate(page_items.iterrows()):
        render_toilet_card(row.to_dict(), rank=start_idx + i + 1)


if __name__ == "__main__":
    main()
