"""
batch/api_server.py
FastAPI でトイレデータをJSONで提供するREST API
"""
import os
import sys
from collections import Counter

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db_utils import load_json

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "toilets.json.gz")

app = FastAPI(title="Toilet Map API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/toilets")
def list_toilets(
    prefecture: str = Query(None),
    min_score: float = Query(0.0),
    max_score: float = Query(100.0),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
):
    data = load_json(DATA_PATH)
    toilets = data.get("toilets", [])
    if prefecture:
        toilets = [t for t in toilets if t.get("prefecture") == prefecture]
    toilets = [t for t in toilets if min_score <= t.get("toilet_score", 0) <= max_score]
    return {"total": len(toilets), "toilets": toilets[offset:offset + limit]}


@app.get("/api/toilets/{toilet_id}")
def get_toilet(toilet_id: int):
    data = load_json(DATA_PATH)
    toilets = data.get("toilets", [])
    if 0 <= toilet_id < len(toilets):
        return toilets[toilet_id]
    return {"error": "not found"}, 404


@app.get("/api/stats")
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
