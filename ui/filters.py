"""
ui/filters.py
フィルタリング・検索ロジック
app.py から分離
"""
import pandas as pd
from app_config import FILTER_CONFIG


def filter_toilets(df: pd.DataFrame, filter_type: str, prefecture: str = None) -> pd.DataFrame:
    """フィルタタイプに従って DataFrame を絞り込む"""
    if prefecture and prefecture != "全て":
        df = df[df["prefecture"] == prefecture]

    pattern = FILTER_CONFIG.get(filter_type)
    if pattern is None:
        return df
    if pattern == "__public__":
        return df[df["is_public_toilet"] == True]
    return df[df["category"].str.contains(pattern, na=False)]


def search_toilets(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """名前・住所で部分一致検索"""
    if not query:
        return df
    mask = (
        df["title"].str.contains(query, case=False, na=False)
        | df["address"].str.contains(query, case=False, na=False)
    )
    return df[mask]