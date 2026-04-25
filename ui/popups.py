"""
ui/popups.py
Popup HTML builders for toilet map markers
"""
from typing import Optional
from app_config import esc, get_score_style
from .types import ToiletDict


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
        prefix = "👍" if kw.startswith("+") else "👎" if kw.startswith("-") else ""
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
    for r in reviews[:2]:
        txt = r.get("text", "")
        key = txt[:80]
        if key in seen:
            continue
        seen.add(key)
        score_val = r.get("score", 0)
        icon = "👍" if score_val > 0 else "👎" if score_val < 0 else "📝"
        border_color = "#2e7d32" if score_val > 0 else "#c62828" if score_val < 0 else "#bbb"
        name = esc(r.get("name", ""))
        rating = r.get("rating", "")
        meta = f'<span style="color:#999;">{name}</span>'
        if rating:
            meta += f' <span style="color:#f9a825;">★{rating}</span>'
        txt_safe = esc(txt).replace("\n", "<br>")
        parts.append(
            f'<div style="font-size:11px;color:#444;padding:4px 6px;background:#fafafa;'
            f'border-radius:4px;margin-top:3px;border-left:3px solid {border_color};">'
            f"{icon} {meta}<br>"
            f'<span style="line-height:1.5;">{txt_safe[:120]}{"..." if len(txt_safe) > 120 else ""}</span></div>'
        )
    return "".join(parts)


def _build_link_html(link: str) -> str:
    if not link:
        return ""
    return (
        '<div style="margin-top:6px;">'
        f'<a href="{link}" target="_blank" rel="noopener noreferrer" '
        'style="font-size:13px;color:#1a73e8;text-decoration:none;font-weight:600;'
        'display:inline-block;padding:4px 0;">'
        "🗺️ Google Mapsで開く →</a></div>"
    )


def build_popup_html(t: ToiletDict) -> str:
    """1トイレ地点のポップアップHTMLを構築（コンパクト・スクロール対応）"""
    color, emoji, label = get_score_style(t["toilet_score"])
    badge = _build_public_badge(t["is_public_toilet"])
    confidence_pct = int(t["confidence"] * 100)
    phone_html = f'<span style="margin-right:6px;">📞{esc(t["phone"])}</span>' if t.get("phone") else ""
    kw_html = _build_keyword_tags(t.get("top_keywords", []))
    rev_html = _build_review_html(t.get("sample_reviews", []))
    link_html = _build_link_html(t.get("link", ""))

    review_section = ""
    if rev_html:
        review_section = (
            '<hr style="margin:4px 0;border:none;border-top:1px dashed #ccc;">'
            '<div style="font-size:10px;font-weight:600;margin-bottom:2px;">🚽 口コミ:</div>'
            + rev_html
        )

    addr = esc(t.get("address", ""))

    return f"""
    <div style="font-family:'Segoe UI','Hiragino Sans','Noto Sans JP',sans-serif;padding:4px;
        max-width:100%;overflow-wrap:break-word;word-break:break-word;
        max-height:45vh;overflow-y:auto;-webkit-overflow-scrolling:touch;">
      <div style="font-size:14px;font-weight:700;margin-bottom:2px;line-height:1.3;">
        {badge}{esc(t['title'])}
      </div>
      <div style="font-size:10px;color:#888;margin-bottom:4px;">{esc(t['category'])}</div>

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

      <div style="font-size:10px;color:#555;margin-bottom:1px;">📍 {addr}</div>
      <div style="font-size:10px;color:#555;">⭐{t.get('rating', '-')} ({t.get('review_count', 0)}件) {phone_html}</div>
      {kw_html}
      {review_section}
      {link_html}
    </div>
    """