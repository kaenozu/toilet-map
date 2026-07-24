"""Data quality dashboard rendering from bounded SQL aggregates or legacy rows."""

from __future__ import annotations

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


def _coerce_count(value: object) -> int:
    if not isinstance(value, (int, float, str)):
        return 0
    try:
        return max(0, int(value))
    except (OverflowError, ValueError):
        return 0


def _format_missing_metric(count: object, total: object) -> str:
    missing_count = _coerce_count(count)
    total_count = _coerce_count(total)
    if total_count == 0:
        return f"{missing_count} (—)"
    return f"{missing_count} ({missing_count / total_count:.1%})"


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
    total = _coerce_count(missing.get("total", 0))

    with st.expander(t.get("data_quality", "📊 データ品質")):
        metric_rows = (
            (
                (t.get("dq_total", "Total"), str(total)),
                (t.get("dq_missing_score", "スコア欠損"), _format_missing_metric(missing.get("no_score"), total)),
                (t.get("dq_missing_reviews", "口コミ0"), _format_missing_metric(missing.get("no_reviews"), total)),
            ),
            (
                (t.get("dq_missing_address", "住所欠損"), _format_missing_metric(missing.get("no_address"), total)),
                (
                    t.get("dq_missing_prefecture", "都道府県欠損"),
                    _format_missing_metric(missing.get("no_prefecture"), total),
                ),
            ),
        )
        for metrics in metric_rows:
            for column, (label, value) in zip(st.columns(len(metrics)), metrics, strict=True):
                with column:
                    st.metric(label, value)

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
