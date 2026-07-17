from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from typing import Any

_WHITESPACE = re.compile(r"\s+")


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).strip().lower()
    return _WHITESPACE.sub(" ", text)


def first_present(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None and value != "":
            return value
    return None


def safe_float(value: Any, *, minimum: float | None = None, maximum: float | None = None) -> float | None:
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    if minimum is not None and result < minimum:
        return None
    if maximum is not None and result > maximum:
        return None
    return result


def safe_int(value: Any, *, minimum: int | None = None) -> int | None:
    if value is None or value == "":
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    if minimum is not None and result < minimum:
        return None
    return result


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()
