"""
ui/data_loader.py
データ読み込み・キャッシュ・都道府県別統計計算 (SQLite版)
"""
import os
import sqlite3
import json
import streamlit as st
import pandas as pd
from app_config import DB_PATH, ERROR_METADATA


def get_data_cache_token() -> tuple[int, int]:
    """DB更新時にキャッシュを自動無効化するためのトークンを返す。"""
    try:
        stat = os.stat(DB_PATH)
    except FileNotFoundError:
        return 0, 0
    return stat.st_mtime_ns, stat.st_size


@st.cache_data(ttl=3600, max_entries=1, show_spinner="データを読み込み中...")
def load_toilet_data(cache_token: tuple[int, int] | None = None):
    """
    SQLite から全データを読み込み、アプリ用の辞書形式で返す。
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
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

        # 都道府県別の統計を pandas groupby で計算
        pdf = pd.DataFrame(toilets)
        if pdf.empty or "prefecture" not in pdf.columns:
            prefecture_stats = {}
        else:
            valid = pdf[pdf["prefecture"].notna() & (pdf["prefecture"] != "")]
            if valid.empty:
                prefecture_stats = {}
            else:
                grouped = valid.groupby("prefecture").agg(
                    count=("lat", "size"),
                    center_lat=("lat", "mean"),
                    center_lng=("lng", "mean"),
                )
                prefecture_stats = grouped.to_dict("index")

        return {"metadata": metadata, "toilets": toilets, "pref_stats": prefecture_stats}
    except sqlite3.Error as e:
        st.error(f"データベース読み込みエラー: {e}")
        return {"metadata": ERROR_METADATA, "toilets": [], "pref_stats": {}}
    finally:
        if conn is not None:
            conn.close()


def toilets_to_dataframe(toilets: list) -> pd.DataFrame:
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
        for kw, _ in kw_list:
            if kw in targets:
                return True
        return False

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
