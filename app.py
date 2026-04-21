"""
toilet-map/app.py
Streamlit版トイレきれい度マップ
toilets.jsonを読み込んでインタラクティブに表示する
"""
import html
import json
import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

# ============================================================
# 定数
# ============================================================
DATA_PATH = "data/toilets.json"

# スコア表示設定（閾値, 色, 絵文字, ラベル）
SCORE_RANGES = [
    (80, "#27ae60", "✨", "とてもきれい"),
    (65, "#2ecc71", "😊", "きれい"),
    (50, "#f1c40f", "😐", "普通"),
    (35, "#f39c12", "😨", "少し気になる"),
    (0, "#e74c3c", "💩", "要注意"),
]

# フィルタ定義
FILTER_CONFIG = {
    "すべて": None,
    "公共トイレ": "__public__",
    "カフェ・飲食": "カフェ|喫茶|レストラン|食堂|ダイニング|コーヒー|パン|ケーキ",
    "コンビニ・店舗": "コンビニ|スーパー|ドラッグ|ストア|マート|商店",
}

# マーカー設定
PUBLIC_MARKER_RADIUS = 14
NORMAL_MARKER_RADIUS = 10

# レビュー保存上限
MAX_SAMPLE_REVIEWS = 5

# モバイル判定閾値
MOBILE_BREAKPOINT = 768

# モバイル用CSS
MOBILE_CSS = """
<style>
/* ===== モバイル最適化 ===== */

/* Streamlitの余分な余白を削減 */
@media (max-width: 768px) {
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 0 !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        max-width: 100% !important;
    }

    /* タイトル縮小 */
    h1 { font-size: 1.3rem !important; margin-bottom: 0.3rem !important; }

    /* キャプション縮小 */
    .stCaption { font-size: 0.75rem !important; }

    /* 地図コンテナの上下マージン削減 */
    .st Folium_folium { margin-top: 0 !important; }

    /* selectboxとtext_inputのフォントサイズ調整（iOSズーム防止） */
    .stSelectbox label, .stTextInput label {
        font-size: 16px !important;  /* 16px以上でiOSはズームしない */
    }

    /* 凡例を小さく */
    .score-legend-mobile { font-size: 0.7rem !important; }
    .score-legend-mobile .bar { width: 120px !important; height: 10px !important; }
}

/* タップしやすいフィルタボタン */
.filter-btn {
    display: inline-block;
    padding: 6px 14px;
    border-radius: 20px;
    border: 1px solid #ddd;
    font-size: 13px;
    cursor: pointer;
    margin: 2px;
    user-select: none;
    -webkit-tap-highlight-color: transparent;
    transition: all 0.15s;
}
.filter-btn:hover { background: #f0f0f0; }
.filter-btn.active {
    background: #1a73e8;
    color: white;
    border-color: #1a73e8;
}

/* 現在地ボタン */
.locate-btn {
    position: fixed;
    bottom: 20px;
    right: 20px;
    z-index: 10000;
    width: 48px;
    height: 48px;
    border-radius: 50%;
    background: white;
    border: 2px solid #1a73e8;
    font-size: 22px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(0,0,0,0.25);
    -webkit-tap-highlight-color: transparent;
}
.locate-btn:active { transform: scale(0.9); }

/* トイレ詳細カード（モバイル用オーバーレイ） */
.detail-overlay {
    display: none;
    position: fixed;
    bottom: 0; left: 0; right: 0;
    z-index: 10001;
    background: white;
    border-top-left-radius: 16px;
    border-top-right-radius: 16px;
    box-shadow: 0 -4px 20px rgba(0,0,0,0.15);
    max-height: 60vh;
    overflow-y: auto;
    padding: 16px;
    animation: slideUp 0.25s ease-out;
}
.detail-overlay.show { display: block; }
@keyframes slideUp {
    from { transform: translateY(100%); }
    to { transform: translateY(0); }
}
.detail-overlay .close-btn {
    position: absolute;
    top: 8px; right: 12px;
    font-size: 24px;
    cursor: pointer;
    color: #999;
    border: none;
    background: none;
}

/* スマホではポップアップ幅を画面幅に合わせる */
@media (max-width: 768px) {
    .leaflet-popup-content-wrapper {
        max-width: calc(100vw - 40px) !important;
        min-width: 0 !important;
    }
    .leaflet-popup-content {
        min-width: 0 !important;
        max-width: calc(100vw - 60px) !important;
        font-size: 13px !important;
    }
}
</style>
"""


