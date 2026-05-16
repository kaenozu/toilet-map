"""
ui/stats.py
統計ダッシュボード表示（Altair グラフ）
app.py から分離
"""
import altair as alt
import pandas as pd
import streamlit as st

from app_config import SCORE_DISTRIBUTION_RANGES

from .types import ToiletDict


def calc_avg_score(toilets: list[ToiletDict]) -> float:
    scored = [t for t in toilets if t.get("toilet_score") is not None and t.get("toilet_score", 0) > 0]
    if not scored:
        return 0.0
    return sum(t["toilet_score"] for t in scored) / len(scored)


def calc_score_distribution(toilets: list[ToiletDict]) -> list[dict[str, object]]:
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


def render_score_distribution(toilets: list[ToiletDict]) -> None:
    dist = calc_score_distribution(toilets)
    if not dist:
        return
    df = pd.DataFrame(dist)
    chart = alt.Chart(df).mark_bar().encode(
        x=alt.X("label:N", title=None, sort=None),
        y=alt.Y("count:Q", title="件数"),
        color=alt.Color("color:N", scale=None, legend=None),
        tooltip=["label:N", "count:Q", "pct:Q"],
    ).properties(height=200)
    st.altair_chart(chart, use_container_width=True)


def render_stats(meta: dict, toilets: list[ToiletDict], t: dict) -> None:
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
