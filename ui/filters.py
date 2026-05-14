"""
ui/filters.py
フィルタリング・検索ロジック
"""
import math
import re
import numpy as np
import pandas as pd
from typing import Optional
from app_config import THRESHOLD
from app_config import FILTER_CONFIG, PUBLIC_FILTER_VALUE

EARTH_RADIUS_KM = 6371.0


def haversine_distance(lat1: float, lng1: float, lat2: float | pd.Series, lng2: float | pd.Series) -> float | pd.Series:
    """2点間の距離を計算 (km)。lat2, lng2 はスカラーまたはpandas Series"""
    if isinstance(lat2, pd.Series):
        lat1_rad = np.radians(lat1)
        lng1_rad = np.radians(lng1)
        lat2_rad = np.radians(lat2)
        lng2_rad = np.radians(lng2)

        dlat = lat2_rad - lat1_rad
        dlng = lng2_rad - lng1_rad

        a = (np.sin(dlat / 2) ** 2 +
             np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlng / 2) ** 2)
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
        return EARTH_RADIUS_KM * c
    else:
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlng / 2) ** 2)
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
    user_lat: Optional[float] = None,
    user_lng: Optional[float] = None,
) -> pd.DataFrame:
    """条件に基づいてフィルタリング。現在地があれば距離を計算。"""
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
        df["distance"] = haversine_distance(user_lat, user_lng, df["lat"], df["lng"])

    return df


def search_toilets(df: pd.DataFrame, query: Optional[str]) -> pd.DataFrame:
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

    words = [w for w in re.split(r"[\s,、]+", q) if w]
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


def filter_by_viewport(df: pd.DataFrame, bounds: dict) -> pd.DataFrame:
    """地図の表示範囲（bounds）に基づいてフィルタリング"""
    if not bounds or not isinstance(bounds, dict):
        return df

    coordinates = _extract_bounds_coordinates(bounds)
    if not coordinates:
        return df

    sw_lat, sw_lng, ne_lat, ne_lng = coordinates
    mask = (
        (df["lat"] >= sw_lat) & (df["lat"] <= ne_lat) &
        (df["lng"] >= sw_lng) & (df["lng"] <= ne_lng)
    )
    return df[mask]


def _extract_bounds_coordinates(bounds: dict) -> tuple[float, float, float, float] | None:
    """Leaflet の bounds から座標を安全に取り出す。"""
    sw = bounds.get("_southWest")
    ne = bounds.get("_northEast")
    if not sw or not ne:
        return None

    try:
        sw_lat = float(sw.get("lat"))
        sw_lng = float(sw.get("lng"))
        ne_lat = float(ne.get("lat"))
        ne_lng = float(ne.get("lng"))
    except (TypeError, ValueError):
        return None

    return sw_lat, sw_lng, ne_lat, ne_lng


def get_underserved_areas_in_viewport(bounds: dict, stats: dict) -> list[dict]:
    """
    表示範囲内の都道府県から不足エリアを特定する。
    複数都道府県が表示範囲内にあれば、中心に近い順に最大5件返す。
    """
    if not bounds:
        return []

    coordinates = _extract_bounds_coordinates(bounds)
    if not coordinates:
        return []

    sw_lat, sw_lng, ne_lat, ne_lng = coordinates
    center_lat = (sw_lat + ne_lat) / 2
    center_lng = (sw_lng + ne_lng) / 2

    from app_config_prefectures import PREFECTURE_CENTERS

    # 表示範囲内にある都道府県を、中心からの距離順にリスト
    visible_prefs = []
    for pref, (plat, plng) in PREFECTURE_CENTERS.items():
        if sw_lat <= plat <= ne_lat and sw_lng <= plng <= ne_lng:
            dist = math.sqrt((plat - center_lat) ** 2 + (plng - center_lng) ** 2)
            visible_prefs.append((dist, pref))

    # 表示範囲内にない場合は最も近い都道府県を使う
    if not visible_prefs:
        for pref, (plat, plng) in PREFECTURE_CENTERS.items():
            dist = math.sqrt((plat - center_lat) ** 2 + (plng - center_lng) ** 2)
            visible_prefs.append((dist, pref))

    visible_prefs.sort()

    MAX_SUGGESTIONS = 5
    underserved = []
    for _, pref in visible_prefs:
        if pref in stats:
            for city, count in stats[pref].items():
                if count < THRESHOLD:
                    underserved.append({"pref": pref, "city": city, "count": count})
                    if len(underserved) >= MAX_SUGGESTIONS:
                        break
        if len(underserved) >= MAX_SUGGESTIONS:
            break

    return underserved[:MAX_SUGGESTIONS]
