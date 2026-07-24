"""
ui/popups.py
Popup HTML builders for toilet map markers
"""
import math

from app_config import MAX_SAMPLE_REVIEWS, REVIEW_TEXT_MAX_LENGTH

from .helpers import esc, format_score, get_confidence_percentage, get_score_style, safe_href
from .types import ToiletDict


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


def _format_rating(value: object) -> str:
    try:
        rating = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ""
    if not math.isfinite(rating) or rating <= 0:
        return ""
    return f"{rating:g}"


def _build_score_rationale_html(t: ToiletDict) -> str:
    """初期表示は短く保ち、算出方法・語句・口コミ例を折りたたんで示す。"""
    review_count = max(0, int(t.get("toilet_review_count", 0) or 0))
    rating = _format_rating(t.get("rating"))
    keywords_html = _build_keyword_tags(t.get("top_keywords", []))
    reviews_html = _build_review_html(t.get("sample_reviews", []))

    if format_score(t.get("toilet_score")) == "—":
        basis = "採点結果なし"
        method = "採点に必要な口コミ・星評価が不足しているため、現在は未採点です。"
    elif review_count > 0:
        basis = f"トイレ関連口コミ {review_count}件"
        if rating:
            basis += f" + 施設評価 ★{rating}"
        method = (
            "トイレに言及した口コミの語句傾向を主軸に、"
            "施設全体の星評価で補正して0〜100点に換算しています。"
        )
    elif rating:
        basis = f"施設評価 ★{rating}（トイレ関連口コミなし）"
        method = "トイレ関連口コミがないため、施設全体の星評価のみから低信頼度の参考値を算出しています。"
    else:
        basis = "根拠となる口コミ・星評価なし"
        method = "根拠データがないため、中立値50点を表示しています。"

    evidence_parts = [
        '<div style="font-size:10px;line-height:1.5;color:#666;margin:5px 0;">'
        f"{method}</div>"
    ]
    if keywords_html:
        evidence_parts.append('<div style="font-size:10px;font-weight:600;margin-top:4px;">検出した語句</div>')
        evidence_parts.append(keywords_html)
    if reviews_html:
        evidence_parts.append('<div style="font-size:10px;font-weight:600;margin-top:5px;">判定に使った口コミ例</div>')
        evidence_parts.append(reviews_html)

    summary = "算出方法と口コミを見る" if keywords_html or reviews_html else "算出方法を見る"
    return (
        '<div style="font-size:10px;color:#555;margin:4px 0;">'
        f'<strong>スコア根拠:</strong> {basis}</div>'
        '<details style="font-size:10px;margin:2px 0 5px;">'
        f'<summary style="cursor:pointer;color:#1a73e8;font-weight:600;">{summary}</summary>'
        + "".join(evidence_parts)
        + "</details>"
    )


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


def _build_confidence_note(confidence_pct: int | None, toilet_review_count: int) -> str:
    if confidence_pct is not None and confidence_pct >= 40 and toilet_review_count >= 3:
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
    score_text = format_score(t.get("toilet_score"))
    score_display = f"{score_text}点" if score_text != "—" else score_text
    color, emoji, label = get_score_style(t.get("toilet_score"))
    badge = _build_public_badge(t.get("is_public_toilet", False))
    confidence_pct = get_confidence_percentage(t.get("confidence"))
    confidence_text = f"{confidence_pct}%" if confidence_pct is not None else "—"
    confidence_bar_width = confidence_pct or 0
    toilet_review_count = max(0, int(t.get("toilet_review_count", 0) or 0))
    rating_text = t["rating"] if t.get("rating") is not None else "-"
    phone_html = f'<span style="margin-right:6px;"><span aria-label="phone" role="img">📞</span>{esc(t["phone"])}</span>' if t.get("phone") else ""
    score_rationale_html = _build_score_rationale_html(t)
    link_html = _build_link_html(t.get("link", ""))
    confidence_note_html = _build_confidence_note(confidence_pct, toilet_review_count)

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
        <span style="font-size:24px;font-weight:800;color:{color};">{emoji} {score_display}</span>
        <span style="font-size:11px;color:#888;">（{label}）</span>
      </div>

      <div style="text-align:center;font-size:10px;color:#888;margin-bottom:2px;">
        信頼度 {confidence_text} | {toilet_review_count}件
      </div>
      <div style="height:3px;border-radius:2px;background:#e0e0e0;margin-bottom:4px;overflow:hidden;">
        <div style="height:100%;width:{confidence_bar_width}%;background:{color};border-radius:2px;"></div>
      </div>

      <div style="font-size:10px;color:#555;margin-bottom:1px;">📍 {addr_esc}</div>
      <div style="font-size:10px;color:#555;"><span aria-label="rating" role="img">⭐</span>{rating_text} ({t.get('review_count', 0)}件) {phone_html}</div>
      {score_rationale_html}
      {confidence_note_html}
      {link_html}
    </div>
    """
