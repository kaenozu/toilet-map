"""Filtering helpers for both SQLite queries and legacy DataFrames."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import TypeAlias

import numpy as np
import pandas as pd

from app_config import EQUIPMENT_KEYWORDS, FILTER_CONFIG, PUBLIC_FILTER_VALUE, THRESHOLD

EARTH_RADIUS_KM = 6371.0
_BARRIER_FREE_OR_COLS = ["has_multi", "has_diaper", "has_wheelchair"]
SqlParam: TypeAlias = str | int | float
NormalizedFilters: TypeAlias = tuple[str, str, str, float | None, float | None]


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


def normalize_filters(filters: Mapping[str, object] | None) -> NormalizedFilters:
    """Convert UI filter state to a stable, cache-friendly tuple."""
    values = filters or {}
    prefecture = str(values.get("prefecture") or "全て")
    filter_type = str(values.get("filter_type") or "すべて")
    search_query = str(values.get("search_query") or "").strip()
    user_location = values.get("user_location")
    user_lat: float | None = None
    user_lng: float | None = None
    if isinstance(user_location, (tuple, list)) and len(user_location) >= 2:
        try:
            user_lat = round(float(user_location[0]), 6)
            user_lng = round(float(user_location[1]), 6)
        except (TypeError, ValueError):
            user_lat = None
            user_lng = None
    return prefecture, filter_type, search_query, user_lat, user_lng


def _escape_like(value: str) -> str:
    return value.replace("!", "!!").replace("%", "!%").replace("_", "!_")


def _like_any(column: str, values: list[str]) -> tuple[str, list[SqlParam]]:
    clauses = [f"COALESCE({column}, '') LIKE ? ESCAPE '!' COLLATE NOCASE" for _ in values]
    params: list[SqlParam] = [f"%{_escape_like(value)}%" for value in values]
    return f"({' OR '.join(clauses)})", params


def _equipment_sql(pattern: str) -> tuple[str, list[SqlParam]] | None:
    keyword_group = {
        "__keyword__multi": "multi",
        "__keyword__diaper": "diaper",
        "__keyword__wheelchair": "wheelchair",
    }.get(pattern)
    if keyword_group:
        return _like_any("top_keywords", sorted(EQUIPMENT_KEYWORDS[keyword_group]))
    if pattern == "__keyword__barrier_free":
        terms = sorted(set().union(*EQUIPMENT_KEYWORDS.values()))
        return _like_any("top_keywords", terms)
    return None


def build_where_clause(
    filters: Mapping[str, object] | NormalizedFilters | None,
    bounds: dict | tuple[float, float, float, float] | None = None,
) -> tuple[str, list[SqlParam]]:
    """Build a parameterized SQLite WHERE clause for the current UI state."""
    normalized = filters if isinstance(filters, tuple) else normalize_filters(filters)
    prefecture, filter_type, search_query, _, _ = normalized
    clauses: list[str] = []
    params: list[SqlParam] = []

    if prefecture != "全て":
        clauses.append("prefecture = ?")
        params.append(prefecture)

    pattern = FILTER_CONFIG.get(filter_type)
    if pattern == PUBLIC_FILTER_VALUE:
        clauses.append("COALESCE(is_public_toilet, 0) = 1")
    elif isinstance(pattern, str) and pattern.startswith("__keyword__"):
        equipment_filter = _equipment_sql(pattern)
        if equipment_filter:
            clause, equipment_params = equipment_filter
            clauses.append(clause)
            params.extend(equipment_params)
    elif isinstance(pattern, str) and pattern:
        category_values = [value for value in pattern.split("|") if value]
        if category_values:
            clause, category_params = _like_any("category", category_values)
            clauses.append(clause)
            params.extend(category_params)

    if search_query:
        score_range_match = re.fullmatch(r"(\d{1,3})[\-~](\d{1,3})", search_query)
        if score_range_match:
            low, high = map(int, score_range_match.groups())
            if low > high:
                clauses.append("1 = 0")
            else:
                clauses.append("toilet_score BETWEEN ? AND ?")
                params.extend([low, high])
        else:
            words = [word for word in re.split(r"[\s,、]+", search_query) if word]
            for word in words:
                escaped = f"%{_escape_like(word)}%"
                clauses.append(
                    "(COALESCE(title, '') LIKE ? ESCAPE '!' COLLATE NOCASE "
                    "OR COALESCE(address, '') LIKE ? ESCAPE '!' COLLATE NOCASE "
                    "OR COALESCE(category, '') LIKE ? ESCAPE '!' COLLATE NOCASE)"
                )
                params.extend([escaped, escaped, escaped])

    coordinates: tuple[float, float, float, float] | None
    if isinstance(bounds, tuple) and len(bounds) == 4:
        coordinates = bounds
    else:
        coordinates = _extract_bounds_coordinates(bounds) if isinstance(bounds, dict) else None
    if coordinates:
        sw_lat, sw_lng, ne_lat, ne_lng = coordinates
        clauses.extend(["lat BETWEEN ? AND ?", "lng BETWEEN ? AND ?"])
        params.extend([sw_lat, ne_lat, sw_lng, ne_lng])

    return (f" WHERE {' AND '.join(clauses)}" if clauses else ""), params


def build_list_order_clause(
    sort: str,
    filters: Mapping[str, object] | NormalizedFilters | None,
) -> tuple[str, list[SqlParam]]:
    normalized = filters if isinstance(filters, tuple) else normalize_filters(filters)
    _, _, _, user_lat, user_lng = normalized
    normalized_sort = str(sort or "score").strip().lower()
    near_sort = normalized_sort in {"near", "distance", "距離順"} or "near" in normalized_sort
    if near_sort and user_lat is not None and user_lng is not None:
        return (
            " ORDER BY CASE WHEN lat IS NULL OR lng IS NULL THEN 1 ELSE 0 END ASC, "
            "((lat - ?) * (lat - ?) + (lng - ?) * (lng - ?)) ASC, "
            "COALESCE(toilet_score, 0) DESC, id ASC",
            [user_lat, user_lat, user_lng, user_lng],
        )
    return (
        " ORDER BY COALESCE(toilet_score, 0) DESC, "
        "COALESCE(confidence, 0) DESC, COALESCE(toilet_review_count, 0) DESC, id ASC",
        [],
    )


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
    """Legacy DataFrame filtering retained for external callers and regression tests."""
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
    """Legacy literal AND-search retained for external callers and regression tests."""
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
        sw_lat = float(southwest.get("lat"))
        sw_lng = float(southwest.get("lng"))
        ne_lat = float(northeast.get("lat"))
        ne_lng = float(northeast.get("lng"))
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in (sw_lat, sw_lng, ne_lat, ne_lng)):
        return None
    if sw_lat > ne_lat or sw_lng > ne_lng:
        return None
    return sw_lat, sw_lng, ne_lat, ne_lng


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
