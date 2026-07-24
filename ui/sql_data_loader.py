"""Bounded SQLite queries for the v1 Streamlit map and result list."""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Mapping, Sequence

import streamlit as st

from app_config import DATA_PATH, DB_PATH, ERROR_METADATA
from batch.snapshot_integrity import ensure_snapshot_current

from .filters import (
    NormalizedFilters,
    build_list_order_clause,
    build_where_clause,
    haversine_distance,
    normalize_filters,
)
from .types import ToiletDict

TOILET_COLUMNS = [
    "id",
    "source_id",
    "title",
    "category",
    "address",
    "lat",
    "lng",
    "phone",
    "rating",
    "review_count",
    "link",
    "is_public_toilet",
    "toilet_score",
    "confidence",
    "toilet_review_count",
    "prefecture",
    "sample_reviews_json",
    "top_keywords",
]
MAP_COLUMNS = [
    "id",
    "title",
    "category",
    "address",
    "lat",
    "lng",
    "phone",
    "rating",
    "review_count",
    "link",
    "is_public_toilet",
    "toilet_score",
    "confidence",
    "toilet_review_count",
    "prefecture",
    "sample_reviews_json",
    "top_keywords",
]
_MAP_ORDER_BY = (
    " ORDER BY COALESCE(confidence, 0) DESC, COALESCE(review_count, 0) DESC, "
    "COALESCE(toilet_review_count, 0) DESC, COALESCE(toilet_score, 0) DESC, id ASC"
)


def get_data_cache_token() -> tuple[int, int]:
    try:
        stat = os.stat(DB_PATH)
    except FileNotFoundError:
        return 0, 0
    return stat.st_mtime_ns, stat.st_size


def _normalize_bounds(bounds: object) -> tuple[float, float, float, float] | None:
    if not isinstance(bounds, dict):
        return None
    from .filters import _extract_bounds_coordinates

    return _extract_bounds_coordinates(bounds)


@st.cache_data(ttl=3600, max_entries=4, show_spinner=False)
def _ensure_snapshot_cached(cache_token: tuple[int, int]) -> bool:
    del cache_token
    ensure_snapshot_current(DATA_PATH, DB_PATH)
    return True


def _connect(cache_token: tuple[int, int]) -> sqlite3.Connection:
    _ensure_snapshot_cached(cache_token)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _decode_json(value: object, fallback: list) -> list:
    if isinstance(value, list):
        return value
    try:
        decoded = json.loads(str(value or "[]"))
    except (json.JSONDecodeError, TypeError, ValueError):
        return fallback.copy()
    return decoded if isinstance(decoded, list) else fallback.copy()


def _rows_to_toilets(rows: Sequence[sqlite3.Row | Mapping[str, object]]) -> list[ToiletDict]:
    toilets: list[ToiletDict] = []
    for row in rows:
        item = dict(row)
        item["sample_reviews"] = _decode_json(item.pop("sample_reviews_json", None), [])
        item["top_keywords"] = _decode_json(item.get("top_keywords"), [])
        item["is_public_toilet"] = bool(item.get("is_public_toilet"))
        toilets.append(item)  # type: ignore[arg-type]
    return toilets


def load_map_items(bounds: dict | None, filters: Mapping[str, object], limit: int = 1500) -> list[ToiletDict]:
    """Load only the columns and rows needed for the bounded map result."""
    safe_limit = max(1, min(int(limit), 1500))
    return _load_map_items_cached(
        get_data_cache_token(),
        _normalize_bounds(bounds),
        normalize_filters(filters),
        safe_limit,
    )


@st.cache_data(ttl=3600, max_entries=64, show_spinner=False)
def _load_map_items_cached(
    cache_token: tuple[int, int],
    bounds: tuple[float, float, float, float] | None,
    filters: NormalizedFilters,
    limit: int,
) -> list[ToiletDict]:
    connection: sqlite3.Connection | None = None
    try:
        connection = _connect(cache_token)
        where_sql, params = build_where_clause(filters, bounds)
        coordinate_sql = " AND lat IS NOT NULL AND lng IS NOT NULL" if where_sql else " WHERE lat IS NOT NULL AND lng IS NOT NULL"
        sql = f"SELECT {', '.join(MAP_COLUMNS)} FROM toilets{where_sql}{coordinate_sql}{_MAP_ORDER_BY} LIMIT ?"
        rows = connection.execute(sql, [*params, limit]).fetchall()
        return _rows_to_toilets(rows)
    except (sqlite3.Error, OSError, ValueError) as exc:
        st.error(f"地図データ読み込みエラー: {exc}")
        return []
    finally:
        if connection is not None:
            connection.close()


