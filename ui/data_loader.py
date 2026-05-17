"""
ui/data_loader.py
データ読み込み・キャッシュ・都道府県別統計計算 (SQLite版)
"""
import json
import logging
import math
import os
import sqlite3

import pandas as pd
import streamlit as st

from app_config import DB_PATH, ERROR_METADATA

from .types import ToiletDict

logger = logging.getLogger(__name__)


def get_toilets_fast() -> list[dict]:
    """Lightweight toilet loader using sqlite3 row_factory (no pandas)."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM toilets")
    return [dict(row) for row in cursor.fetchall()]


def get_data_cache_token() -> tuple[int, int]:
    """DB更新時にキャッシュを自動無効化するためのトークンを返す。"""
    try:
        stat = os.stat(DB_PATH)
    except FileNotFoundError:
        return 0, 0
    return stat.st_mtime_ns, stat.st_size


@st.cache_resource
def get_db_connection() -> sqlite3.Connection:
    """SQLite接続をキャッシュして返す（@st.cache_resource で管理）。"""
    return sqlite3.connect(DB_PATH)


@st.cache_data(ttl=3600, max_entries=1, show_spinner="データを読み込み中...")
def load_toilet_data(cache_token: tuple[int, int] | None = None) -> dict:
    """SQLite から全データを読み込み、アプリ用の辞書形式で返す。"""
    try:
        conn = get_db_connection()
        # トイレデータ読み込み
        df = pd.read_sql("SELECT * FROM toilets", conn)
        # メタデータ読み込み
        meta_df = pd.read_sql("SELECT * FROM metadata", conn)

        # メタデータを辞書に変換
        metadata = dict(zip(meta_df["key"], meta_df["value"]))

        # 型変換 (SQLite は文字列で保存されているため)
        for k in ["total", "scored", "public_toilets", "zoom"]:
            if k in metadata:
                metadata[k] = int(metadata[k])
        for k in ["center_lat", "center_lng"]:
            if k in metadata:
                metadata[k] = float(metadata[k])

        # JSON 文字列をパースしてリストに戻す
        toilets = df.to_dict("records")
        for t in toilets:
            sample_reviews_json = t.get("sample_reviews_json")
            if sample_reviews_json in (None, ""):
                t["sample_reviews"] = []
            else:
                try:
                    t["sample_reviews"] = json.loads(sample_reviews_json)
                except json.JSONDecodeError:
                    st.warning("sample_reviews_json の解析に失敗したため空配列で読み込みました。")
                    t["sample_reviews"] = []

            # top_keywords のデシリアライズ（JSON文字列→リスト）
            tk_json = t.get("top_keywords")
            if isinstance(tk_json, str):
                try:
                    t["top_keywords"] = json.loads(tk_json)
                except json.JSONDecodeError:
                    t["top_keywords"] = []

        # 都道府県別の統計（中心座標など）を動的に計算
        pref_stats = {}
        for t in toilets:
            pref = t.get("prefecture")
            if not pref or (isinstance(pref, float) and math.isnan(pref)):
                continue
            if pref not in pref_stats:
                pref_stats[pref] = {"count": 0, "lat_sum": 0.0, "lng_sum": 0.0}
            pref_stats[pref]["count"] += 1
            pref_stats[pref]["lat_sum"] += t["lat"] or 0
            pref_stats[pref]["lng_sum"] += t["lng"] or 0

        for data in pref_stats.values():
            c = data.pop("count")
            data["center_lat"] = data.pop("lat_sum") / c if c else 0
            data["center_lng"] = data.pop("lng_sum") / c if c else 0

        return {"metadata": metadata, "toilets": toilets, "pref_stats": pref_stats}
    except sqlite3.Error as e:
        st.error(f"データベース読み込みエラー: {e}。ページを更新して再試行してください。")
        logger.exception("データベース読み込みエラー")
        st.session_state["_data_error"] = True
        return {"metadata": ERROR_METADATA, "toilets": [], "pref_stats": {}}


def toilets_to_dataframe(toilets: list[ToiletDict]) -> pd.DataFrame:
    """ toilets リストを DataFrame に変換（設備フラグカラムを追加）"""
    df = pd.DataFrame(toilets)
    _add_equipment_columns(df)
    return df


def _add_equipment_columns(df: pd.DataFrame) -> None:
    """top_keywords から設備フラグカラム (has_multi, has_diaper, has_wheelchair) を追加"""
    from app_config import EQUIPMENT_KEYWORDS
    if "top_keywords" not in df.columns:
        df["has_multi"] = False
        df["has_diaper"] = False
        df["has_wheelchair"] = False
        return

    def _check_keywords(kw_list, targets):
        if not kw_list or not isinstance(kw_list, list):
            return False
        return any(kw in targets for kw, _ in kw_list)

    df["has_multi"] = df["top_keywords"].apply(
        lambda kws: _check_keywords(kws, EQUIPMENT_KEYWORDS["multi"])
    )
    df["has_diaper"] = df["top_keywords"].apply(
        lambda kws: _check_keywords(kws, EQUIPMENT_KEYWORDS["diaper"])
    )
    df["has_wheelchair"] = df["top_keywords"].apply(
        lambda kws: _check_keywords(kws, EQUIPMENT_KEYWORDS["wheelchair"])
    )


def get_prefectures(df: pd.DataFrame) -> list[str]:
    """ DataFrame から都道府県リストを生成 """
    if "prefecture" in df.columns:
        prefs = df["prefecture"].dropna().unique().tolist()
        return ["全て"] + sorted([p for p in prefs if p])
    return ["全て"]


def render_data_retry() -> None:
    """データ読み込みエラー時に再試行ボタンを表示する。app.py から呼び出し可能。"""
    if st.session_state.get("_data_error") and st.button("🔄 データを再読み込み", key="retry_db_load", use_container_width=True):
        load_toilet_data.clear()
        st.session_state.pop("_data_error", None)
        st.rerun()