# ============================================================
# ユーティリティ
# ============================================================
def esc(text):
    """HTMLエスケープ"""
    return html.escape(str(text or ""), quote=True) if text else ""


def get_score_style(score: float) -> tuple[str, str, str]:
    """スコアに基づいて (色, 絵文字, ラベル) を返す"""
    for threshold, color, emoji, label in SCORE_RANGES:
        if score >= threshold:
            return color, emoji, label
    return SCORE_RANGES[-1][1:]


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
# ポップアップHTML生成（レスポンシブ対応）
# ============================================================
def _build_public_badge(is_public: bool) -> str:
    if not is_public:
        return ""
    return (
        '<span style="font-size:10px;padding:2px 6px;border-radius:3px;'
        'background:#e3f2fd;color:#1565c0;font-weight:600;">公共トイレ</span> '
    )


def _build_keyword_tags(keywords: list) -> str:
    if not keywords:
        return ""
    tags = []
    for kw, cnt in keywords[:5]:
        safe_kw = esc(kw[1:]) if kw.startswith(("+", "-")) else esc(kw)
        prefix = "👍" if kw.startswith("+") else "👎" if kw.startswith("-") else ""
        bg = "#e8f5e9" if kw.startswith("+") else "#ffebee" if kw.startswith("-") else "#f5f5f5"
        color = "#2e7d32" if kw.startswith("+") else "#c62828" if kw.startswith("-") else "#555"
        border = "#a5d6a7" if kw.startswith("+") else "#ef9a9a" if kw.startswith("-") else "#e0e0e0"
        tags.append(
            f'<span style="display:inline-block;font-size:11px;padding:2px 6px;'
            f'border-radius:4px;background:{bg};color:{color};'
            f'border:1px solid {border};margin:1px;word-break:break-all;">'
            f'{prefix}{safe_kw} ×{cnt}</span>'
        )
    return '<div style="margin-top:4px;line-height:2;">' + " ".join(tags) + "</div>"


def _build_review_html(reviews: list) -> str:
    if not reviews:
        return ""
    seen = set()
    parts = []
    for r in reviews[:2]:
        txt = r.get("text", "")
        key = txt[:80]
        if key in seen:
            continue
        seen.add(key)
        score_val = r.get("score", 0)
        icon = "👍" if score_val > 0 else "👎" if score_val < 0 else "📝"
        border_color = "#2e7d32" if score_val > 0 else "#c62828" if score_val < 0 else "#bbb"
        name = esc(r.get("name", ""))
        rating = r.get("rating", "")
        meta = f'<span style="color:#999;">{name}</span>'
        if rating:
            meta += f' <span style="color:#f9a825;">★{rating}</span>'
        txt_safe = esc(txt).replace("\n", "<br>")
        # モバイルではテキストを短縮
        parts.append(
            f'<div style="font-size:11px;color:#444;padding:4px 6px;background:#fafafa;'
            f'border-radius:4px;margin-top:3px;border-left:3px solid {border_color};">'
            f"{icon} {meta}<br>"
            f'<span style="line-height:1.5;">{txt_safe[:120]}{"..." if len(txt_safe) > 120 else ""}</span></div>'
        )
    return "".join(parts)


def _build_link_html(link: str) -> str:
    if not link:
        return ""
    return (
        '<div style="margin-top:6px;">'
        f'<a href="{link}" target="_blank" rel="noopener noreferrer" '
        'style="font-size:13px;color:#1a73e8;text-decoration:none;font-weight:600;'
        'display:inline-block;padding:4px 0;">'
        "🗺️ Google Mapsで開く →</a></div>"
    )


