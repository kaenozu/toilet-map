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


def render_stats(meta: dict, toilets: list):
    with st.expander("📊 統計"):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("総数", meta.get("total", 0))
        with col2:
            st.metric("スコア算出", meta.get("scored", 0))
        with col3:
            st.metric("公共トイレ", meta.get("public_toilets", 0))
        with col4:
            avg_score = calc_avg_score(toilets)
            st.metric("平均スコア", f"{avg_score:.0f}")