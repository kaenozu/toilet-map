"""
ui/components.py
Streamlit UI components for toilet map
"""
from datetime import datetime

import streamlit as st

from .helpers import esc, get_score_style, get_toilet_identity_key, safe_href
from .reviews import render_review_form
from .types import ToiletDict


def _parse_timestamp(value: object) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _build_score_reason_text(toilet: ToiletDict) -> str:
    keywords = toilet.get("top_keywords") or []
    pos_hits = 0
    neg_hits = 0
    for kw, count in keywords:
        if kw.startswith("+"):
            pos_hits += count
        elif kw.startswith("-"):
            neg_hits += count

    toilet_review_count = int(toilet.get("toilet_review_count", 0) or 0)
    if pos_hits == 0 and neg_hits == 0:
        return f"根拠: トイレ言及 {toilet_review_count}件 と評価から算出"
    return (
        f"根拠: トイレ言及 {toilet_review_count}件 "
        f"(ポジ語 {pos_hits} / ネガ語 {neg_hits})"
    )


def build_data_freshness_text(meta: dict[str, object], t: dict[str, str]) -> str:
    """生成日時と SQLite 同期日時を短い1行で返す。"""
    generated_at = meta.get("last_updated") or "N/A"
    synced_at = meta.get("db_synced_at") or "N/A"
    text = f"{t['freshness']} | {t['source_updated']} {generated_at} / {t['db_synced']} {synced_at}"

    generated_dt = _parse_timestamp(generated_at)
    if generated_dt is None:
        return text

    now = datetime.now(generated_dt.tzinfo)
    age_days = (now - generated_dt).days
    stale_days = 7
    if age_days >= stale_days:
        stale_label = t.get("freshness_stale", "更新から")
        day_label = t.get("freshness_days", "日")
        text = f"{text} | ⚠ {stale_label} {age_days}{day_label}"
    return text


def build_result_context_text(
    list_items: int,
    map_items: int,
    filter_elapsed_ms: float | None = None,
    map_elapsed_ms: float | None = None,
    t: dict[str, str] | None = None,
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


def render_score_legend() -> None:
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


def _build_links_html(t: ToiletDict) -> str:
    """トイレカード内の外部リンクを返す"""
    parts = []
    link_href = safe_href(t.get("link"))
    if link_href:
        parts.append(
            f'<a href="{link_href}" target="_blank" rel="noopener noreferrer" '
            f'style="font-size:11px;color:#1a73e8;text-decoration:none;margin-right:10px;">'
            f"Google Maps で開く</a>"
        )
    lat = t.get("lat")
    lng = t.get("lng")
    if lat is not None and lng is not None:
        dirs_url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}"
        parts.append(
            f'<a href="{dirs_url}" target="_blank" rel="noopener noreferrer" '
            f'style="font-size:11px;color:#1a73e8;text-decoration:none;">'
            f"&#x1F4CD; ルート検索</a>"
        )
    return "".join(parts)


def build_toilet_card_html(toilet: ToiletDict, rank: int | None = None, meta: dict | None = None, compact: bool = False) -> str:
    """トイレカードのHTMLを返す"""
    t = toilet
    color, emoji, _ = get_score_style(t["toilet_score"])
    confidence_pct = int(t["confidence"] * 100)

    rank_html = f'<span style="color:#999;font-weight:600;min-width:24px;">#{rank}</span>' if rank else ""

    freshness_badge = ""
    freshness_value = None
    if meta:
        freshness_value = meta.get("last_updated") or meta.get("updated_at")
    if freshness_value:
        date_part = str(freshness_value)[:10]
        freshness_badge = (
            f'<span style="background:#fff3e0;color:#e65100;padding:1px 6px;'
            f'border-radius:3px;font-size:10px;margin-left:6px;">'
            f'📅 データ: {date_part}</span>'
        )

    public_tag = (
        ' <span style="background:#e3f2fd;color:#1565c0;padding:1px 6px;border-radius:3px;font-size:10px;">公共</span>'
        if t.get("is_public_toilet")
        else ""
    )

    if compact:
        aria_label = f"{esc(t['title'])} - {t['toilet_score']:.0f}点"
        return f"""
        <div class="toilet-card" aria-label="{aria_label}"
            style="display:flex;align-items:center;gap:6px;padding:4px 8px;
            background:#ffffff;color:#222222;border-radius:6px;margin-bottom:2px;
            border:1px solid #e0e0e0;min-height:40px;
            -webkit-tap-highlight-color:transparent;">
            {rank_html}
            <div style="min-width:36px;text-align:center;">
                <div aria-hidden="true" style="font-size:18px;font-weight:700;color:{color};line-height:1;">{emoji}</div>
                <div style="font-size:11px;font-weight:600;color:{color};">{t['toilet_score']:.0f}</div>
            </div>
            <div style="flex:1;min-width:0;color:#222222;">
                <div style="font-size:12px;font-weight:600;color:#222222;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                    {esc(t['title'])}
                </div>
                <div style="font-size:10px;color:#666666;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                    &#x1F4CD; {esc(t.get('address', ''))}
                </div>
                <div style="font-size:10px;color:#666666;">
                    口コミ {t.get('review_count', 0)}件
                </div>
            </div>
        </div>
        """.strip()

    links_html = _build_links_html(t)
    score_reason = _build_score_reason_text(t)

    aria_label = f"{esc(t['title'])} - {t['toilet_score']:.0f}点"
    return f"""
    <div class="toilet-card" aria-label="{aria_label}"
        style="display:flex;align-items:center;gap:10px;padding:8px 12px;
        background:#ffffff;color:#222222;border-radius:8px;margin-bottom:4px;
        border:1px solid #e0e0e0;min-height:60px;
        -webkit-tap-highlight-color:transparent;">
        {rank_html}
        <div style="min-width:50px;text-align:center;">
            <div aria-hidden="true" style="font-size:24px;font-weight:800;color:{color};line-height:1;">{emoji}</div>
            <div style="font-size:14px;font-weight:700;color:{color};">{t['toilet_score']:.0f}</div>
        </div>
        <div style="flex:1;min-width:0;color:#222222;">
            <div class="toilet-card-title" style="font-size:14px;font-weight:600;color:#222222;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                {public_tag} {esc(t['title'])}
            </div>
            <div class="toilet-card-subtitle" style="font-size:11px;color:#666666;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                &#x1F4CD; {esc(t.get('address', ''))}{freshness_badge}
            </div>
            <div class="toilet-card-meta" style="font-size:11px;color:#666666;">
                &#x2B50; {t.get('rating', '-')} &#xB7; 口コミ {t.get('review_count', 0)}件 &#xB7; 信頼度 {confidence_pct}%
            </div>
            <div class="toilet-card-meta" style="font-size:10px;color:#757575;">
                {esc(score_reason)}
            </div>
            <div style="font-size:11px;margin-top:4px;">
                {links_html}
            </div>
        </div>
        <div class="toilet-card-arrow" style="font-size:18px;color:#aaaaaa;">&#x203A;</div>
    </div>
    """.strip()


def render_toilet_card(
    toilet: ToiletDict,
    rank: int | None = None,
    meta: dict[str, object] | None = None,
    compact: bool = False,
    include_review_form: bool = True,
) -> None:
    """ランキングリストのトイレカード（1行）"""
    st.markdown(build_toilet_card_html(toilet, rank, meta, compact=compact), unsafe_allow_html=True)
    if not compact and include_review_form:
        render_review_form(get_toilet_identity_key(toilet), toilet.get("title", ""))
