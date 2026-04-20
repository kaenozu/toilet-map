"""
toilet-map/app.py
Streamlit版トイレきれい度マップ
toilets.jsonを読み込んでインタラクティブに表示する
"""
import json
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

DATA_PATH = "data/toilets.json"


def load_data():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


# キャッシュ対応ラッパー
@st.cache_data(ttl=3600)
def _load_data_cached():
    return load_data()


def score_to_color(score):
    if score >= 80:
        return "#27ae60"
    if score >= 65:
        return "#2ecc71"
    if score >= 50:
        return "#f1c40f"
    if score >= 35:
        return "#f39c12"
    return "#e74c3c"


def score_to_emoji(score):
    if score >= 80:
        return "✨"
    if score >= 65:
        return "😊"
    if score >= 50:
        return "😐"
    if score >= 35:
        return "😨"
    return "💩"


def score_label(score):
    if score >= 80:
        return "とてもきれい"
    if score >= 65:
        return "きれい"
    if score >= 50:
        return "普通"
    if score >= 35:
        return "少し気になる"
    return "要注意"


def esc(text):
    """HTMLエスケープ"""
    if not text:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_map(toilets, center_lat, center_lng, zoom):
    from folium.plugins import MarkerCluster
    m = folium.Map(location=[center_lat, center_lng], zoom_start=zoom, tiles="OpenStreetMap")

    cluster = MarkerCluster(
        options={"maxClusterRadius": 50, "spiderfyOnMaxZoom": True},
        name="トイレ"
    ).add_to(m)

    for t in toilets:
        color = score_to_color(t["toilet_score"])
        emoji = score_to_emoji(t["toilet_score"])
        radius = 14 if t["is_public_toilet"] else 10

        public_badge = '<span style="font-size:10px;padding:2px 6px;border-radius:3px;background:#e3f2fd;color:#1565c0;font-weight:600;">公共トイレ</span> ' if t["is_public_toilet"] else ""

        # キーワードタグ
        kw_html = ""
        if t.get("top_keywords"):
            tags = []
            for kw, cnt in t["top_keywords"][:5]:
                if kw.startswith("+"):
                    tags.append(f'<span style="display:inline-block;font-size:11px;padding:2px 7px;border-radius:4px;background:#e8f5e9;color:#2e7d32;border:1px solid #a5d6a7;margin:1px;">👍 {esc(kw[1:])} ×{cnt}</span>')
                elif kw.startswith("-"):
                    tags.append(f'<span style="display:inline-block;font-size:11px;padding:2px 7px;border-radius:4px;background:#ffebee;color:#c62828;border:1px solid #ef9a9a;margin:1px;">👎 {esc(kw[1:])} ×{cnt}</span>')
                else:
                    tags.append(f'<span style="display:inline-block;font-size:11px;padding:2px 7px;border-radius:4px;background:#f5f5f5;color:#555;border:1px solid #e0e0e0;margin:1px;">{esc(kw)} ×{cnt}</span>')
            kw_html = '<div style="margin-top:6px;line-height:2;">' + " ".join(tags) + "</div>"

        # レビュー
        rev_html = ""
        seen = set()
        for r in t.get("sample_reviews", [])[:5]:
            txt = r.get("text", "")
            key = txt[:80]
            if key in seen:
                continue
            seen.add(key)
            icon = "👍" if r.get("score", 0) > 0 else "👎" if r.get("score", 0) < 0 else "📝"
            txt_safe = esc(txt).replace("\n", "<br>")
            name = esc(r.get("name", ""))
            rating = r.get("rating", "")
            meta = f'<span style="color:#999;">{name}</span>'
            if rating:
                meta += f' <span style="color:#f9a825;">★{rating}</span>'
            rev_html += f"""<div style="font-size:11px;color:#444;padding:6px 8px;background:#fafafa;
                border-radius:4px;margin-top:4px;border-left:3px solid {'#2e7d32' if r.get('score',0)>0 else '#c62828' if r.get('score',0)<0 else '#bbb'};">
                {icon} {meta}<br>
                <span style="line-height:1.6;">{txt_safe}</span></div>"""

        link_html = f'<div style="margin-top:8px;"><a href="{t["link"]}" target="_blank" style="font-size:12px;color:#1a73e8;text-decoration:none;font-weight:600;">🗺️ Google Mapsで開く →</a></div>' if t.get("link") else ""

        popup_html = f"""
        <div style="min-width:300px;max-width:420px;max-height:520px;overflow-y:auto;
            font-family:'Segoe UI','Hiragino Sans','Noto Sans JP',sans-serif;padding:4px;">
          <div style="font-size:16px;font-weight:700;margin-bottom:4px;">
            {public_badge}{esc(t['title'])}
          </div>
          <div style="font-size:11px;color:#888;margin-bottom:8px;">{esc(t['category'])}</div>

          <div style="text-align:center;margin:8px 0;">
            <span style="font-size:32px;font-weight:800;color:{color};">{emoji} {t['toilet_score']:.0f}点</span>
            <span style="font-size:13px;color:#888;">（{score_label(t['toilet_score'])}）</span>
          </div>

          <div style="text-align:center;font-size:11px;color:#888;margin-bottom:4px;">
            信頼度 {int(t['confidence']*100)}% | トイレ言及 {t['toilet_review_count']}件
          </div>
          <div style="height:4px;border-radius:2px;background:#e0e0e0;margin-bottom:8px;overflow:hidden;">
            <div style="height:100%;width:{int(t['confidence']*100)}%;background:{color};border-radius:2px;"></div>
          </div>

          <div style="font-size:12px;color:#555;margin-bottom:2px;">📍 {esc(t.get('address',''))}</div>
          <div style="font-size:12px;color:#555;margin-bottom:2px;">⭐ {t.get('rating','-')} (口コミ {t.get('review_count',0)}件)</div>
          {f'<div style="font-size:12px;color:#555;">📞 {esc(t["phone"])}</div>' if t.get("phone") else ""}

          {kw_html}
        """

        if rev_html:
            popup_html += '<hr style="margin:8px 0 6px;border:none;border-top:1px dashed #ccc;">'
            popup_html += '<div style="font-size:12px;font-weight:600;margin-bottom:2px;">🚽 トイレ口コミ:</div>' + rev_html

        popup_html += link_html
        popup_html += "</div>"

        folium.CircleMarker(
            location=[t["lat"], t["lng"]],
            radius=radius,
            color="white",
            weight=2,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            popup=folium.Popup(popup_html, max_width=420),
            tooltip=f"{emoji} {t['title']}",
        ).add_to(cluster)

    return m


