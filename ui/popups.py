"""
ui/popups.py
Popup HTML builders for toilet map markers
"""
import logging

from app_config import MAX_SAMPLE_REVIEWS, REVIEW_TEXT_MAX_LENGTH

from .helpers import esc, get_score_style, safe_href
from .types import ToiletDict

logger = logging.getLogger(__name__)


def clean(s: str | None) -> str:
    """文字列をサニタイズして改行をスペースに置換（シングルクォートは esc が自動エスケープ）"""
    if not s:
        return ""
    return esc(str(s)).replace("\n", " ").replace("\r", " ")


def _build_public_badge(is_public: bool) -> str:
    if not is_public:
        return ""
    return (
        '<span style="font-size:10px;padding:2px 6px;border-radius:3px;'
        'background:#e3f2fd;color:#1565c0;font-weight:600;">公共トイレ</span> '
    )


def _build_keyword_tags(keywords: list[tuple[str, int]]) -> str:
    if not keywords:
        return ""
    tags = []
    for kw, cnt in keywords[:5]:
        safe_kw = esc(kw[1:]) if kw.startswith(("+", "-")) else esc(kw)
        prefix = '<span aria-label="positive" role="img">👍</span>' if kw.startswith("+") else '<span aria-label="negative" role="img">👎</span>' if kw.startswith("-") else ""
        bg = "#e8f5e9" if kw.startswith("+") else "#ffebee" if kw.startswith("-") else "#f5f5f5"
        color = "#2e7d32" if kw.startswith("+") else "#c62828" if kw.startswith("-") else "#555"
        border = "#a5d6a7" if kw.startswith("+") else "#ef9a9a" if kw.startswith("-") else "#e0e0e0"
        tags.append(
            f'<span style="display:inline-block;font-size:11px;padding:2px 6px;'
            f'border-radius:4px;background:{bg};color:{color};'
            f'border:1px solid {border};margin:1px;word-break:break-all;">'
            f'{prefix}{safe_kw} ×{cnt}</span>'
        )
    return '<div style="margin-top:4px;line-height:2;">' + " ".join(tags) + "</div>"


def _build_review_html(reviews: list[dict]) -> str:
    if not reviews:
        return ""
    seen = set()
    parts = []
    for r in reviews[:MAX_SAMPLE_REVIEWS]:
        txt = r.get("text", "")
        key = txt[:80]
        if key in seen:
            continue
        seen.add(key)
        score_val = r.get("score", 0)
        icon = '<span aria-label="thumbs up" role="img">👍</span>' if score_val > 0 else '<span aria-label="thumbs down" role="img">👎</span>' if score_val < 0 else '<span aria-label="review" role="img">📝</span>'
        border_color = "#2e7d32" if score_val > 0 else "#c62828" if score_val < 0 else "#bbb"
        name = esc(r.get("name", ""))
        rating = r.get("rating", "")
        meta = f'<span style="color:#999;">{name}</span>'
        if rating:
            meta += f' <span style="color:#f9a825;">★{rating}</span>'
        txt_safe = esc(txt).replace("\n", "<br>")
        display_text = txt_safe[:REVIEW_TEXT_MAX_LENGTH]
        suffix = "..." if len(txt_safe) > REVIEW_TEXT_MAX_LENGTH else ""
        parts.append(
            f'<div style="font-size:11px;color:#444;padding:4px 6px;background:#fafafa;'
            f'border-radius:4px;margin-top:3px;border-left:3px solid {border_color};">'
            f"{icon} {meta}<br>"
            f'<span style="line-height:1.5;">{display_text}{suffix}</span></div>'
        )
    return "".join(parts)


def _build_link_html(link: str) -> str:
    safe_link = safe_href(link)
    if not safe_link:
        return ""
    return (
        '<div style="margin-top:6px;">'
        f'<a href="{safe_link}" target="_blank" rel="noopener noreferrer" '
        'style="font-size:13px;color:#1a73e8;text-decoration:none;font-weight:600;'
        'display:inline-block;padding:4px 0;">'
        "🗺️ Google Mapsで開く →</a></div>"
    )


def _build_review_link_html(t: ToiletDict) -> str:
    if not t.get("place_id"):
        return ""
    return '<div style="margin-top:4px;font-size:10px;"><a href="#" onclick="alert(\'レビュー機能は地図画面でご利用ください\')" style="color:#888;">\U0001f4ac レビューを書く</a></div>'


