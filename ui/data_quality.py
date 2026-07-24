"""Data quality dashboard rendering from bounded SQL aggregates or legacy rows."""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd
import streamlit as st

from .types import ToiletDict


def _calc_missing_stats(toilets: list[ToiletDict]) -> dict[str, int]:
    total = len(toilets)
    no_score = sum(1 for t in toilets if t.get("toilet_score") is None)
    no_address = sum(1 for t in toilets if not (t.get("address") or "").strip())
    no_prefecture = sum(1 for t in toilets if not (t.get("prefecture") or "").strip())
    no_reviews = sum(1 for t in toilets if t.get("toilet_review_count", 0) == 0)
    return {
        "total": total,
        "no_score": no_score,
        "no_address": no_address,
        "no_prefecture": no_prefecture,
        "no_reviews": no_reviews,
    }


def _as_count(value: object, total: int | None = None) -> int:
    """Convert aggregate values to safe non-negative counts."""
    if not isinstance(value, (int, float, str)):
        return 0
    try:
        count = max(0, int(value))
    except (ValueError, OverflowError):
        count = 0
    return min(count, total) if total is not None else count


def build_data_quality_summary(missing: Mapping[str, object], t: Mapping[str, str]) -> str | None:
    """Build a concise, screen-reader-friendly explanation of data coverage."""
    total = _as_count(missing.get("total"))
    if total == 0:
        return None

    no_score = _as_count(missing.get("no_score"), total)
    no_address = _as_count(missing.get("no_address"), total)
    no_prefecture = _as_count(missing.get("no_prefecture"), total)
    scored = total - no_score
    coverage = round(scored * 100 / total)
    scored_label = t.get("scored", "Scored")

    summary = f"{scored_label}: {scored}/{total} ({coverage}%) · 未採点 / Unscored: {no_score}."
    if no_score:
        summary += " 未採点は低評価ではありません / Unscored does not mean a low rating."
    if no_address or no_prefecture:
        summary += (
            f" 住所欠損 / Missing address: {no_address} · "
            f"都道府県欠損 / Missing prefecture: {no_prefecture}. "
            "位置情報の欠損は検索・集計精度に影響します / "
            "Missing location fields may affect search and aggregation accuracy."
        )
    return summary


def _legacy_summary(toilets: list[ToiletDict]) -> dict[str, object]:
    pref_counts: dict[str, int] = {}
    for toilet in toilets:
        pref = toilet.get("prefecture", "")
        if pref:
            pref_counts[pref] = pref_counts.get(pref, 0) + 1
    scored = [t["toilet_score"] for t in toilets if t.get("toilet_score") is not None]
    score_bins: list[dict[str, object]] = []
    if scored:
        counts = pd.Series(scored).value_counts(bins=10).sort_index()
        score_bins = [{"label": str(index), "count": int(count)} for index, count in counts.items()]
    return {"missing": _calc_missing_stats(toilets), "pref_counts": pref_counts, "score_bins": score_bins}


def render_data_quality(meta: dict, data: list[ToiletDict] | dict[str, object], t: dict) -> None:
    summary = data if isinstance(data, dict) else _legacy_summary(data)
    missing_value = summary.get("missing", {}) if isinstance(summary, dict) else {}
    pref_counts_value = summary.get("pref_counts", {}) if isinstance(summary, dict) else {}
    score_bins_value = summary.get("score_bins", []) if isinstance(summary, dict) else []
    missing = missing_value if isinstance(missing_value, dict) else {}
    pref_counts = pref_counts_value if isinstance(pref_counts_value, dict) else {}
    score_bins = score_bins_value if isinstance(score_bins_value, list) else []

    with st.expander(t.get("data_quality", "📊 データ品質")):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(t.get("dq_total", "Total"), missing.get("total", 0))
        with col2:
            st.metric("未採点 / Unscored", missing.get("no_score", 0))
        with col3:
            st.metric(t.get("dq_missing_address", "住所欠損"), missing.get("no_address", 0))
        with col4:
            st.metric(t.get("dq_missing_reviews", "口コミ0"), missing.get("no_reviews", 0))

        quality_summary = build_data_quality_summary(missing, t)
        if quality_summary:
            st.caption(quality_summary)

        if pref_counts:
            pref_df = pd.DataFrame(
                sorted(pref_counts.items(), key=lambda item: item[1], reverse=True),
                columns=["prefecture", "count"],
            )
            st.bar_chart(pref_df.set_index("prefecture"))

        if score_bins:
            score_df = pd.DataFrame(score_bins)
            st.subheader(t.get("dq_score_dist", "スコア分布"))
            st.bar_chart(score_df.set_index("label")["count"])

        freshness = meta.get("last_updated") or meta.get("db_synced_at") or "N/A"
        st.caption(f"{t.get('freshness', 'Freshness')}: {freshness}")
