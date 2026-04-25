"""
ui/filters.py
フィルタリング・検索ロジック
app.py から分離
import pandas as pd
import numpy as np
from app_config import FILTER_CONFIG


def haversine_distance(lat1, lon1, lat2, lon2):
    """2点間の距離を計算 (km)"""
    R = 6371  # 地球の半径
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return R * c


def filter_toilets(
    df: pd.DataFrame,
    filter_type: str,
    prefecture: str = "全て",
    user_lat: float = None,
    user_lng: float = None,
) -> pd.DataFrame:
    """条件に基づいてフィルタリング。現在地があれば距離を計算。"""
    if prefecture != "全て":
        df = df[df["prefecture"] == prefecture]

    pattern = FILTER_CONFIG.get(filter_type)
    if pattern == "__public__":
        df = df[df["is_public_toilet"]]
    elif pattern:
        df = df[df["category"].str.contains(pattern, na=False)]

    if user_lat is not None and user_lng is not None:
        df["distance"] = haversine_distance(user_lat, user_lng, df["lat"], df["lng"])

    return df


def search_toilets(df: pd.DataFrame, query: str) -> pd.DataFrame:
...
    """名前・住所で部分一致検索"""
    if not query:
        return df
    mask = (
        df["title"].str.contains(query, case=False, na=False)
        | df["address"].str.contains(query, case=False, na=False)
    )
    return df[mask]