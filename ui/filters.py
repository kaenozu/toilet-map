"""
ui/filters.py
フィルタリング・検索ロジック
"""
import math
import pandas as pd
from typing import Optional
from app_config import FILTER_CONFIG, PUBLIC_FILTER_VALUE


def haversine_distance(lat1: float, lon1: float, lat2, lon2) -> float | pd.Series:
    """2点間の距離を計算 (km)。lat2, lon2 はスカラーまたはpandas Series"""
    R = 6371.0  # 地球の半径 (km)
    if isinstance(lat2, pd.Series):
        # pandas ベクトル化計算
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        # Series はラグ付きで計算
        lat2_rad = lat2.apply(math.radians)
        lon2_rad = lon2.apply(math.radians)
        
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        sin_dlat_half = dlat.apply(lambda x: math.sin(x / 2))
        sin_dlon_half = dlon.apply(lambda x: math.sin(x / 2))
        
        cos_lat1 = math.cos(lat1_rad)
        cos_lat2 = lat2_rad.apply(math.cos)
        
        a = sin_dlat_half ** 2 + cos_lat1 * cos_lat2 * sin_dlon_half ** 2
        c = 2 * a.apply(lambda x: math.atan2(math.sqrt(x), math.sqrt(1 - x)))
        return R * c
    else:
        # スカラー計算
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c


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
    elif pattern:
        df = df[df["category"].str.contains(pattern, na=False)]

    if user_lat is not None and user_lng is not None:
        df["distance"] = haversine_distance(user_lat, user_lng, df["lat"], df["lng"])

    return df


def search_toilets(df: pd.DataFrame, query: Optional[str]) -> pd.DataFrame:
    """名前・住所で部分一致検索"""
    if not query:
        return df
    mask = (
        df["title"].str.contains(query, case=False, na=False)
        | df["address"].str.contains(query, case=False, na=False)
    )
    return df[mask]