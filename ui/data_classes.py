"""
ui/data_classes.py
データクラスを定義してapp.pyの複雑さを軽減
"""

from dataclasses import dataclass

import pandas as pd


@dataclass
class PreparedData:
    """データ準備フェーズの結果を保持するクラス"""

    metadata: dict
    dataframe: pd.DataFrame
    prefectures: list
    prefecture_stats: dict
    language_strings: dict
    query_params: dict
    toilets: list[dict]


@dataclass
class RenderConfig:
    """描画フェーズの設定を保持するクラス"""

    selected_pref: str
    sort_order: str
    dark_mode: bool
    selected_tile: str
    compact_mode: bool
    show_heatmap: bool


@dataclass
class SidebarUIState:
    """サイドバーUIの状態を保持するクラス"""

    language_strings: dict
    language_code: str
    selected_pref: str
    filter_type: str
    search_query: str
    sort_order: str
    user_location: tuple[float, float] | None
    gps_enabled: bool
    dark_mode: bool
    selected_tile: str
    translated_to_internal: dict
