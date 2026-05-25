"""
ui/filters.py
フィルタリング・検索ロジック
"""

import logging
import math
import re

import numpy as np
import pandas as pd

from app_config import FILTER_CONFIG, PUBLIC_FILTER_VALUE

logger = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371.0

ROMAJI_TO_JAPANESE = {
    "tokyo": "東京",
    "osaka": "大阪",
    "kyoto": "京都",
    "nagoya": "名古屋",
    "sapporo": "札幌",
    "fukuoka": "福岡",
    "yokohama": "横浜",
    "kobe": "神戸",
    "kawasaki": "川崎",
    "sendai": "仙台",
    "hiroshima": "広島",
    "chiba": "千葉",
    "okinawa": "沖縄",
}

ENGLISH_PREFECTURE_NAMES = {
    "hokkaido": "北海道",
    "aomori": "青森県",
    "iwate": "岩手県",
    "miyagi": "宮城県",
    "akita": "秋田県",
    "yamagata": "山形県",
    "fukushima": "福島県",
    "ibaraki": "茨城県",
    "tochigi": "栃木県",
    "gunma": "群馬県",
    "saitama": "埼玉県",
    "chiba": "千葉県",
    "tokyo": "東京都",
    "kanagawa": "神奈川県",
    "niigata": "新潟県",
    "toyama": "富山県",
    "ishikawa": "石川県",
    "fukui": "福井県",
    "yamanashi": "山梨県",
    "nagano": "長野県",
    "gifu": "岐阜県",
    "shizuoka": "静岡県",
    "aichi": "愛知県",
    "mie": "三重県",
    "shiga": "滋賀県",
    "kyoto": "京都府",
    "osaka": "大阪府",
    "hyogo": "兵庫県",
    "nara": "奈良県",
    "wakayama": "和歌山県",
    "tottori": "鳥取県",
    "shimane": "島根県",
    "okayama": "岡山県",
    "hiroshima": "広島県",
    "yamaguchi": "山口県",
    "tokushima": "徳島県",
    "kagawa": "香川県",
    "ehime": "愛媛県",
    "kochi": "高知県",
    "fukuoka": "福岡県",
    "saga": "佐賀県",
    "nagasaki": "長崎県",
    "kumamoto": "熊本県",
    "oita": "大分県",
    "miyazaki": "宮崎県",
    "kagoshima": "鹿児島県",
    "okinawa": "沖縄県",
}


def haversine_distance(lat1: float, lng1: float, lat2: float | pd.Series, lng2: float | pd.Series) -> float | pd.Series:
    """2点間の距離を計算 (km)。lat2, lng2 はスカラーまたはpandas Series"""
    if isinstance(lat2, pd.Series):
        lat1_rad = np.radians(lat1)
        lng1_rad = np.radians(lng1)
        lat2_rad = np.radians(lat2)
        lng2_rad = np.radians(lng2)

        dlat = lat2_rad - lat1_rad
        dlng = lng2_rad - lng1_rad

        a = np.sin(dlat / 2) ** 2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlng / 2) ** 2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
        return EARTH_RADIUS_KM * c
    else:
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return EARTH_RADIUS_KM * c


# barrier_free は多目的・おむつ替え・車椅子のいずれかが true ならマッチ
_BARRIER_FREE_OR_COLS = ["has_multi", "has_diaper", "has_wheelchair"]


def _apply_equipment_filter(df: pd.DataFrame, pattern: str) -> pd.DataFrame:
    """設備フィルタ（__keyword__*）を適用"""
    column_map = {
        "__keyword__multi": "has_multi",
        "__keyword__diaper": "has_diaper",
        "__keyword__wheelchair": "has_wheelchair",
    }
    if pattern == "__keyword__barrier_free":
        cols = [c for c in _BARRIER_FREE_OR_COLS if c in df.columns]
        if cols:
            mask = df[cols[0]]
            for c in cols[1:]:
                mask = mask | df[c]
            return df[mask]
        return df
    col = column_map.get(pattern)
    if col and col in df.columns:
        return df[df[col]]
    return df


def filter_toilets(
    df: pd.DataFrame,
    filter_type: str,
    prefecture: str = "全て",
    user_lat: float | None = None,
    user_lng: float | None = None,
) -> pd.DataFrame:
    """条件に基づいてフィルタリング。現在地があれば距離を計算。"""
    try:
        if prefecture != "全て":
            df = df[df["prefecture"] == prefecture]

        pattern = FILTER_CONFIG.get(filter_type)
        if pattern == PUBLIC_FILTER_VALUE:
            df = df[df["is_public_toilet"]]
        elif pattern and isinstance(pattern, str) and pattern.startswith("__keyword__"):
            df = _apply_equipment_filter(df, pattern)
        elif pattern:
            df = df[df["category"].str.contains(pattern, na=False)]

        if user_lat is not None and user_lng is not None:
            df = df.copy()
            df["distance"] = haversine_distance(user_lat, user_lng, df["lat"], df["lng"])

        return df
    except Exception as e:
        logger.warning("filter_toilets failed: %s", e)
        return df


def search_toilets(df: pd.DataFrame, query: str | None) -> pd.DataFrame:
    """名前・住所・カテゴリで検索（部分単語一致, スコア範囲対応）"""
    if not query:
        return df
    q = query.strip()
    if not q:
        return df

    score_range_match = re.match(r"^(\d{1,3})[\-~](\d{1,3})$", q)
    if score_range_match:
        lo = int(score_range_match.group(1))
        hi = int(score_range_match.group(2))
        return df[(df["toilet_score"] >= lo) & (df["toilet_score"] <= hi)]

    q_lower = q.lower()
    extra_terms = []
    if q_lower in ROMAJI_TO_JAPANESE:
        extra_terms.append(ROMAJI_TO_JAPANESE[q_lower])
    if q_lower in ENGLISH_PREFECTURE_NAMES:
        extra_terms.append(ENGLISH_PREFECTURE_NAMES[q_lower])

    words = [w for w in re.split(r"[\s,、]+", q) if w]
    if extra_terms:
        words.extend(extra_terms)
    if not words:
        return df

    masks = [
        (
            df["title"].str.contains(w, case=False, na=False)
            | df["address"].str.contains(w, case=False, na=False)
            | df["category"].str.contains(w, case=False, na=False)
        )
        for w in words
    ]
    combined = masks[0]
    for m in masks[1:]:
        combined = combined | m
    return df[combined]
