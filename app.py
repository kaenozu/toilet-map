"""
toilet-map/app.py
Streamlit版トイレきれい度マップ
toilets.jsonを読み込んでインタラクティブに表示する
"""
import json
import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from ui.styles import MOBILE_CSS
from ui.components import (
    render_score_legend,
    render_toilet_card,
)
from ui.popups import build_popup_html
from app_config import (
    DATA_PATH,
    FILTER_CONFIG,
    PUBLIC_MARKER_RADIUS,
    NORMAL_MARKER_RADIUS,
    get_score_style,
    esc,
    PREFECTURE_CENTERS,
    TILE_OPTIONS,
    POPUP_FIX_JS,
)

PER_PAGE = 20


# ============================================================
# データ読み込み
# ============================================================
def load_data():
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "toilets" not in data or "metadata" not in data:
            raise ValueError("Invalid data structure")
        return data
    except FileNotFoundError:
        st.error(f"データファイルが見つかりません: {DATA_PATH}")
        return {"metadata": {"total": 0, "scored": 0, "public_toilets": 0, "center_lat": 36.2231, "center_lng": 139.3772, "zoom": 13, "area_name": "エラー"}, "toilets": []}
    except json.JSONDecodeError:
        st.error(f"データファイルの形式が不正です: {DATA_PATH}")
        return {"metadata": {"total": 0, "scored": 0, "public_toilets": 0, "center_lat": 36.2231, "center_lng": 139.3772, "zoom": 13, "area_name": "エラー"}, "toilets": []}
    except Exception as e:
        st.error(f"データ読み込みエラー: {e}")
        return {"metadata": {"total": 0, "scored": 0, "public_toilets": 0, "center_lat": 36.2231, "center_lng": 139.3772, "zoom": 13, "area_name": "エラー"}, "toilets": []}


@st.cache_data(ttl=3600)
def _load_data_cached():
    data = load_data()
    toilets = data["toilets"]
    stats = {}
    for t in toilets:
        pref = t.get("prefecture", "")
        if pref:
            if pref not in stats:
                stats[pref] = {"count": 0, "lats": [], "lngs": []}
            stats[pref]["count"] += 1
            stats[pref]["lats"].append(t["lat"])
            stats[pref]["lngs"].append(t["lng"])
    for pref, s in stats.items():
        s["center_lat"] = sum(s["lats"]) / len(s["lats"])
        s["center_lng"] = sum(s["lngs"]) / len(s["lngs"])
        del s["lats"]
        del s["lngs"]
    data["pref_stats"] = stats
    return data


# ============================================================
# フィルタリング
# ============================================================
def filter_toilets(df: pd.DataFrame, filter_type: str, prefecture: str = None) -> pd.DataFrame:
    """フィルタタイプに従ってDataFrameを絞り込む"""
    if prefecture and prefecture != "全て":
        df = df[df["prefecture"] == prefecture]

    pattern = FILTER_CONFIG.get(filter_type)
    if pattern is None:
        return df
    if pattern == "__public__":
        return df[df["is_public_toilet"] == True]
    return df[df["category"].str.contains(pattern, na=False)]


