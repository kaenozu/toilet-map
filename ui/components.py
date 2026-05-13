"""
ui/components.py
Streamlit UI components for toilet map
"""
import streamlit as st
from app_config import esc, get_score_style, safe_href
from .types import ToiletDict


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


def build_toilet_card_html(toilet: ToiletDict) -> str:
    """トイレカードのHTMLを返す"""
    t = toilet
    color, emoji, _ = get_score_style(t["toilet_score"])
    confidence_pct = int(t["confidence"] * 100)

    public_tag = (
        ' <span style="background:#e3f2fd;color:#1565c0;padding:1px 6px;border-radius:3px;font-size:10px;">公共</span>'
        if t.get("is_public_toilet")
        else ""
    )

    link_href = safe_href(t.get("link"))
    link_start = (
        f'<a href="{link_href}" target="_blank" rel="noopener noreferrer" style="text-decoration:none;color:inherit;">'
        if link_href
        else ""
    )
    link_end = "</a>" if link_href else ""

    return f"""
    {link_start}
    <div class="toilet-card" style="display:flex;align-items:center;gap:10px;padding:8px 12px;
        background:#ffffff;color:#222222;border-radius:8px;margin-bottom:4px;
        border:1px solid #e0e0e0;min-height:60px;
        -webkit-tap-highlight-color:transparent;">
        <div style="min-width:50px;text-align:center;">
            <div style="font-size:24px;font-weight:800;color:{color};line-height:1;">{emoji}</div>
            <div style="font-size:14px;font-weight:700;color:{color};">{t['toilet_score']:.0f}</div>
        </div>
        <div style="flex:1;min-width:0;color:#222222;">
            <div style="font-size:14px;font-weight:600;color:#222222;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                {public_tag} {esc(t['title'])}
            </div>
            <div style="font-size:11px;color:#666666;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                &#x1F4CD; {esc(t.get('address', ''))}
            </div>
            <div style="font-size:11px;color:#666666;">
                &#x2B50; {t.get('rating', '-')} &#xB7; 口コミ {t.get('review_count', 0)}件 &#xB7; 信頼度 {confidence_pct}%
            </div>
        </div>
        <div style="font-size:18px;color:#aaaaaa;">&#x203A;</div>
    </div>
    {link_end}
    """.strip()


def render_toilet_card(toilet: ToiletDict):
    """ランキングリストのトイレカード（1行）"""
    st.markdown(build_toilet_card_html(toilet), unsafe_allow_html=True)
