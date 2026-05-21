"""
ui/helpers.py
UI helper functions (esc, safe_href, get_score_style)
Extracted from app_config.py to reduce coupling and keep config clean.
"""
import html
import re
from urllib.parse import urlparse

from app_config import SCORE_RANGES


def esc(text: str | None) -> str:
    """HTMLエスケープ"""
    return html.escape(str(text or ""), quote=True) if text else ""


def safe_href(url: str | None) -> str:
    """安全な外部リンクだけを href に使える文字列に変換する"""
    if not url:
        return ""
    parsed = urlparse(str(url).strip())
    if parsed.scheme not in {"http", "https"}:
        return ""
    if not parsed.netloc:
        return ""
    return html.escape(parsed.geturl(), quote=True)


def _normalize_identity_text(value: object) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def get_toilet_identity_key(toilet: dict[str, object]) -> str:
    """レビュー保存やAI紐付けに使う安定キーを返す。"""
    place_id = str(toilet.get("place_id") or "").strip()
    if place_id:
        return f"place_id:{place_id}"

    data_id = str(toilet.get("data_id") or "").strip()
    if data_id:
        return f"data_id:{data_id}"

    lat = toilet.get("lat")
    lng = toilet.get("lng")
    if lat is not None and lng is not None:
        try:
            return f"coords:{float(lat):.6f},{float(lng):.6f}"
        except (TypeError, ValueError):
            pass

    title = _normalize_identity_text(toilet.get("title"))
    address = _normalize_identity_text(toilet.get("address"))
    return f"title_address:{title}|{address}"


def get_score_style(score: float) -> tuple[str, str, str]:
    """スコアに基づいて (色, 絵文字, ラベル) を返す"""
    for threshold, color, emoji, label in SCORE_RANGES:
        if score >= threshold:
            return color, emoji, label
    return SCORE_RANGES[-1][1:]