def search_toilets(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """名前・住所で部分一致検索"""
    if not query:
        return df
    mask = (
        df["title"].str.contains(query, case=False, na=False)
        | df["address"].str.contains(query, case=False, na=False)
    )
    return df[mask]


# ============================================================
# マップ構築
# ============================================================
def build_map(toilets: list, center_lat: float, center_lng: float, zoom: int, tile: str = "OpenStreetMap") -> folium.Map:
    """Folium地図を生成してマーカーを配置"""
    m = folium.Map(
        location=[center_lat, center_lng],
        zoom_start=zoom,
        tiles=tile,
        control_scale=True,
    )

    m.get_root().html.add_child(folium.Element(POPUP_FIX_JS))

    # クラスター閾値をデータ件数に応じて動的調整
    cluster_radius = 50 if len(toilets) < 500 else 80 if len(toilets) < 1000 else 100

    cluster = MarkerCluster(
        options={"maxClusterRadius": cluster_radius, "spiderfyOnMaxZoom": True},
        name="トイレ",
    ).add_to(m)

    for t in toilets:
        color, emoji, label = get_score_style(t["toilet_score"])
        radius = PUBLIC_MARKER_RADIUS if t["is_public_toilet"] else NORMAL_MARKER_RADIUS

        popup_html = build_popup_html(t)

        folium.CircleMarker(
            location=[t["lat"], t["lng"]],
            radius=radius,
            color="white",
            weight=2,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            popup=folium.Popup(popup_html, max_width=320, auto_pan=True),
            tooltip=f"{emoji} {t['title']}",
        ).add_to(cluster)

    return m


# ============================================================
# メイン
# ============================================================
def main():
    # set_page_configは他のStreamlitコマンドより先に呼ぶ必要がある
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

    data = _load_data_cached()
    meta = data["metadata"]
    toilets = data["toilets"]

    st.title("🚽 トイレきれい度マップ")

    # データフレーム化＆トイレ口コミありのみ
    df = pd.DataFrame(toilets)
    df = df[df["toilet_review_count"] > 0].reset_index(drop=True)

    # 都道府県フィルター（prefecture 列が存在しない場合は「全て」のみ）
    if "prefecture" in df.columns:
        prefectures = ["全て"] + sorted(df["prefecture"].dropna().unique().tolist())
    else:
        prefectures = ["全て"]

    st.caption(
        f"{meta['area_name']} - Googleレビューからトイレのきれい度を可視化 | "
        f"トイレ口コミあり{len(df)}件 | データ更新日: {meta.get('last_updated', '-')}"
    )

    # 統計ダッシュボード
    with st.expander("📊 統計"):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("総数", meta.get("total", 0))
        with col2:
            st.metric("スコア算出", meta.get("scored", 0))
        with col3:
            st.metric("公共トイレ", meta.get("public_toilets", 0))
        with col4:
            avg_score = sum(t["toilet_score"] for t in toilets if t.get("toilet_score", 0) > 0) / max(1, sum(1 for t in toilets if t.get("toilet_score", 0) > 0))
            st.metric("平均スコア", f"{avg_score:.0f}")

    # CSVエクスポート
    if total_items > 0:
        csv = filtered.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 CSVダウンロード",
            data=csv,
            file_name=f"toilet_map_{selected_pref}_{filter_type}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # フィルタ＆検索（モバイルでは縦並び）
    col_pref, col_filter, col_search = st.columns([1, 1, 2])
    with col_pref:
        selected_pref = st.selectbox("都道府県", prefectures, label_visibility="collapsed", key="pref_select")
    with col_filter:
        filter_type = st.selectbox("フィルタ", list(FILTER_CONFIG.keys()), label_visibility="collapsed", key="filter_select")
    with col_search:
        search_query = st.text_input("検索（名前・住所）", "", placeholder="🔍 名前・住所で検索…", label_visibility="collapsed", key="search_input")

    # タイルレイヤー選択
    tile_name = st.selectbox("地図スタイル", list(TILE_OPTIONS.keys()), label_visibility="collapsed", key="tile_select")
    tile = TILE_OPTIONS[tile_name]

    # フィルタ→検索→ソート
    filtered = filter_toilets(df, filter_type, selected_pref)
    filtered = search_toilets(filtered, search_query)
    filtered = filtered.sort_values("toilet_score", ascending=False)

    # マップ中心座標：都道府県選択時はその県の中間点へ、それ以外はデータ全体の中間点へ
    stats = data.get("pref_stats", {})
    if selected_pref != "全て" and selected_pref in PREFECTURE_CENTERS:
        if selected_pref in stats and stats[selected_pref]["count"] >= 5:
            map_lat = stats[selected_pref]["center_lat"]
            map_lng = stats[selected_pref]["center_lng"]
            map_zoom = 11
        else:
            map_lat, map_lng = PREFECTURE_CENTERS[selected_pref]
            map_zoom = 11
    else:
        map_lat = meta["center_lat"]
        map_lng = meta["center_lng"]
        map_zoom = meta["zoom"]

    # フィルタ変更時はページをリセット
    filter_key = f"{selected_pref}|{filter_type}|{search_query}"
    if st.session_state.get("last_filter_key", "") != filter_key:
        st.session_state.page = 1
        st.session_state.last_filter_key = filter_key

    total_items = len(filtered)
    total_pages = max(1, (total_items + PER_PAGE - 1) // PER_PAGE)

    if "page" not in st.session_state:
        st.session_state.page = 1
    page = st.session_state.page

    col_prev, col_page, col_next = st.columns([1, 2, 1])
    with col_prev:
        prev_disabled = page <= 1
        if st.button("◀ 前へ", disabled=prev_disabled, use_container_width=True):
            st.session_state.page = max(1, page - 1)
            st.rerun()
    with col_page:
        st.markdown(
            f"<div style='text-align:center;padding:4px;font-size:14px;font-weight:600;'>"
            f"ページ {page}/{total_pages}</div>",
            unsafe_allow_html=True,
        )
    with col_next:
        next_disabled = page >= total_pages
        if st.button("次へ ▶", disabled=next_disabled, use_container_width=True):
            st.session_state.page = min(total_pages, page + 1)
            st.rerun()

    start_idx = (page - 1) * PER_PAGE
    end_idx = start_idx + PER_PAGE
    page_items = filtered.iloc[start_idx:end_idx]

    st.markdown(f"**{total_items}件** 表示中　（きれい度順）")
    render_score_legend()

    # 戻るボタン（モバイル用）
    st.markdown(
        '<div class="back-to-top"><button class="back-btn" onclick="window.scrollTo({top:0,behavior:\'smooth\'})">⬆️</button></div>',
        unsafe_allow_html=True
    )

    # 地図表示（マップは常に全フィルタ結果を表示、ランキングのみページネーション）
    map_height = 500
    m = build_map(
        filtered.to_dict("records"),
        map_lat,
        map_lng,
        map_zoom,
        tile=tile,
    )
    st_folium(m, height=map_height, returned_objects=[], use_container_width=True)

    # ランキングリスト（ページネーション対応）
    st.divider()
    st.subheader(f"📍 トイレランキング ({total_items}件中 {(page-1)*PER_PAGE+1}-{(min(page*PER_PAGE,total_items))}件)")

    for i, (_, row) in enumerate(page_items.iterrows()):
        render_toilet_card(row.to_dict(), rank=start_idx + i + 1)


if __name__ == "__main__":
    main()
