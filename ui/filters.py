"""Filtering and literal AND-search logic."""

from __future__ import annotations

import math
import re

import numpy as np
import pandas as pd

from app_config import FILTER_CONFIG, PUBLIC_FILTER_VALUE, THRESHOLD

EARTH_RADIUS_KM = 6371.0
_BARRIER_FREE_OR_COLS = ["has_multi", "has_diaper", "has_wheelchair"]


def haversine_distance(lat1: float, lng1: float, lat2: float | pd.Series, lng2: float | pd.Series) -> float | pd.Series:
    if isinstance(lat2, pd.Series):
        lat1_rad, lng1_rad = np.radians(lat1), np.radians(lng1)
        lat2_rad, lng2_rad = np.radians(lat2), np.radians(lng2)
        dlat, dlng = lat2_rad - lat1_rad, lng2_rad - lng1_rad
        a = np.sin(dlat / 2) ** 2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlng / 2) ** 2
        return EARTH_RADIUS_KM * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _apply_equipment_filter(df: pd.DataFrame, pattern: str) -> pd.DataFrame:
    column_map = {
        "__keyword__multi": "has_multi",
        "__keyword__diaper": "has_diaper",
        "__keyword__wheelchair": "has_wheelchair",
    }
    if pattern == "__keyword__barrier_free":
        columns = [column for column in _BARRIER_FREE_OR_COLS if column in df.columns]
        if not columns:
            return df
        mask = df[columns[0]].fillna(False).astype(bool)
        for column in columns[1:]:
            mask |= df[column].fillna(False).astype(bool)
        return df[mask]
    equipment_column = column_map.get(pattern)
    return (
        df[df[equipment_column].fillna(False).astype(bool)]
        if equipment_column and equipment_column in df.columns
        else df
    )


def filter_toilets(
    df: pd.DataFrame,
    filter_type: str,
    prefecture: str = "全て",
    user_lat: float | None = None,
    user_lng: float | None = None,
) -> pd.DataFrame:
    result = df
    if prefecture != "全て":
        result = result[result["prefecture"] == prefecture]
    pattern = FILTER_CONFIG.get(filter_type)
    if pattern == PUBLIC_FILTER_VALUE:
        result = result[result["is_public_toilet"].fillna(False).astype(bool)]
    elif isinstance(pattern, str) and pattern.startswith("__keyword__"):
        result = _apply_equipment_filter(result, pattern)
    elif pattern:
        result = result[result["category"].str.contains(pattern, na=False, regex=True)]
    if user_lat is not None and user_lng is not None:
        result = result.copy()
        result["distance"] = haversine_distance(user_lat, user_lng, result["lat"], result["lng"])
    return result


def _literal_mask(series: pd.Series, word: str) -> pd.Series:
    return series.astype("string").str.contains(word, case=False, na=False, regex=False)


def search_toilets(df: pd.DataFrame, query: str | None) -> pd.DataFrame:
    if not query or not (query := query.strip()):
        return df
    score_range_match = re.fullmatch(r"(\d{1,3})[\-~](\d{1,3})", query)
    if score_range_match:
        low, high = map(int, score_range_match.groups())
        if low > high:
            return df.iloc[0:0]
        return df[(df["toilet_score"] >= low) & (df["toilet_score"] <= high)]

    words = [word for word in re.split(r"[\s,、]+", query) if word]
    if not words:
        return df
    combined = pd.Series(True, index=df.index)
    for word in words:
        word_mask = (
            _literal_mask(df["title"], word)
            | _literal_mask(df["address"], word)
            | _literal_mask(df["category"], word)
        )
        combined &= word_mask
    return df[combined]


def filter_by_viewport(df: pd.DataFrame, bounds: dict) -> pd.DataFrame:
    if not bounds or not isinstance(bounds, dict):
        return df
    coordinates = _extract_bounds_coordinates(bounds)
    if not coordinates:
        return df
    sw_lat, sw_lng, ne_lat, ne_lng = coordinates
    return df[(df["lat"] >= sw_lat) & (df["lat"] <= ne_lat) & (df["lng"] >= sw_lng) & (df["lng"] <= ne_lng)]


def _extract_bounds_coordinates(bounds: dict) -> tuple[float, float, float, float] | None:
    southwest, northeast = bounds.get("_southWest"), bounds.get("_northEast")
    if not southwest or not northeast:
        return None
    try:
        return float(southwest.get("lat")), float(southwest.get("lng")), float(northeast.get("lat")), float(northeast.get("lng"))
    except (TypeError, ValueError):
        return None


def get_underserved_areas_in_viewport(bounds: dict, stats: dict) -> list[dict]:
    if not bounds or not (coordinates := _extract_bounds_coordinates(bounds)):
        return []
    sw_lat, sw_lng, ne_lat, ne_lng = coordinates
    center_lat, center_lng = (sw_lat + ne_lat) / 2, (sw_lng + ne_lng) / 2
    from app_config import PREFECTURE_CENTERS

    visible = [
        (math.hypot(lat - center_lat, lng - center_lng), pref)
        for pref, (lat, lng) in PREFECTURE_CENTERS.items()
        if sw_lat <= lat <= ne_lat and sw_lng <= lng <= ne_lng
    ]
    if not visible:
        visible = [
            (math.hypot(lat - center_lat, lng - center_lng), pref)
            for pref, (lat, lng) in PREFECTURE_CENTERS.items()
        ]
    underserved: list[dict] = []
    for _, pref in sorted(visible):
        for city, count in stats.get(pref, {}).items():
            if count < THRESHOLD:
                underserved.append({"pref": pref, "city": city, "count": count})
                if len(underserved) == 5:
                    return underserved
    return underserved
