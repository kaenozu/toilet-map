"""
ui/components.py
Streamlit UI components for toilet map
"""
from datetime import date, datetime

import streamlit as st

from .helpers import esc, format_score, get_confidence_percentage, get_score_style, safe_href
from .types import ToiletDict

FRESH_DATA_MAX_AGE_DAYS = 7
STALE_DATA_MIN_AGE_DAYS = 31


def _parse_metadata_date(value: object) -> date | None:
    """Metadata timestampを日付へ変換し、解釈できない値はNoneにする。"""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return None


def _freshness_status(generated_on: date | None, today: date, t: dict[str, str]) -> tuple[str, str]:
    """生成日から表示用の鮮度ステータスと経過日数を返す。"""
    if generated_on is None:
        return "⚪", t.get("freshness_unknown", "Update date unknown")

    age_days = (today - generated_on).days
    if age_days < 0:
        return "⚪", t.get("freshness_unknown", "Update date unknown")

    age_text = t.get("freshness_age_days", "{days} days ago").format(days=age_days)
    if age_days <= FRESH_DATA_MAX_AGE_DAYS:
        label = t.get("freshness_current", "Current")
        return "🟢", f"{label} ({age_text})"
    if age_days < STALE_DATA_MIN_AGE_DAYS:
        label = t.get("freshness_aging", "Aging")
        return "🟡", f"{label} ({age_text})"
    label = t.get("freshness_stale", "Stale")
    return "🔴", f"{label} ({age_text})"


def build_data_freshness_text(
    meta: dict[str, object],
    t: dict[str, str],
    today: date | None = None,
) -> str:
    """生成日時・SQLite同期日時と、更新経過日数に応じた鮮度状態を返す。"""
    generated_at = meta.get("last_updated") or "N/A"
    synced_at = meta.get("db_synced_at") or "N/A"
    icon, status = _freshness_status(_parse_metadata_date(meta.get("last_updated")), today or date.today(), t)
    return (
        f"{icon} {t['freshness']}: {status} | "
        f"{t['source_updated']} {generated_at} / {t['db_synced']} {synced_at}"
    )


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


def build_score_legend_html() -> str:
    """採点済みの色勾配と未採点状態を説明する凡例HTMLを返す。"""
    return """
    <div class="score-legend-mobile" role="group" aria-label="スコア凡例 / Score legend"
        style="display:flex;align-items:center;flex-wrap:wrap;gap:4px;font-size:12px;margin-bottom:4px;">
        <span aria-hidden="true">💩</span>
        <div class="bar" aria-label="低スコアから高スコア / Low to high score"
            style="width:200px;height:14px;border-radius:7px;
            background:linear-gradient(to right,#e74c3c,#f39c12,#f1c40f,#2ecc71,#27ae60);"></div>
        <span aria-hidden="true">✨</span>
        <span class="unscored-legend"
            style="display:inline-flex;align-items:center;gap:3px;margin-left:6px;white-space:nowrap;">
            <span aria-hidden="true" style="font-size:16px;font-weight:700;color:#6b7280;">○</span>
            <span>未採点 / Unscored</span>
        </span>
    </div>
    """.strip()


def render_score_legend() -> None:
    """スコア凡例を表示（レスポンシブ）"""
    st.markdown(build_score_legend_html(), unsafe_allow_html=True)


def _build_links_html(t: ToiletDict) -> str:
    """トイレカード内の外部リンクを返す。リンク目的を施設名込みで読み上げ可能にする。"""
    parts = []
    title = esc(str(t.get("title") or "トイレ / Toilet"))
    link_href = safe_href(t.get("link"))
    if link_href:
        parts.append(
            f'<a href="{link_href}" target="_blank" rel="noopener noreferrer" '
            f'aria-label="{title}をGoogle Mapsで開く（新しいタブ） / '
            f'Open {title} in Google Maps (new tab)" '
            f'style="font-size:11px;color:#1a73e8;text-decoration:none;margin-right:10px;">'
            f"Google Maps で開く</a>"
        )
    lat = t.get("lat")
    lng = t.get("lng")
    if lat is not None and lng is not None:
        dirs_url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}"
        parts.append(
            f'<a href="{dirs_url}" target="_blank" rel="noopener noreferrer" '
            f'aria-label="{title}へのルートを検索（新しいタブ） / '
            f'Get directions to {title} (new tab)" '
            f'style="font-size:11px;color:#1a73e8;text-decoration:none;">'
            f"&#x1F4CD; ルート検索</a>"
        )
    return "".join(parts)


