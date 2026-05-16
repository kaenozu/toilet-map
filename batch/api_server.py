"""
batch/api_server.py
FastAPI でトイレデータをJSONで提供するREST API
"""
import os
import re
from collections import Counter

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from db_utils import load_json

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "toilets.json.gz")

app = FastAPI(title="Toilet Map API", version="1.0.0")
app.openapi_tags = [
    {"name": "toilets", "description": "トイレデータの取得"},
    {"name": "stats", "description": "統計情報"},
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://toilet-map.streamlit.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/toilets", tags=["toilets"], summary="トイレ一覧を取得", response_model=dict)
def list_toilets(
    prefecture: str = Query(None),
    min_score: float = Query(0.0),
    max_score: float = Query(100.0),
    q: str = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
):
    data = load_json(DATA_PATH)
    toilets = data.get("toilets", [])
    if prefecture:
        toilets = [t for t in toilets if t.get("prefecture") == prefecture]
    toilets = [t for t in toilets if min_score <= t.get("toilet_score", 0) <= max_score]
    if q:
        words = [w.lower() for w in re.split(r"[\s,、]+", q.strip()) if w]
        if words:
            filtered = []
            for t in toilets:
                target = (t.get("title", "") + t.get("address", "") + t.get("category", "")).lower()
                if all(w in target for w in words):
                    filtered.append(t)
            toilets = filtered
    return {"total": len(toilets), "toilets": toilets[offset:offset + limit]}


@app.get("/api/toilets/{toilet_id}", tags=["toilets"], summary="個別トイレを取得", response_model=dict)
def get_toilet(toilet_id: int):
    data = load_json(DATA_PATH)
    toilets = data.get("toilets", [])
    if 0 <= toilet_id < len(toilets):
        return toilets[toilet_id]
    return JSONResponse(content={"error": "not found"}, status_code=404)


@app.get("/api/stats", tags=["stats"], summary="全体統計を取得", response_model=dict)
def stats():
    data = load_json(DATA_PATH)
    toilets = data.get("toilets", [])
    pref_counts = Counter(t.get("prefecture", "不明") for t in toilets)
    scores = [t.get("toilet_score", 0) for t in toilets]
    avg_score = sum(scores) / len(scores) if scores else 0
    return {
        "total": len(toilets),
        "scored": sum(1 for s in scores if s > 0),
        "avg_score": round(avg_score, 1),
        "prefectures": dict(pref_counts.most_common()),
    }


@app.get("/api/stats/distribution", tags=["stats"], summary="スコア分布を取得", response_model=dict)
def score_distribution():
    data = load_json(DATA_PATH)
    toilets = data.get("toilets", [])
    scored = [t for t in toilets if t.get("toilet_score", 0) > 0]
    if not scored:
        return {"total": 0, "distribution": []}
    buckets = [
        (80, 101, "80-100"), (65, 80, "65-79"), (50, 65, "50-64"),
        (35, 50, "35-49"), (0, 35, "0-34"),
    ]
    distribution = []
    for lo, hi, label in buckets:
        count = sum(1 for t in scored if lo <= t["toilet_score"] < hi)
        distribution.append({"label": label, "count": count, "pct": round(count / len(scored) * 100, 1)})
    return {"total": len(scored), "distribution": distribution}
