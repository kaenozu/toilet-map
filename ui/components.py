"""
ui/components.py
Streamlit UI components for toilet map
"""
import streamlit as st
from app_config import get_score_style, esc, FILTER_CONFIG, MAX_SAMPLE_REVIEWS


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


def render_toilet_card(toilet: dict, rank: int = None):
    """ランキングリストのトイレカード（1行）"""
    t = toilet
    color, emoji, label = get_score_style(t["toilet_score"])
    confidence_pct = int(t["confidence"] * 100)

    public_tag = ' <span style="background:#e3f2fd;color:#1565c0;padding:1px 6px;border-radius:3px;font-size:10px;">公共</span>' if t.get("is_public_toilet") else ""

    link_start = f'<a href="{t["link"]}" target="_blank" rel="noopener noreferrer" style="text-decoration:none;color:inherit;">' if t.get("link") else ""
    link_end = "</a>" if t.get("link") else ""

    rank_html = f'<span style="color:#999;font-weight:600;min-width:24px;">#{rank}</span>' if rank else ""

    st.markdown(
        f"""
        {link_start}
        <div class="toilet-card" style="display:flex;align-items:center;gap:10px;padding:8px 12px;
            background:#ffffff;color:#222222;border-radius:8px;margin-bottom:4px;
            border:1px solid #e0e0e0;min-height:60px;
            -webkit-tap-highlight-color:transparent;">
            {rank_html}
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
        """,
        unsafe_allow_html=True,
    )