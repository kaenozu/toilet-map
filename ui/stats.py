"""
ui/stats.py
統計ダッシュボード表示
app.py から分離
"""
import streamlit as st
from app_config import SCORE_DISTRIBUTION_RANGES


def calc_avg_score(toilets: list) -> float:
    scored = [t for t in toilets if t.get("toilet_score", 0) > 0]
    if not scored:
        return 0.0
    return sum(t["toilet_score"] for t in scored) / len(scored)


def calc_score_distribution(toilets: list) -> list[dict]:
    scored = [t for t in toilets if t.get("toilet_score", 0) > 0]
    if not scored:
        return []
    total = len(scored)
    counts = [0] * len(SCORE_DISTRIBUTION_RANGES)
    for t in scored:
        s = t["toilet_score"]
        for i, (lo, hi, _, _) in enumerate(SCORE_DISTRIBUTION_RANGES):
            if lo <= s < hi:
                counts[i] += 1
                break
    result = []
    for count, (_, _, label, color) in zip(counts, SCORE_DISTRIBUTION_RANGES):
        pct = count / total * 100 if total > 0 else 0
        result.append({"count": count, "pct": round(pct, 1), "label": label, "color": color})
    return result


def render_score_distribution(toilets: list):
    dist = calc_score_distribution(toilets)
    if not dist:
        return
    bars_html = "<div style='margin-top:12px;'>"
    for d in dist:
        bars_html += (
            f"<div style='display:flex;align-items:center;margin:4px 0;font-size:13px;'>"
            f"<span style='width:90px;color:#f0f0f0;'>{d['label']}</span>"
            f"<div style='flex:1;background:#2a3444;border-radius:4px;height:20px;overflow:hidden;'>"
            f"<div style='width:{d['pct']}%;background:{d['color']};height:100%;border-radius:4px;"
            f"min-width:{2 if d['count'] > 0 else 0}px;'></div></div>"
            f"<span style='width:60px;text-align:right;color:#aaa;margin-left:8px;'>{d['count']} ({d['pct']:.0f}%)</span>"
            f"</div>"
        )
    bars_html += "</div>"
    st.markdown(bars_html, unsafe_allow_html=True)


def render_stats(meta: dict, toilets: list, t: dict):
    with st.expander(f"{t['stats']}（{t.get('stats_all', '全体')}）"):
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