def filter_toilets(df, filter_type):
    if filter_type == "公共トイレ":
        return df[df["is_public_toilet"] == True]
    if filter_type == "カフェ・飲食":
        pat = "カフェ|喫茶|レストラン|食堂|ダイニング|コーヒー|パン|ケーキ"
        return df[df["category"].str.contains(pat, na=False)]
    if filter_type == "コンビニ・店舗":
        pat = "コンビニ|スーパー|ドラッグ|ストア|マート|商店"
        return df[df["category"].str.contains(pat, na=False)]
    return df


def main():
    st.set_page_config(page_title="トイレきれい度マップ", layout="wide", page_icon="🚽")

    data = _load_data_cached()
    meta = data["metadata"]
    toilets = data["toilets"]

    st.title("🚽 トイレきれい度マップ")

    df = pd.DataFrame(toilets)
    df = df[df["toilet_review_count"] > 0].reset_index(drop=True)

    st.caption(f"{meta['area_name']} - Googleレビューからトイレのきれい度を可視化 | トイレ口コミあり{len(df)}件")

    col_filter, col_search = st.columns([1, 2])

    with col_filter:
        filter_type = st.selectbox("フィルタ", ["すべて", "公共トイレ", "カフェ・飲食", "コンビニ・店舗"])

    with col_search:
        search_query = st.text_input("検索（名前・住所）", "")

    filtered = filter_toilets(df, filter_type)

    if search_query:
        mask = filtered["title"].str.contains(search_query, case=False, na=False) | \
               filtered["address"].str.contains(search_query, case=False, na=False)
        filtered = filtered[mask]

    # きれい度順でソート（デフォルト）
    filtered = filtered.sort_values("toilet_score", ascending=False)

    st.markdown(f"**{len(filtered)}件** 表示中　（きれい度順）")
    st.markdown("""
    <div style="display:flex;align-items:center;gap:4px;font-size:12px;margin-bottom:4px;">
        <span>💩 汚い</span>
        <div style="width:200px;height:14px;border-radius:7px;
            background:linear-gradient(to right,#e74c3c,#f39c12,#f1c40f,#2ecc71,#27ae60);"></div>
        <span>きれい ✨</span>
    </div>
    """, unsafe_allow_html=True)

    m = build_map(filtered.to_dict("records"), meta["center_lat"], meta["center_lng"], meta["zoom"])
    st_folium(m, height=700, returned_objects=[], use_container_width=True)


if __name__ == "__main__":
    main()
