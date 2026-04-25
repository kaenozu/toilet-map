"""
ui/data_loader.py
データ読み込み・キャッシュ・都道府県別統計計算
app.py から分離
"""
import json
import streamlit as st
import pandas as pd
from app_config import DATA_PATH, ERROR_METADATA


@st.cache_data(ttl=3600)
def load_toilet_data():
    """
    toilets.json を読み込み、prefecture 別統計を付与して返す
    Returns: {"metadata": dict, "toilets": list, "pref_stats": dict}
    """
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "toilets" not in data or "metadata" not in data:
            raise ValueError("Invalid data structure")
    except FileNotFoundError:
        st.error(f"データファイルが見つかりません: {DATA_PATH}")
        return {"metadata": ERROR_METADATA, "toilets": [], "pref_stats": {}}
    except json.JSONDecodeError:
        st.error(f"データファイルの形式が不正です: {DATA_PATH}")
        return {"metadata": ERROR_METADATA, "toilets": [], "pref_stats": {}}
    except Exception as e:
        st.error(f"データ読み込みエラー: {e}")
        return {"metadata": ERROR_METADATA, "toilets": [], "pref_stats": {}}

    toilets = data["toilets"]
    pref_stats = {}

    for t in toilets:
        pref = t.get("prefecture", "")
        if not pref:
            continue
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

    data["pref_stats"] = pref_stats
    return data


def toilets_to_dataframe(toilets: list) -> pd.DataFrame:
    """ toilets リストを DataFrame に変換（口コミありのみ）"""
    df = pd.DataFrame(toilets)
    df = df[df["toilet_review_count"] > 0].reset_index(drop=True)
    return df


def get_prefectures(df: pd.DataFrame) -> list[str]:
    """ DataFrame から都道府県リストを生成"""
    if "prefecture" in df.columns:
        return ["全て"] + sorted(df["prefecture"].dropna().unique().tolist())
    return ["全て"]