"""
ui/components.py
Streamlit UI components for toilet map
"""
import streamlit as st


def build_data_freshness_text(meta: dict, t: dict) -> str:
    """生成日時と SQLite 同期日時を短い1行で返す。"""
    generated_at = meta.get("last_updated") or "N/A"
    synced_at = meta.get("db_synced_at") or "N/A"
    return f"{t['freshness']} | {t['source_updated']} {generated_at} / {t['db_synced']} {synced_at}"


def build_result_context_text(
    list_items: int,
    map_items: int,
    filter_elapsed_ms: float | None = None,
    map_elapsed_ms: float | None = None,
    t: dict | None = None,
) -> str:
    """一覧件数と地図件数、簡易計測結果を短い文で返す。"""
    labels = t or {}
    list_label = labels.get("result_context_list", "一覧")
    map_label = labels.get("result_context_map", "地図")
    filter_label = labels.get("result_context_filter", "絞り込み")
    count_suffix = labels.get("result_context_count_suffix", "件")
    parts = [f"{list_label} {list_items}{count_suffix}"]
    parts.append(f"{map_label} {map_items}{count_suffix}")
    timings = []
    if filter_elapsed_ms is not None:
        timings.append(f"{filter_label} {filter_elapsed_ms:.0f}ms")
    if map_elapsed_ms is not None:
        timings.append(f"{map_label} {map_elapsed_ms:.0f}ms")
    if timings:
        parts.append(" / ".join(timings))
    return " | ".join(parts)


def render_score_legend():
    """スコア凡例を表示（レスポンシブ）"""
    st.markdown(
        """
    <div class="score-legend-mobile" style="display:flex;align-items:center;gap:4px;font-size:12px;margin-bottom:4px;">
        <span>💩</span>
        <div class="bar" style="width:200px;height:14px;border-radius:7px;
            background:linear-gradient(to right,#e74c3c,#f39c12,#f1c40f,#2ecc71,#27ae60);"></div>
        <span>✨</span>
    </div>
    """,
        unsafe_allow_html=True,
    )