def build_popup_html(t: dict) -> str:
    """1トイレ地点のポップアップHTMLを構築（コンパクト・スクロール対応）"""
    color, emoji, label = get_score_style(t["toilet_score"])
    badge = _build_public_badge(t["is_public_toilet"])
    confidence_pct = int(t["confidence"] * 100)
    phone_html = f'<span style="margin-right:6px;">📞{esc(t["phone"])}</span>' if t.get("phone") else ""
    kw_html = _build_keyword_tags(t.get("top_keywords"))
    rev_html = _build_review_html(t.get("sample_reviews", []))
    link_html = _build_link_html(t.get("link", ""))

    review_section = ""
    if rev_html:
        review_section = (
            '<hr style="margin:4px 0;border:none;border-top:1px dashed #ccc;">'
            '<div style="font-size:10px;font-weight:600;margin-bottom:2px;">🚽 口コミ:</div>'
            + rev_html
        )

    # 住所を短縮（郵便番号削除）
    addr = t.get("address", "")
    addr = esc(addr)

    return f"""
    <div style="font-family:'Segoe UI','Hiragino Sans','Noto Sans JP',sans-serif;padding:4px;
        max-width:100%;overflow-wrap:break-word;word-break:break-word;
        max-height:45vh;overflow-y:auto;-webkit-overflow-scrolling:touch;">
      <div style="font-size:14px;font-weight:700;margin-bottom:2px;line-height:1.3;">
        {badge}{esc(t['title'])}
      </div>
      <div style="font-size:10px;color:#888;margin-bottom:4px;">{esc(t['category'])}</div>

      <div style="text-align:center;margin:4px 0;">
        <span style="font-size:24px;font-weight:800;color:{color};">{emoji} {t['toilet_score']:.0f}点</span>
        <span style="font-size:11px;color:#888;">（{label}）</span>
      </div>

      <div style="text-align:center;font-size:10px;color:#888;margin-bottom:2px;">
        信頼度 {confidence_pct}% | {t['toilet_review_count']}件
      </div>
      <div style="height:3px;border-radius:2px;background:#e0e0e0;margin-bottom:4px;overflow:hidden;">
        <div style="height:100%;width:{confidence_pct}%;background:{color};border-radius:2px;"></div>
      </div>

      <div style="font-size:10px;color:#555;margin-bottom:1px;">📍 {addr}</div>
      <div style="font-size:10px;color:#555;">⭐{t.get('rating', '-')} ({t.get('review_count', 0)}件) {phone_html}</div>
      {kw_html}
      {review_section}
      {link_html}
    </div>
    """


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
# UI描画
# ============================================================
def render_score_legend():
    """スコア凡例を表示（レスポンシブ）"""
    st.markdown(
        """
    <div class="score-legend-mobile" style="display:flex;align-items:center;gap:4px;font-size:12px;margin-bottom:4px;">
        <span>💩</span>
        <div class="bar" style="width:200px;height:14px;border-radius:7px;
            background:linear-gradient(to right,#e74c3c,#f39c12,#f1c40f,#2ecc71,#27ae60);"></div>
        <span>✨</span>
    </div>
    """,
        unsafe_allow_html=True,
    )


def render_filter_buttons(selected: str) -> str:
    """フィルタボタンをHTMLで描画（タップしやすい）し、選択中のキーを返す"""
    buttons = []
    for key in FILTER_CONFIG:
        active = ' active' if key == selected else ''
        buttons.append(
            f'<span class="filter-btn{active}" '
            f'data-key="{key}" '
            f'onclick="document.querySelectorAll(\'.filter-btn\').forEach(b=>b.classList.remove(\'active\'));'
            f'this.classList.add(\'active\');'
            f'window.parent.postMessage({{type:\'streamlit:setComponentValue\',value:\'{key}\'}},\'*\')">'
            f'{key}</span>'
        )
    st.markdown(
        '<div style="display:flex;flex-wrap:wrap;gap:4px;margin:4px 0;">'
        + "".join(buttons) + "</div>",
        unsafe_allow_html=True,
    )
    return selected


