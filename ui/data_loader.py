"""SQLite data loading with automatic migration from canonical JSON."""

from __future__ import annotations

import json
import os
import sqlite3

import pandas as pd
import streamlit as st

from app_config import DATA_PATH, DB_PATH, EQUIPMENT_KEYWORDS, ERROR_METADATA
from batch.db_utils import ensure_database_current

from .types import ToiletDict


def get_data_cache_token() -> tuple[int, int]:
    try:
        stat = os.stat(DB_PATH)
    except FileNotFoundError:
        return 0, 0
    return stat.st_mtime_ns, stat.st_size


@st.cache_data(ttl=3600, max_entries=1, show_spinner="データを読み込み中...")
def load_toilet_data(cache_token: tuple[int, int] | None = None) -> dict:
    connection: sqlite3.Connection | None = None
    try:
        if cache_token is not None:
            ensure_database_current(DATA_PATH, DB_PATH)
        connection = sqlite3.connect(DB_PATH)
        dataframe = pd.read_sql("SELECT * FROM toilets", connection)
        metadata_frame = pd.read_sql("SELECT * FROM metadata", connection)
        metadata = dict(zip(metadata_frame["key"], metadata_frame["value"]))
        for key in ["total", "scored", "public_toilets", "zoom"]:
            if key in metadata:
                metadata[key] = int(metadata[key])
        for key in ["center_lat", "center_lng"]:
            if key in metadata:
                metadata[key] = float(metadata[key])

        toilets = dataframe.to_dict("records")
        for toilet in toilets:
            try:
                toilet["sample_reviews"] = json.loads(toilet.get("sample_reviews_json") or "[]")
            except json.JSONDecodeError:
                toilet["sample_reviews"] = []
            try:
                toilet["top_keywords"] = json.loads(toilet.get("top_keywords") or "[]")
            except json.JSONDecodeError:
                toilet["top_keywords"] = []

        prefecture_stats: dict[str, dict] = {}
        for toilet in toilets:
            pref = toilet.get("prefecture")
            lat, lng = toilet.get("lat"), toilet.get("lng")
            if not pref or lat is None or lng is None:
                continue
            stats = prefecture_stats.setdefault(pref, {"count": 0, "lats": [], "lngs": []})
            stats["count"] += 1
            stats["lats"].append(lat)
            stats["lngs"].append(lng)
        for stats in prefecture_stats.values():
            stats["center_lat"] = sum(stats.pop("lats")) / stats["count"]
            stats["center_lng"] = sum(stats.pop("lngs")) / stats["count"]
        return {"metadata": metadata, "toilets": toilets, "pref_stats": prefecture_stats}
    except (sqlite3.Error, OSError, ValueError) as exc:
        st.error(f"データベース読み込みエラー: {exc}")
        return {"metadata": ERROR_METADATA, "toilets": [], "pref_stats": {}}
    finally:
        if connection is not None:
            connection.close()


def toilets_to_dataframe(toilets: list[ToiletDict]) -> pd.DataFrame:
    dataframe = pd.DataFrame(toilets)
    _add_equipment_columns(dataframe)
    return dataframe


def _add_equipment_columns(dataframe: pd.DataFrame) -> None:
    if "top_keywords" not in dataframe.columns:
        for column in ("has_multi", "has_diaper", "has_wheelchair"):
            dataframe[column] = False
        return

    def check_keywords(keywords: object, targets: set[str]) -> bool:
        if not isinstance(keywords, list):
            return False
        return any(isinstance(item, list | tuple) and item and str(item[0]).lstrip("+-~") in targets for item in keywords)

    dataframe["has_multi"] = dataframe["top_keywords"].apply(lambda values: check_keywords(values, EQUIPMENT_KEYWORDS["multi"]))
    dataframe["has_diaper"] = dataframe["top_keywords"].apply(lambda values: check_keywords(values, EQUIPMENT_KEYWORDS["diaper"]))
    dataframe["has_wheelchair"] = dataframe["top_keywords"].apply(lambda values: check_keywords(values, EQUIPMENT_KEYWORDS["wheelchair"]))


def get_prefectures(dataframe: pd.DataFrame) -> list[str]:
    if "prefecture" not in dataframe.columns:
        return ["全て"]
    prefectures = dataframe["prefecture"].dropna().unique().tolist()
    return ["全て", *sorted(pref for pref in prefectures if pref)]