def load_list_items(
    filters: Mapping[str, object],
    sort: str,
    page: int = 1,
    per_page: int = 20,
) -> list[ToiletDict]:
    """Load one list page using SQL ORDER BY, LIMIT and OFFSET."""
    safe_page = max(1, int(page))
    safe_per_page = max(1, min(int(per_page), 200))
    return _load_list_items_cached(
        get_data_cache_token(),
        normalize_filters(filters),
        str(sort or "score"),
        safe_page,
        safe_per_page,
    )


@st.cache_data(ttl=3600, max_entries=128, show_spinner=False)
def _load_list_items_cached(
    cache_token: tuple[int, int],
    filters: NormalizedFilters,
    sort: str,
    page: int,
    per_page: int,
) -> list[ToiletDict]:
    connection: sqlite3.Connection | None = None
    try:
        connection = _connect(cache_token)
        where_sql, where_params = build_where_clause(filters)
        order_sql, order_params = build_list_order_clause(sort, filters)
        offset = (page - 1) * per_page
        sql = f"SELECT {', '.join(TOILET_COLUMNS)} FROM toilets{where_sql}{order_sql} LIMIT ? OFFSET ?"
        rows = connection.execute(sql, [*where_params, *order_params, per_page, offset]).fetchall()
        toilets = _rows_to_toilets(rows)
        _, _, _, user_lat, user_lng = filters
        normalized_sort = sort.strip().lower()
        near_sort = normalized_sort in {"near", "distance", "距離順"} or "near" in normalized_sort
        if near_sort and user_lat is not None and user_lng is not None:
            for toilet in toilets:
                lat, lng = toilet.get("lat"), toilet.get("lng")
                if lat is not None and lng is not None:
                    toilet["distance"] = float(haversine_distance(user_lat, user_lng, float(lat), float(lng)))
        return toilets
    except (sqlite3.Error, OSError, ValueError) as exc:
        st.error(f"一覧データ読み込みエラー: {exc}")
        return []
    finally:
        if connection is not None:
            connection.close()


def count_items(filters: Mapping[str, object]) -> int:
    """Count matching records without loading them."""
    return _count_items_cached(get_data_cache_token(), normalize_filters(filters))


@st.cache_data(ttl=3600, max_entries=128, show_spinner=False)
def _count_items_cached(cache_token: tuple[int, int], filters: NormalizedFilters) -> int:
    connection: sqlite3.Connection | None = None
    try:
        connection = _connect(cache_token)
        where_sql, params = build_where_clause(filters)
        row = connection.execute(f"SELECT COUNT(*) AS count FROM toilets{where_sql}", params).fetchone()
        return int(row["count"] if row else 0)
    except (sqlite3.Error, OSError, ValueError) as exc:
        st.error(f"件数取得エラー: {exc}")
        return 0
    finally:
        if connection is not None:
            connection.close()


def load_metadata() -> dict:
    return _load_metadata_cached(get_data_cache_token())


@st.cache_data(ttl=3600, max_entries=4, show_spinner=False)
def _load_metadata_cached(cache_token: tuple[int, int]) -> dict:
    connection: sqlite3.Connection | None = None
    try:
        connection = _connect(cache_token)
        rows = connection.execute("SELECT key, value FROM metadata").fetchall()
        metadata = {row["key"]: row["value"] for row in rows}
        for key in ["total", "scored", "public_toilets", "zoom"]:
            if key in metadata:
                metadata[key] = int(metadata[key])
        for key in ["center_lat", "center_lng"]:
            if key in metadata:
                metadata[key] = float(metadata[key])
        return metadata
    except (sqlite3.Error, OSError, ValueError) as exc:
        st.error(f"メタデータ読み込みエラー: {exc}")
        return dict(ERROR_METADATA)
    finally:
        if connection is not None:
            connection.close()


def load_prefectures() -> list[str]:
    return _load_prefectures_cached(get_data_cache_token())


@st.cache_data(ttl=3600, max_entries=4, show_spinner=False)
def _load_prefectures_cached(cache_token: tuple[int, int]) -> list[str]:
    connection: sqlite3.Connection | None = None
    try:
        connection = _connect(cache_token)
        rows = connection.execute(
            "SELECT DISTINCT prefecture FROM toilets "
            "WHERE prefecture IS NOT NULL AND TRIM(prefecture) != '' ORDER BY prefecture"
        ).fetchall()
        return ["全て", *[str(row["prefecture"]) for row in rows]]
    except (sqlite3.Error, OSError, ValueError) as exc:
        st.error(f"都道府県読み込みエラー: {exc}")
        return ["全て"]
    finally:
        if connection is not None:
            connection.close()