def _build_toilet_card_aria_label(
    toilet: ToiletDict,
    rank: int | None,
    score_text: str,
    rating_text: object,
    confidence_text: str,
) -> str:
    """視覚的なカード情報を重複なく読み上げるアクセシブル名を返す。"""
    parts = []
    if rank is not None:
        parts.append(f"順位 {rank}位")
    parts.append(str(toilet.get("title") or "トイレ"))
    parts.append(f"スコア {score_text}点" if score_text != "—" else "未採点")
    if rating_text != "-":
        parts.append(f"評価 {rating_text}")
    parts.append(f"口コミ {toilet.get('review_count', 0)}件")
    parts.append(f"信頼度 {confidence_text}")
    if toilet.get("is_public_toilet"):
        parts.append("公共トイレ")
    address = str(toilet.get("address") or "").strip()
    if address:
        parts.append(f"住所 {address}")
    return esc("、".join(parts))


def build_toilet_card_html(toilet: ToiletDict, rank: int | None = None, meta: dict | None = None) -> str:
    """トイレカードのHTMLを返す"""
    t = toilet
    score_text = format_score(t.get("toilet_score"))
    color, emoji, _ = get_score_style(t.get("toilet_score"))
    confidence_pct = get_confidence_percentage(t.get("confidence"))
    confidence_text = f"{confidence_pct}%" if confidence_pct is not None else "—"
    rating_text = t["rating"] if t.get("rating") is not None else "-"

    rank_html = (
        f'<span aria-hidden="true" style="color:#999;font-weight:600;min-width:24px;">#{rank}</span>'
        if rank
        else ""
    )

    freshness_badge = ""
    if meta and meta.get("updated_at"):
        date_part = str(meta["updated_at"])[:10]
        freshness_badge = (
            f'<span style="background:#fff3e0;color:#e65100;padding:1px 6px;'
            f'border-radius:3px;font-size:10px;margin-left:6px;">'
            f"📅 データ: {date_part}</span>"
        )

    public_tag = (
        ' <span style="background:#e3f2fd;color:#1565c0;padding:1px 6px;border-radius:3px;font-size:10px;">公共</span>'
        if t.get("is_public_toilet")
        else ""
    )

    links_html = _build_links_html(t)
    aria_label = _build_toilet_card_aria_label(t, rank, score_text, rating_text, confidence_text)
    return f"""
    <div class="toilet-card" role="listitem" aria-label="{aria_label}"
        style="display:flex;align-items:center;gap:10px;padding:8px 12px;
        background:#ffffff;color:#222222;border-radius:8px;margin-bottom:4px;
        border:1px solid #e0e0e0;min-height:60px;
        -webkit-tap-highlight-color:transparent;">
        {rank_html}
        <div style="min-width:50px;text-align:center;">
            <div aria-hidden="true" style="font-size:24px;font-weight:800;color:{color};line-height:1;">{emoji}</div>
            <div style="font-size:14px;font-weight:700;color:{color};">{score_text}</div>
        </div>
        <div style="flex:1;min-width:0;color:#222222;">
            <div class="toilet-card-title" style="font-size:14px;font-weight:600;color:#222222;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                {public_tag} {esc(t['title'])}
            </div>
            <div class="toilet-card-subtitle" style="font-size:11px;color:#666666;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                <span aria-hidden="true">&#x1F4CD;</span> {esc(t.get('address', ''))}{freshness_badge}
            </div>
            <div class="toilet-card-meta" style="font-size:11px;color:#666666;">
                <span aria-hidden="true">&#x2B50;</span> {rating_text} &#xB7; 口コミ {t.get('review_count', 0)}件 &#xB7; 信頼度 {confidence_text}
            </div>
            <div style="font-size:11px;margin-top:4px;">
                {links_html}
            </div>
        </div>
        <div class="toilet-card-arrow" aria-hidden="true" style="font-size:18px;color:#aaaaaa;">&#x203A;</div>
    </div>
    """.strip()


def render_toilet_card(toilet: ToiletDict, rank: int | None = None, meta: dict[str, object] | None = None) -> None:
    """ランキングリストのトイレカード（1行）"""
    st.markdown(build_toilet_card_html(toilet, rank, meta), unsafe_allow_html=True)
