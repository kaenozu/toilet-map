"""
ui/data_quality.py
Data quality dashboard for admin use.

Shows total records, prefecture breakdown, score distribution,
missing data stats, and freshness info.

Related: ui/stats.py, app.py, app_config.py
"""
import streamlit as st
import pandas as pd


def _calc_missing_stats(toilets: list) -> dict:
    total = len(toilets)
    no_score = sum(1 for t in toilets if t.get("toilet_score") is None)
    no_address = sum(
        1 for t in toilets if not t.get("address", "").strip()
    )
    no_prefecture = sum(
        1 for t in toilets if not t.get("prefecture", "").strip()
    )
    no_reviews = sum(
        1 for t in toilets if t.get("toilet_review_count", 0) == 0
    )
    return {
        "total": total,
        "no_score": no_score,
        "no_address": no_address,
        "no_prefecture": no_prefecture,
        "no_reviews": no_reviews,
    }


def render_data_quality(meta: dict, toilets: list, t: dict) -> None:
    with st.expander(t.get("data_quality", "📊 データ品質")):
        missing = _calc_missing_stats(toilets)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(t.get("total", "Total"), missing["total"])
        with col2:
            st.metric(
                t.get("dq_missing_score", "スコア欠損"),
                missing["no_score"],
            )
        with col3:
            st.metric(
                t.get("dq_missing_address", "住所欠損"),
                missing["no_address"],
            )
        with col4:
            st.metric(
                t.get("dq_missing_reviews", "口コミ0"),
                missing["no_reviews"],
            )

        pref_counts: dict[str, int] = {}
        for toilet in toilets:
            pref = toilet.get("prefecture", "")
            if pref:
                pref_counts[pref] = pref_counts.get(pref, 0) + 1

        if pref_counts:
            pref_df = pd.DataFrame(
                sorted(pref_counts.items(), key=lambda x: x[1], reverse=True),
                columns=["prefecture", "count"],
            )
            st.bar_chart(pref_df.set_index("prefecture"))

        scored = [
            t["toilet_score"]
            for t in toilets
            if t.get("toilet_score") is not None
        ]
        if scored:
            score_df = pd.DataFrame({"score": scored})
            st.subheader(t.get("dq_score_dist", "スコア分布"))
            st.bar_chart(
                score_df["score"].value_counts(bins=10).sort_index()
            )

        freshness = meta.get("last_updated") or meta.get("db_synced_at") or "N/A"
        st.caption(f"{t.get('freshness', 'Freshness')}: {freshness}")
