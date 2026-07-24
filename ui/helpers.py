"""
ui/helpers.py
UI helper functions (esc, safe_href, get_score_style)
Extracted from app_config.py to reduce coupling and keep config clean.
"""
import html
import math
from urllib.parse import urlparse

from app_config import EQUIPMENT_KEYWORDS, SCORE_RANGES

UNSCORED_STYLE = ("#6b7280", "○", "未採点 / Unscored")
EQUIPMENT_TAG_LABELS = (
    ("multi", "多目的"),
    ("diaper", "おむつ替え"),
    ("wheelchair", "車椅子対応"),
)


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


def get_equipment_tags(keywords: object) -> list[str]:
    """口コミキーワードから、表示順が安定した設備言及タグを返す。"""
    if not isinstance(keywords, list):
        return []

    normalized: set[str] = set()
    for item in keywords:
        if isinstance(item, str):
            raw_keyword = item
        elif isinstance(item, (list, tuple)) and item:
            raw_keyword = str(item[0])
        else:
            continue
        keyword = raw_keyword.lstrip("+-~").strip()
        if keyword:
            normalized.add(keyword)

    return [
        label
        for group, label in EQUIPMENT_TAG_LABELS
        if normalized.intersection(EQUIPMENT_KEYWORDS[group])
    ]


def coerce_finite_float(value: object) -> float | None:
    """UI表示用の有限数へ変換し、欠損・不正値はNoneにする。"""
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def format_score(value: object) -> str:
    """スコアを整数表示へ整形し、未採点はダッシュで示す。"""
    score = coerce_finite_float(value)
    return f"{score:.0f}" if score is not None else "—"


def get_confidence_percentage(value: object) -> int | None:
    """0〜1の信頼度を0〜100へ変換し、欠損・不正値はNoneにする。"""
    confidence = coerce_finite_float(value)
    if confidence is None:
        return None
    return int(max(0.0, min(confidence, 1.0)) * 100)


def get_score_style(score: object) -> tuple[str, str, str]:
    """スコアに基づいて (色, 絵文字, ラベル) を返す。未採点は中立表示にする。"""
    numeric_score = coerce_finite_float(score)
    if numeric_score is None:
        return UNSCORED_STYLE
    for threshold, color, emoji, label in SCORE_RANGES:
        if numeric_score >= threshold:
            return color, emoji, label
    return SCORE_RANGES[-1][1:]
