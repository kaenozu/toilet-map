"""
batch/gap_analyzer.py
統計分析・ギャップ検出
本モジュールは test_batch_verification.py からインポートされる。
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from functools import lru_cache
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
from utils import extract_prefecture
from utils import logger

from app_config import THRESHOLD


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PREFECTURE_CITIES_PATH = os.path.join(SCRIPT_DIR, "prefecture_cities.json")
SUMMARY_KEYS = {
    "total",
    "scored",
    "score_avg",
    "prefecture_counts",
    "city_counts",
    "prefecture_city_counts",
}
_CITY_FROM_ADDRESS_RE = re.compile(r"([^\s0-9A-Za-z()（）]+?[市区町村])")


@lru_cache(maxsize=1)
def _load_prefecture_catalog() -> dict[str, list[str]]:
    """都道府県ごとの市区町村一覧を読み込む。"""
    if not os.path.exists(PREFECTURE_CITIES_PATH):
        return {}
    try:
        with open(PREFECTURE_CITIES_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}

    catalog: dict[str, list[str]] = {}
    for prefecture, cities in raw.items():
        if isinstance(cities, list):
            cleaned = [str(city).strip() for city in cities if str(city).strip()]
            if cleaned:
                catalog[str(prefecture).strip()] = cleaned
    return catalog


def _normalize_name(value: Any, default: str = "不明") -> str:
    text = str(value or "").strip()
    return text or default


def _normalize_city_counts(city_counts: dict[Any, Any]) -> dict[str, int]:
    normalized: dict[str, int] = {}
    for city, count in city_counts.items():
        try:
            normalized[str(city)] = int(count)
        except (TypeError, ValueError):
            continue
    return normalized


def _extract_city(address: str, prefecture: str = "") -> str:
    """住所文字列から市区町村を抽出する。"""
    if not address:
        return ""

    fragment = address
    if prefecture and prefecture in fragment:
        fragment = fragment.split(prefecture, 1)[1]

    match = _CITY_FROM_ADDRESS_RE.search(fragment)
    if match:
        return match.group(1)

    catalog = _load_prefecture_catalog()
    candidates = catalog.get(prefecture, []) if prefecture else []
    if not candidates:
        candidates = [city for cities in catalog.values() for city in cities]

    for city in sorted({city for city in candidates if city}, key=len, reverse=True):
        if city in address:
            return city

    return ""


def _coerce_prefecture_city_counts(stats: dict) -> dict[str, dict[str, int]]:
    """find_gaps が扱いやすい形へ統計を正規化する。"""
    nested = stats.get("prefecture_city_counts")
    if isinstance(nested, dict) and nested:
        return {
            str(prefecture): _normalize_city_counts(city_counts)
            for prefecture, city_counts in nested.items()
            if isinstance(city_counts, dict)
        }

    counts: dict[str, dict[str, int]] = {}
    for key, value in stats.items():
        if key in SUMMARY_KEYS:
            continue
        if isinstance(value, dict):
            counts[str(key)] = _normalize_city_counts(value)
    return counts


def get_stats(toilets: list[dict]) -> dict:
    """トイレデータから統計情報を抽出する。"""
    prefecture_counts: Counter[str] = Counter()
    city_counts: Counter[str] = Counter()
    prefecture_city_counts: dict[str, Counter[str]] = {}
    score_sum = 0.0
    scored = 0

    for toilet in toilets:
        address = str(toilet.get("address") or "")
        prefecture = _normalize_name(toilet.get("prefecture") or extract_prefecture(address))
        city = _normalize_name(toilet.get("city") or _extract_city(address, prefecture))
        score = toilet.get("toilet_score")

        prefecture_counts[prefecture] += 1
        city_counts[city] += 1
        prefecture_city_counts.setdefault(prefecture, Counter())[city] += 1

        if score not in (None, ""):
            try:
                score_sum += float(score)
                scored += 1
            except (TypeError, ValueError) as exc:
                logger.warning(f"Skipping invalid toilet_score value: {score!r} ({exc})")

    return {
        "total": len(toilets),
        "scored": scored,
        "score_avg": round(score_sum / scored, 2) if scored else 0,
        "prefecture_counts": dict(prefecture_counts),
        "city_counts": dict(city_counts),
        "prefecture_city_counts": {
            prefecture: dict(city_counter)
            for prefecture, city_counter in prefecture_city_counts.items()
        },
    }


def find_gaps(stats: dict, threshold: int = THRESHOLD, include_catalog: bool = False) -> list[dict]:
    """エリア別のスコアギャップを検出する。"""
    prefecture_city_counts = _coerce_prefecture_city_counts(stats)

    if include_catalog:
        catalog = _load_prefecture_catalog()
        for prefecture, city_list in catalog.items():
            city_counts = prefecture_city_counts.setdefault(prefecture, {})
            for city in city_list:
                city_counts.setdefault(city, 0)

    gaps: list[dict] = []
    for prefecture, city_counts in prefecture_city_counts.items():
        normalized = _normalize_city_counts(city_counts)
        prefecture_total = sum(normalized.values())
        active = prefecture_total > 0

        for city, count in normalized.items():
            if count < threshold:
                gaps.append(
                    {
                        "prefecture": prefecture,
                        "city": city,
                        "count": count,
                        "prefecture_total": prefecture_total,
                        "active": active,
                        "message": f"データ不足: {count}件（閾値 {threshold}）",
                    }
                )

    gaps.sort(
        key=lambda item: (
            0 if item.get("active") else 1,
            -int(item.get("prefecture_total", 0)),
            int(item.get("count", 0)),
            item.get("prefecture", ""),
            item.get("city", ""),
        )
    )
    return gaps
