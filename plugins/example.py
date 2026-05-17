"""
plugins/example.py
Example plugin: show top keywords as a bar chart.
Related: ui/plugin_api.py
"""
from collections import Counter

import streamlit as st


def widget(toilets: list[dict], t: dict) -> None:
    """Display a keyword frequency bar chart."""
    st.caption("🏷 キーワード頻度（プラグイン）")
    all_keywords = []
    for toilet in toilets[:200]:
        keywords = toilet.get("top_keywords") or []
        if isinstance(keywords, list):
            for kw in keywords:
                if isinstance(kw, (list, tuple)) and len(kw) > 0:
                    all_keywords.append(str(kw[0]))
                elif isinstance(kw, str):
                    all_keywords.append(kw)
    if all_keywords:
        counter = Counter(all_keywords)
        top = dict(counter.most_common(10))
        st.bar_chart(top, height=150)
