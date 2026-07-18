# mypy: disable-error-code="no-redef"
"""FastAPI REST API backed by the same SQLite snapshot as Streamlit."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from .db_utils import DB_PATH, JSON_PATH, ensure_database_current
except ImportError:
    from db_utils import DB_PATH, JSON_PATH, ensure_database_current


class ToiletModel(BaseModel):
    id: int
    source_id: str
    title: str = ""
    category: str = ""
    address: str = ""
    lat: float | None = None
    lng: float | None = None
    phone: str = ""
    rating: float | None = None
    review_count: int = 0
    link: str = ""
    is_public_toilet: bool = False
    toilet_score: float = 0.0
    confidence: float = 0.0
    toilet_review_count: int = 0
    prefecture: str = ""
    sample_reviews: list[dict[str, Any]] = Field(default_factory=list)
    top_keywords: list[list[Any]] = Field(default_factory=list)


class ToiletListResponse(BaseModel):
    total: int
    toilets: list[ToiletModel]


class StatsResponse(BaseModel):
    total: int
    scored: int
    avg_score: float
    prefectures: dict[str, int]


class DistributionBucket(BaseModel):
    label: str
    count: int
    pct: float


class DistributionResponse(BaseModel):
    total: int
    distribution: list[DistributionBucket]


app = FastAPI(title="Toilet Map API", version="1.1.0")
app.openapi_tags = [
    {"name": "toilets", "description": "トイレデータの取得"},
    {"name": "stats", "description": "統計情報"},
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://toilet-map.streamlit.app"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@contextmanager
def _connection() -> Iterator[sqlite3.Connection]:
    ensure_database_current(JSON_PATH, DB_PATH)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def _parse_json_list(value: object) -> list:
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(str(value))
    except (TypeError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _row_to_toilet(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["is_public_toilet"] = bool(item.get("is_public_toilet"))
    item["sample_reviews"] = _parse_json_list(item.pop("sample_reviews_json", None))
    item["top_keywords"] = _parse_json_list(item.get("top_keywords"))
    return item


def _search_words(query: str | None) -> list[str]:
    return [word for word in re.split(r"[\s,、]+", (query or "").strip()) if word]


@app.get("/api/toilets", tags=["toilets"], summary="トイレ一覧を取得", response_model=ToiletListResponse)
def list_toilets(
    prefecture: str | None = Query(None),
    min_score: float = Query(0.0, ge=0.0, le=100.0),
    max_score: float = Query(100.0, ge=0.0, le=100.0),
    q: str | None = Query(None, max_length=200),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> ToiletListResponse:
    if min_score > max_score:
        raise HTTPException(status_code=422, detail="min_score must not exceed max_score")

    where = ["toilet_score BETWEEN ? AND ?"]
    params: list[Any] = [min_score, max_score]
    if prefecture:
        where.append("prefecture = ?")
        params.append(prefecture)
    for word in _search_words(q):
        where.append(
            "(title LIKE ? ESCAPE '\\' COLLATE NOCASE "
            "OR address LIKE ? ESCAPE '\\' COLLATE NOCASE "
            "OR category LIKE ? ESCAPE '\\' COLLATE NOCASE)"
        )
        escaped = word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        params.extend([pattern, pattern, pattern])

    where_sql = " AND ".join(where)
    with _connection() as connection:
        total = connection.execute(f"SELECT COUNT(*) FROM toilets WHERE {where_sql}", params).fetchone()[0]
        rows = connection.execute(
            f"SELECT * FROM toilets WHERE {where_sql} ORDER BY toilet_score DESC, id ASC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
    return ToiletListResponse(total=total, toilets=[ToiletModel(**_row_to_toilet(row)) for row in rows])


@app.get("/api/toilets/{toilet_id}", tags=["toilets"], summary="個別トイレを取得", response_model=ToiletModel)
def get_toilet(toilet_id: str) -> ToiletModel:
    with _connection() as connection:
        row = connection.execute("SELECT * FROM toilets WHERE source_id = ?", (toilet_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="not found")
    return ToiletModel(**_row_to_toilet(row))


@app.get("/api/stats", tags=["stats"], summary="全体統計を取得", response_model=StatsResponse)
def stats() -> StatsResponse:
    with _connection() as connection:
        total, scored, average = connection.execute(
            "SELECT COUNT(*), SUM(CASE WHEN confidence > 0 THEN 1 ELSE 0 END), AVG(toilet_score) FROM toilets"
        ).fetchone()
        rows = connection.execute(
            "SELECT COALESCE(NULLIF(prefecture, ''), '不明'), COUNT(*) FROM toilets GROUP BY 1 ORDER BY 2 DESC"
        ).fetchall()
    return StatsResponse(
        total=int(total or 0),
        scored=int(scored or 0),
        avg_score=round(float(average or 0), 1),
        prefectures={str(prefecture): int(count) for prefecture, count in rows},
    )


@app.get("/api/stats/distribution", tags=["stats"], summary="スコア分布を取得", response_model=DistributionResponse)
def score_distribution() -> DistributionResponse:
    buckets = [(80, 101, "80-100"), (65, 80, "65-79"), (50, 65, "50-64"), (35, 50, "35-49"), (0, 35, "0-34")]
    with _connection() as connection:
        total = connection.execute("SELECT COUNT(*) FROM toilets WHERE confidence > 0").fetchone()[0]
        distribution: list[DistributionBucket] = []
        for low, high, label in buckets:
            count = connection.execute(
                "SELECT COUNT(*) FROM toilets WHERE confidence > 0 AND toilet_score >= ? AND toilet_score < ?",
                (low, high),
            ).fetchone()[0]
            distribution.append(
                DistributionBucket(label=label, count=count, pct=round(count / total * 100, 1) if total else 0.0)
            )
    return DistributionResponse(total=total, distribution=distribution)
