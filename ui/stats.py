"""
ui/stats.py
統計ダッシュボード表示
app.py から分離
"""
import streamlit as st


def calc_avg_score(toilets: list) -> float:
    scored = [t for t in toilets if t.get("toilet_score", 0) > 0]
    if not scored:
        return 0.0
    return sum(t["toilet_score"] for t in scored) / len(scored)


def render_score_distribution(toilets: list):
    scored = [t for t in toilets if t.get("toilet_score", 0) > 0]
    if not scored:
        return
    total = len(scored)
    ranges = [
        (80, 101, "✨ 80-100", "#27ae60"),
        (65, 80, "😊 65-79", "#2ecc71"),
        (50, 65, "😐 50-64", "#f1c40f"),
        (35, 50, "😨 35-49", "#f39c12"),
        (0, 35, "💩 0-34", "#e74c3c"),
    ]
    bars_html = "<div style='margin-top:12px;'>"
    for lo, hi, label, color in ranges:
        count = sum(1 for t in scored if lo <= t["toilet_score"] < hi)
        pct = count / total * 100 if total > 0 else 0
        bars_html += (
            f"<div style='display:flex;align-items:center;margin:4px 0;font-size:13px;'>"
            f"<span style='width:90px;color:#f0f0f0;'>{label}</span>"
            f"<div style='flex:1;background:#2a3444;border-radius:4px;height:20px;overflow:hidden;'>"
            f"<div style='width:{pct}%;background:{color};height:100%;border-radius:4px;"
            f"min-width:{2 if count > 0 else 0}px;'></div></div>"
            f"<span style='width:60px;text-align:right;color:#aaa;margin-left:8px;'>{count} ({pct:.0f}%)</span>"
            f"</div>"
        )
    bars_html += "</div>"
    st.markdown(bars_html, unsafe_allow_html=True)


def render_stats(meta: dict, toilets: list, t: dict):
    with st.expander(t["stats"]):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(t["total"], meta.get("total", 0))
        with col2:
            st.metric(t["scored"], meta.get("scored", 0))
        with col3:
            st.metric(t["public"], meta.get("public_toilets", 0))
        with col4:
            avg_score = calc_avg_score(toilets)
            st.metric(t["avg_score"], f"{avg_score:.0f}")
        render_score_distribution(toilets)