def render_detail_card(toilet: dict):
    """モバイル用 詳細カード（expander）"""
    color, emoji, label = get_score_style(toilet["toilet_score"])
    confidence_pct = int(toilet["confidence"] * 100)

    with st.expander(
        f"{emoji} {toilet['title']} — {toilet['toilet_score']:.0f}点（{label}）"
    ):
        c1, c2 = st.columns([1, 1])
        with c1:
            st.write(f"📍 {toilet.get('address', '')}")
            st.write(f"⭐ {toilet.get('rating', '-')} (口コミ {toilet.get('review_count', 0)}件)")
        with c2:
            st.write(f"🏷️ {toilet.get('category', '')}")
            if toilet.get("phone"):
                st.write(f"📞 {toilet['phone']}")
            st.write(f"信頼度 {confidence_pct}% | トイレ言及 {toilet['toilet_review_count']}件")

        # キーワード
        if toilet.get("top_keywords"):
            tags = []
            for kw, cnt in toilet["top_keywords"][:5]:
                prefix = "👍" if kw.startswith("+") else "👎" if kw.startswith("-") else ""
                tags.append(f"`{prefix}{kw[1:] if kw.startswith(('+','-')) else kw} ×{cnt}`")
            st.markdown(" ".join(tags))

        # レビュー
        if toilet.get("sample_reviews"):
            for r in toilet["sample_reviews"][:3]:
                score_val = r.get("score", 0)
                icon = "👍" if score_val > 0 else "👎" if score_val < 0 else "📝"
                st.markdown(
                    f"**{icon}** {esc(r.get('text', ''))[:200]}"
                )

        # リンク
        if toilet.get("link"):
            st.markdown(f"[🗺️ Google Mapsで開く]({toilet['link']})")


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

    # モバイル用：ランキングリスト
    st.divider()
    st.subheader("📍 トイレランキング")

    # 上位10件をカード表示
    for i, (_, row) in enumerate(filtered.head(20).iterrows()):
        t = row.to_dict()
        color, emoji, label = get_score_style(t["toilet_score"])
        confidence_pct = int(t["confidence"] * 100)

        # タップしやすい大きなカード
        score_bg = color
        public_tag = ' <span style="background:#e3f2fd;color:#1565c0;padding:1px 6px;border-radius:3px;font-size:10px;">公共</span>' if t.get("is_public_toilet") else ""

        link_start = f'<a href="{t["link"]}" target="_blank" rel="noopener noreferrer" style="text-decoration:none;color:inherit;">' if t.get("link") else ""
        link_end = "</a>" if t.get("link") else ""

        st.markdown(
            f"""
            {link_start}
            <div style="display:flex;align-items:center;gap:10px;padding:8px 12px;
                background:#ffffff;color:#222222;border-radius:8px;margin-bottom:4px;
                border:1px solid #e0e0e0;min-height:60px;
                -webkit-tap-highlight-color:transparent;">
                <div style="min-width:50px;text-align:center;">
                    <div style="font-size:24px;font-weight:800;color:{color};line-height:1;">{emoji}</div>
                    <div style="font-size:14px;font-weight:700;color:{color};">{t['toilet_score']:.0f}</div>
                </div>
                <div style="flex:1;min-width:0;color:#222222;">
                    <div style="font-size:14px;font-weight:600;color:#222222;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                        {public_tag} {esc(t['title'])}
                    </div>
                    <div style="font-size:11px;color:#666666;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                        📍 {esc(t.get('address', ''))}
                    </div>
                    <div style="font-size:11px;color:#666666;">
                        ⭐ {t.get('rating', '-')} · 口コミ {t.get('review_count', 0)}件 · 信頼度 {confidence_pct}%
                    </div>
                </div>
                <div style="font-size:18px;color:#aaaaaa;">›</div>
            </div>
            {link_end}
            """,
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