def _build_ai_summary_html(t: ToiletDict) -> str:
    summary = t.get("ai_cleanliness_summary")
    score = t.get("ai_sentiment_score")
    if not summary and score is None:
        return ""
    color = "#2e7d32" if (score or 50) >= 60 else "#e65100"
    bg = "#e8f5e9" if (score or 50) >= 60 else "#fff3e0"
    border = "#a5d6a7" if (score or 50) >= 60 else "#ffe0b2"
    score_html = f'<span style="font-weight:600;">{score:.0f}</span>' if score is not None else ""
    return (
        f'<div style="margin-top:6px;padding:6px 8px;border-radius:6px;'
        f'background:{bg};color:{color};border:1px solid {border};'
        f'font-size:11px;line-height:1.5;">'
        f'<span style="font-weight:600;">🤖 AI分析:</span>'
        f'{score_html} {esc(summary or "")}'
        f'</div>'
    )


def _build_equipment_tags(equipment: list[str]) -> str:
    if not equipment:
        return ""
    tags = "".join(
        f'<span style="display:inline-block;font-size:11px;padding:2px 6px;'
        f'border-radius:4px;background:#e8f5e9;color:#2e7d32;'
        f'border:1px solid #a5d6a7;margin:1px;">{esc(t)}</span>'
        for t in equipment[:8]
    )
    return (
        '<div style="margin-top:4px;line-height:2;">'
        '<span style="font-size:10px;font-weight:600;color:#555;margin-right:4px;">🏷️ 設備:</span>'
        + tags + "</div>"
    )


def _build_confidence_note(confidence: float, toilet_review_count: int) -> str:
    if confidence >= 0.4 and toilet_review_count >= 3:
        return ""
    return (
        '<div style="margin-top:6px;font-size:10px;line-height:1.5;'
        'padding:6px 8px;border-radius:6px;background:#fff8e1;color:#8d6e63;'
        'border:1px solid #ffe082;">'
        '参考値: トイレ関連レビューが少ないため、スコアは暫定的です。'
        '</div>'
    )


def build_popup_html(t: ToiletDict) -> str:
    """1トイレ地点のポップアップHTMLを構築（コンパクト・スクロール対応）"""
    try:
        color, emoji, label = get_score_style(t["toilet_score"])
        badge = _build_public_badge(t["is_public_toilet"])
        confidence_pct = int(t["confidence"] * 100)
        phone_html = f'<span style="margin-right:6px;"><span aria-label="phone" role="img">📞</span>{esc(t["phone"])}</span>' if t.get("phone") else ""
        equip_html = _build_equipment_tags(t.get("equipment", []))
        kw_html = _build_keyword_tags(t.get("top_keywords", []))
        rev_html = _build_review_html(t.get("sample_reviews", []))
        link_html = _build_link_html(t.get("link", ""))
        confidence_note_html = _build_confidence_note(t.get("confidence", 0), t.get("toilet_review_count", 0))

        review_section = ""
        if rev_html:
            review_section = (
                '<hr style="margin:4px 0;border:none;border-top:1px dashed #ccc;">'
                '<div style="font-size:10px;font-weight:600;margin-bottom:2px;">🚽 口コミ:</div>'
                + rev_html
            )

        title_esc = clean(t['title'])
        addr_esc = clean(t.get('address', ''))
        cat_esc = clean(t.get('category', ''))

        return f"""
        <div style="font-family:'Segoe UI','Hiragino Sans','Noto Sans JP',sans-serif;padding:4px;
            max-width:100%;overflow-wrap:break-word;word-break:break-word;
            max-height:45vh;overflow-y:auto;-webkit-overflow-scrolling:touch;">
          <div style="font-size:14px;font-weight:700;margin-bottom:2px;line-height:1.3;">
            {badge}{title_esc}
          </div>
          <div style="font-size:10px;color:#888;margin-bottom:4px;">{cat_esc}</div>


          <div style="text-align:center;margin:4px 0;">
            <span style="font-size:24px;font-weight:800;color:{color};">{emoji} {t['toilet_score']:.0f}点</span>
            <span style="font-size:11px;color:#888;">（{label}）</span>
          </div>

          <div style="text-align:center;font-size:10px;color:#888;margin-bottom:2px;">
            信頼度 {confidence_pct}% | {t['toilet_review_count']}件
          </div>
          <div style="height:3px;border-radius:2px;background:#e0e0e0;margin-bottom:4px;overflow:hidden;">
            <div style="height:100%;width:{confidence_pct}%;background:{color};border-radius:2px;"></div>
          </div>

          <div style="font-size:10px;color:#555;margin-bottom:1px;">📍 {addr_esc}</div>
          <div style="font-size:10px;color:#555;"><span aria-label="rating" role="img">⭐</span>{t.get('rating', '-')} ({t.get('review_count', 0)}件) {phone_html}</div>
        {confidence_note_html}
          {_build_ai_summary_html(t)}
          {equip_html}
          {kw_html}
          {review_section}
          {link_html}
        </div>
        """
    except Exception as e:
        logger.exception("Popup HTML build failed")
        return f"<div style='padding:8px;color:#c62828;'>{esc(str(e))}</div>"
