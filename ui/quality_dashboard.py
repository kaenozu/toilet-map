"""
ui/quality_dashboard.py
Data quality age graph and diff report for the toilet-map app.
Related: ui/data_quality.py, batch/verify_data.py, app.py
"""
from datetime import UTC, datetime

import pandas as pd
import streamlit as st


def _is_data_stale(meta: dict) -> bool:
    """Check if data is older than 7 days."""
    raw = meta.get("last_updated") or ""
    if not raw:
        return False
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(str(raw).strip()[:19], fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            delta = datetime.now(UTC) - parsed
            return delta.days > 7
        except ValueError:
            continue
    return False


def render_quality_dashboard(meta: dict, toilets: list[dict], t: dict) -> None:
    """Render the quality dashboard expander with age and diff info."""
    with st.expander(t.get("data_quality", "\U0001f4ca \u30c7\u30fc\u30bf\u54c1\u8cea"), expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            age_days = _calc_data_age_days(meta)
            st.metric(
                "\u30c7\u30fc\u30bf\u7d4c\u904e\u65e5\u6570",
                f"{age_days}\u65e5",
                delta="\u53e4\u3044" if age_days > 7 else "\u65b0\u3057\u3044",
                delta_color="inverse",
            )
        with col2:
            st.metric("\u7dcf\u30c8\u30a4\u30ec\u6570", len(toilets))
        with col3:
            stale = _is_data_stale(meta)
            st.metric(
                "\u72b6\u614b",
                "\u26a0\ufe0f \u8981\u66f4\u65b0" if stale else "\u2705 \u6700\u65b0",
            )

        # Score distribution
        scores = [t.get("toilet_score") for t in toilets if t.get("toilet_score") is not None]
        if scores:
            st.caption("\u30b9\u30b3\u30a2\u5206\u5e03")
            score_series = pd.Series(scores, name="score")
            st.bar_chart(
                score_series.value_counts(bins=10).sort_index(),
                height=150,
            )


def _calc_data_age_days(meta: dict) -> int:
    raw = meta.get("last_updated", "")
    if not raw:
        return -1
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(str(raw).strip()[:19], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return (datetime.now(UTC) - dt).days
        except ValueError:
            continue
    return -1
