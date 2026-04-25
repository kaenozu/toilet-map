"""
ui/data_loader.py
データ読み込み・キャッシュ・都道府県別統計計算 (SQLite版)
"""
import sqlite3
import json
import streamlit as st
import pandas as pd
from app_config import DB_PATH, ERROR_METADATA


@st.cache_data(ttl=3600)
def load_toilet_data():
    """
    SQLite から全データを読み込み、アプリ用の辞書形式で返す。
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        # トイレデータ読み込み
        df = pd.read_sql("SELECT * FROM toilets", conn)
        # メタデータ読み込み
        meta_df = pd.read_sql("SELECT * FROM metadata", conn)
        conn.close()

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
            if "sample_reviews_json" in t:
                t["sample_reviews"] = json.loads(t["sample_reviews_json"])
            else:
                t["sample_reviews"] = []

        # 都道府県別の統計（中心座標など）を動的に計算
        pref_stats = {}
        for t in toilets:
            pref = t.get("prefecture")
            if not pref: continue
            if pref not in pref_stats:
                pref_stats[pref] = {"count": 0, "lats": [], "lngs": []}
            pref_stats[pref]["count"] += 1
            pref_stats[pref]["lats"].append(t["lat"])
            pref_stats[pref]["lngs"].append(t["lng"])

        for pref, s in pref_stats.items():
            s["center_lat"] = sum(s["lats"]) / len(s["lats"])
            s["center_lng"] = sum(s["lngs"]) / len(s["lngs"])
            del s["lats"]
            del s["lngs"]

        return {"metadata": metadata, "toilets": toilets, "pref_stats": pref_stats}
    except Exception as e:
        st.error(f"データベース読み込みエラー: {e}")
        return {"metadata": ERROR_METADATA, "toilets": [], "pref_stats": {}}


def toilets_to_dataframe(toilets: list) -> pd.DataFrame:
    """ toilets リストを DataFrame に変換 """
    return pd.DataFrame(toilets)


def get_prefectures(df: pd.DataFrame) -> list[str]:
    """ DataFrame から都道府県リストを生成 """
    if "prefecture" in df.columns:
        prefs = df["prefecture"].dropna().unique().tolist()
        return ["全て"] + sorted([p for p in prefs if p])
    return ["全て"]
