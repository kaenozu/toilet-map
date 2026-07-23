from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from fastapi import FastAPI, Query
from psycopg import Connection, connect
from psycopg.rows import dict_row

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://toilet_map:toilet_map@localhost:5432/toilet_map",
).replace("postgresql+psycopg://", "postgresql://")

app = FastAPI(title="Toilet Map API", version="2.0.0")


@contextmanager
def database() -> Iterator[Connection]:
    with connect(DATABASE_URL, row_factory=dict_row) as connection:
        yield connection


@app.get("/health")
def health() -> dict[str, str]:
    with database() as connection:
        connection.execute("SELECT 1").fetchone()
    return {"status": "ok"}


@app.get("/api/v2/places")
def list_places(
    prefecture: str | None = None,
    q: str | None = Query(None, max_length=200),
    min_score: float | None = Query(None, ge=0, le=100),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    conditions = ["d.status = 'published'"]
    params: list[object] = []
    if prefecture:
        conditions.append("p.prefecture = %s")
        params.append(prefecture)
    if q:
        conditions.append("(p.name ILIKE %s OR p.address ILIKE %s)")
        pattern = f"%{q}%"
        params.extend([pattern, pattern])
    if min_score is not None:
        conditions.append("p.toilet_score >= %s")
        params.append(min_score)

    where_sql = " AND ".join(conditions)
    sql = f"""
        SELECT p.id, p.stable_key, p.name, p.address, p.prefecture, p.category,
               ST_Y(p.location::geometry) AS latitude,
               ST_X(p.location::geometry) AS longitude,
               p.toilet_score, p.confidence, p.review_count, p.attributes,
               d.id AS dataset_version_id, d.published_at
          FROM places p
          JOIN dataset_versions d ON d.id = p.dataset_version_id
         WHERE {where_sql}
         ORDER BY p.toilet_score DESC NULLS LAST, p.id
         LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])
    with database() as connection:
        rows = connection.execute(sql, params).fetchall()
    return {"items": rows, "limit": limit, "offset": offset}


@app.get("/api/v2/stats")
def stats() -> dict:
    with database() as connection:
        row = connection.execute(
            """
            SELECT d.id AS dataset_version_id, d.published_at, d.record_count,
                   count(p.id) FILTER (WHERE p.toilet_score IS NOT NULL) AS scored_count,
                   avg(p.toilet_score) AS average_score
              FROM dataset_versions d
              LEFT JOIN places p ON p.dataset_version_id = d.id
             WHERE d.status = 'published'
             GROUP BY d.id
            """
        ).fetchone()
    return row or {"dataset_version_id": None, "record_count": 0, "scored_count": 0}
