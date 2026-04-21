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
import app_config

from ui.styles import MOBILE_CSS
from ui.components import (
    render_score_legend,
    render_filter_buttons,
    render_detail_card,
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
)


# ============================================================
# データ読み込み
# ============================================================
def load_data():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(ttl=3600)
def _load_data_cached():
    return load_data()


# ============================================================
# フィルタリング
# ============================================================
def filter_toilets(df: pd.DataFrame, filter_type: str) -> pd.DataFrame:
    """フィルタタイプに従ってDataFrameを絞り込む"""
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
def build_map(toilets: list, center_lat: float, center_lng: float, zoom: int) -> folium.Map:
    """Folium地図を生成してマーカーを配置"""
    m = folium.Map(
        location=[center_lat, center_lng],
        zoom_start=zoom,
        tiles="OpenStreetMap",
        # モバイルでのスワイプ操作を改善
        control_scale=True,
    )

    # ポップアップが地図枠内に収まるよう Leaflet イベントで自動パン
    popup_fix_js = """
    <script>
    (function(){
      function fixPopups(){
        var mapEl = document.getElementById('map');
        if(!mapEl) { setTimeout(fixPopups, 500); return; }
        var lmap = null;
        // foliumが生成したL.Mapを探す
        for(var k in window){
          try{ if(window[k] && window[k].getContainer && window[k].getContainer()===mapEl){ lmap=window[k]; break; } }catch(e){}
        }
        if(!lmap){ setTimeout(fixPopups, 500); return; }

        lmap.on('popupopen', function(e){
          var px = lmap.latLngToContainerPoint(e.popup.getLatLng());
          // ポップアップをマーカーより上ではなく下（手前）に表示
          // 高さを取得して自動パン先を計算
          setTimeout(function(){
            var popup = e.popup._container;
            if(!popup) return;
            var mapRect = lmap.getContainer().getBoundingClientRect();
            var popRect = popup.getBoundingClientRect();
            // 左右はみ出し補正
            if(popRect.left < mapRect.left + 8){
              popup.style.left = (mapRect.left + 8 - popRect.left + parseFloat(popup.style.left||0)) + 'px';
            }
            if(popRect.right > mapRect.right - 8){
              popup.style.left = (parseFloat(popup.style.left||0) - (popRect.right - mapRect.right + 8)) + 'px';
            }
            // 上はみ出し → マップを下にパン
            if(popRect.top < mapRect.top + 8){
              var dy = mapRect.top + 8 - popRect.top;
              lmap.panBy([0, -dy], {animate: true, duration: 0.2});
            }
            // 下はみ出し → マップを上にパン
            if(popRect.bottom > mapRect.bottom - 8){
              var dy = popRect.bottom - mapRect.bottom + 8;
              lmap.panBy([0, dy], {animate: true, duration: 0.2});
            }
          }, 50);
        });
      }
      fixPopups();
    })();
    </script>
    """
    m.get_root().html.add_child(folium.Element(popup_fix_js))

    cluster = MarkerCluster(
        options={"maxClusterRadius": 50, "spiderfyOnMaxZoom": True},
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

    st.caption(
        f"{meta['area_name']} - Googleレビューからトイレのきれい度を可視化 | "
        f"トイレ口コミあり{len(df)}件"
    )

    # フィルタ＆検索（モバイルでは縦並び）
    col_filter, col_search = st.columns([1, 2])
    with col_filter:
        filter_type = st.selectbox("フィルタ", list(FILTER_CONFIG.keys()), label_visibility="collapsed")
    with col_search:
        search_query = st.text_input("検索（名前・住所）", "", placeholder="🔍 名前・住所で検索…")

    # フィルタ→検索→ソート
    filtered = filter_toilets(df, filter_type)
    filtered = search_toilets(filtered, search_query)
    filtered = filtered.sort_values("toilet_score", ascending=False)

    st.markdown(f"**{len(filtered)}件** 表示中　（きれい度順）")
    render_score_legend()

    # 地図表示（高さを画面サイズに応じて調整）
    map_height = 500  # モバイル想定
    m = build_map(
        filtered.to_dict("records"),
        meta["center_lat"],
        meta["center_lng"],
        meta["zoom"],
    )
    st_folium(m, height=map_height, returned_objects=[], use_container_width=True)

    # ランキングリスト
    st.divider()
    st.subheader("📍 トイレランキング")

    for i, (_, row) in enumerate(filtered.head(20).iterrows()):
        render_toilet_card(row.to_dict(), rank=i + 1)


if __name__ == "__main__":
    main()