def load_prefecture_stats() -> dict[str, dict[str, float | int]]:
    return _load_prefecture_stats_cached(get_data_cache_token())


@st.cache_data(ttl=3600, max_entries=4, show_spinner=False)
def _load_prefecture_stats_cached(cache_token: tuple[int, int]) -> dict[str, dict[str, float | int]]:
    connection: sqlite3.Connection | None = None
    try:
        connection = _connect(cache_token)
        rows = connection.execute(
            "SELECT prefecture, COUNT(*) AS count, AVG(lat) AS center_lat, AVG(lng) AS center_lng "
            "FROM toilets WHERE prefecture IS NOT NULL AND TRIM(prefecture) != '' "
            "AND lat IS NOT NULL AND lng IS NOT NULL GROUP BY prefecture"
        ).fetchall()
        return {
            str(row["prefecture"]): {
                "count": int(row["count"]),
                "center_lat": float(row["center_lat"]),
                "center_lng": float(row["center_lng"]),
            }
            for row in rows
        }
    except (sqlite3.Error, OSError, ValueError) as exc:
        st.error(f"地域統計読み込みエラー: {exc}")
        return {}
    finally:
        if connection is not None:
            connection.close()


def load_data_quality_summary() -> dict[str, object]:
    return _load_data_quality_summary_cached(get_data_cache_token())


@st.cache_data(ttl=3600, max_entries=4, show_spinner=False)
def _load_data_quality_summary_cached(cache_token: tuple[int, int]) -> dict[str, object]:
    connection: sqlite3.Connection | None = None
    try:
        connection = _connect(cache_token)
        missing = connection.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN toilet_score IS NULL THEN 1 ELSE 0 END) AS no_score,
                   SUM(CASE WHEN address IS NULL OR TRIM(address) = '' THEN 1 ELSE 0 END) AS no_address,
                   SUM(CASE WHEN prefecture IS NULL OR TRIM(prefecture) = '' THEN 1 ELSE 0 END) AS no_prefecture,
                   SUM(CASE WHEN COALESCE(toilet_review_count, 0) = 0 THEN 1 ELSE 0 END) AS no_reviews
            FROM toilets
            """
        ).fetchone()
        prefectures = connection.execute(
            "SELECT prefecture, COUNT(*) AS count FROM toilets "
            "WHERE prefecture IS NOT NULL AND TRIM(prefecture) != '' "
            "GROUP BY prefecture ORDER BY count DESC"
        ).fetchall()
        score_bins = connection.execute(
            """
            SELECT CASE WHEN toilet_score >= 100 THEN 9 ELSE CAST(toilet_score / 10 AS INTEGER) END AS bucket,
                   COUNT(*) AS count
            FROM toilets
            WHERE toilet_score IS NOT NULL
            GROUP BY bucket ORDER BY bucket
            """
        ).fetchall()
        missing_stats = (
            {
                key: int(missing[key] or 0)
                for key in ("total", "no_score", "no_address", "no_prefecture", "no_reviews")
            }
            if missing
            else {key: 0 for key in ("total", "no_score", "no_address", "no_prefecture", "no_reviews")}
        )
        return {
            "missing": missing_stats,
            "pref_counts": {str(row["prefecture"]): int(row["count"]) for row in prefectures},
            "score_bins": [
                {
                    "label": f"{int(row['bucket']) * 10}-{100 if int(row['bucket']) == 9 else int(row['bucket']) * 10 + 9}",
                    "count": int(row["count"]),
                }
                for row in score_bins
            ],
        }
    except (sqlite3.Error, OSError, ValueError) as exc:
        st.error(f"データ品質読み込みエラー: {exc}")
        return {"missing": {}, "pref_counts": {}, "score_bins": []}
    finally:
        if connection is not None:
            connection.close()


def clear_query_caches() -> None:
    for cached in (
        _ensure_snapshot_cached,
        _load_map_items_cached,
        _load_list_items_cached,
        _count_items_cached,
        _load_metadata_cached,
        _load_prefectures_cached,
        _load_prefecture_stats_cached,
        _load_data_quality_summary_cached,
    ):
        cached.clear()
