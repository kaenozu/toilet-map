"""
ui/helpers.py
UI helper functions (esc, safe_href, get_score_style)
Extracted from app_config.py to reduce coupling and keep config clean.
"""
import html
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


def get_score_style(score: float) -> tuple[str, str, str]:
    """スコアに基づいて (色, 絵文字, ラベル) を返す"""
    for threshold, color, emoji, label in SCORE_RANGES:
        if score >= threshold:
            return color, emoji, label
    return SCORE_RANGES[-1][1:]
