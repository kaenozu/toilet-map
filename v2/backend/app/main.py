from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .db import database
from .importer import import_legacy

app = FastAPI(title="Toilet Map API", version="2.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin
        for origin in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
        if origin
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "")


class ImportRequest(BaseModel):
    path: str = Field(default="/data/toilets.json.gz", min_length=1)
    source: str = Field(default="legacy-json", min_length=1, max_length=100)
    auto_publish: bool = False


class JobRequest(BaseModel):
    kind: str = Field(min_length=1, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)


def require_admin(x_admin_key: Annotated[str | None, Header()] = None) -> None:
    if not ADMIN_API_KEY or x_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin key")


@app.get("/health")
def health() -> dict[str, str]:
    with database() as connection:
        connection.execute("SELECT 1").fetchone()
    return {"status": "ok"}


@app.get("/api/v2/places")
def list_places(
    prefecture: str | None = None,
    category: str | None = None,
    q: str | None = Query(None, max_length=200),
    min_score: float | None = Query(None, ge=0, le=100),
    include_unscored: bool = True,
    north: float | None = Query(None, ge=-90, le=90),
    south: float | None = Query(None, ge=-90, le=90),
    east: float | None = Query(None, ge=-180, le=180),
    west: float | None = Query(None, ge=-180, le=180),
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    conditions = ["d.status = 'published'"]
    params: list[object] = []
    if prefecture:
        conditions.append("p.prefecture = %s")
        params.append(prefecture)
    if category:
        conditions.append("p.category = %s")
        params.append(category)
    if q:
        conditions.append("(p.name ILIKE %s OR p.address ILIKE %s)")
        pattern = f"%{q}%"
        params.extend([pattern, pattern])
    if min_score is not None:
        clause = "p.toilet_score >= %s"
        if include_unscored:
            clause = f"({clause} OR p.toilet_score IS NULL)"
        conditions.append(clause)
        params.append(min_score)
    elif not include_unscored:
        conditions.append("p.toilet_score IS NOT NULL")

    bounds = (north, south, east, west)
    if any(value is not None for value in bounds):
        if not all(value is not None for value in bounds):
            raise HTTPException(status_code=422, detail="north, south, east and west must be supplied together")
        assert north is not None and south is not None and east is not None and west is not None
        if south >= north:
            raise HTTPException(status_code=422, detail="south must be lower than north")
        conditions.append("ST_Intersects(p.location::geometry, ST_MakeEnvelope(%s, %s, %s, %s, 4326))")
        params.extend([west, south, east, north])

    where_sql = " AND ".join(conditions)
    select_sql = f"""
        SELECT p.id, p.facility_id, p.stable_key, p.name, p.address, p.prefecture, p.category,
               ST_Y(p.location::geometry) AS latitude,
               ST_X(p.location::geometry) AS longitude,
               p.toilet_score::float AS toilet_score,
               p.confidence::float AS confidence,
               p.review_count, p.attributes,
               d.id AS dataset_version_id, d.published_at
          FROM places p
          JOIN dataset_versions d ON d.id = p.dataset_version_id
         WHERE {where_sql}
         ORDER BY p.toilet_score DESC NULLS LAST, p.id
         LIMIT %s OFFSET %s
    """
    count_sql = f"""
        SELECT count(*) AS total
          FROM places p
          JOIN dataset_versions d ON d.id = p.dataset_version_id
         WHERE {where_sql}
    """
    with database() as connection:
        count_row = connection.execute(count_sql, params).fetchone()
        total = int(count_row["total"] if count_row else 0)
        rows = connection.execute(select_sql, [*params, limit, offset]).fetchall()
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@app.get("/api/v2/places/{place_id}")
def get_place(place_id: int) -> dict[str, Any]:
    with database() as connection:
        row = connection.execute(
            """
            SELECT p.id, p.facility_id, p.source_record_id, p.stable_key, p.name, p.address,
                   p.prefecture, p.category,
                   ST_Y(p.location::geometry) AS latitude,
                   ST_X(p.location::geometry) AS longitude,
                   p.toilet_score::float AS toilet_score,
                   p.confidence::float AS confidence,
                   p.review_count, p.attributes, d.published_at
              FROM places p
              JOIN dataset_versions d ON d.id = p.dataset_version_id
             WHERE p.id = %s AND d.status = 'published'
            """,
            (place_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="place not found")
        facility_id = row["facility_id"]
        sources = []
        scores = []
        if facility_id is not None:
            sources = connection.execute(
                """
                SELECT sr.id, sr.source_type::text AS source_type, sr.provider, sr.external_id,
                       sr.confidence::float AS confidence,
                       sr.verification_status::text AS verification_status,
                       sr.record_status::text AS record_status, sr.observed_at, sr.fetched_at, sr.expires_at,
                       link.status::text AS link_status, link.match_method, link.match_score::float AS match_score
                  FROM facility_source_links link
                  JOIN source_records sr ON sr.id = link.source_record_id
                 WHERE link.facility_id = %s AND link.status = 'matched'
                 ORDER BY sr.fetched_at DESC, sr.id DESC
                """,
                (facility_id,),
            ).fetchall()
            scores = connection.execute(
                """
                SELECT dimension, score::float AS score, confidence::float AS confidence,
                       evidence_count, model_version, last_observed_at, calculated_at
                  FROM facility_scores
                 WHERE facility_id = %s
                 ORDER BY dimension, calculated_at DESC
                """,
                (facility_id,),
            ).fetchall()
    return {**row, "sources": sources, "dimension_scores": scores}


@app.get("/api/v2/facilities/{facility_id}/provenance")
def facility_provenance(facility_id: int) -> dict[str, Any]:
    with database() as connection:
        facility = connection.execute(
            """
            SELECT id, canonical_key, status::text AS status, name, address, prefecture, category,
                   ST_Y(location::geometry) AS latitude, ST_X(location::geometry) AS longitude,
                   attributes, last_verified_at, created_at, updated_at
              FROM facilities WHERE id = %s
            """,
            (facility_id,),
        ).fetchone()
        if facility is None:
            raise HTTPException(status_code=404, detail="facility not found")
        sources = connection.execute(
            """
            SELECT sr.id, sr.source_type::text AS source_type, sr.provider, sr.external_id,
                   sr.record_status::text AS record_status,
                   sr.verification_status::text AS verification_status,
                   sr.confidence::float AS confidence, sr.observed_at, sr.fetched_at, sr.expires_at,
                   link.status::text AS link_status, link.match_method, link.match_score::float AS match_score,
                   link.decision_reason, link.decided_at, link.decided_by
              FROM facility_source_links link
              JOIN source_records sr ON sr.id = link.source_record_id
             WHERE link.facility_id = %s
             ORDER BY sr.fetched_at DESC, sr.id DESC
            """,
            (facility_id,),
        ).fetchall()
    return {"facility": facility, "sources": sources}


@app.get("/api/v2/stats")
def stats() -> dict[str, Any]:
    with database() as connection:
        row = connection.execute(
            """
            SELECT d.id AS dataset_version_id, d.published_at, d.record_count,
                   count(p.id) FILTER (WHERE p.toilet_score IS NOT NULL) AS scored_count,
                   avg(p.toilet_score)::float AS average_score,
                   count(DISTINCT NULLIF(p.prefecture, '')) AS prefecture_count
              FROM dataset_versions d
              LEFT JOIN places p ON p.dataset_version_id = d.id
             WHERE d.status = 'published'
             GROUP BY d.id
            """
        ).fetchone()
    return row or {
        "dataset_version_id": None,
        "record_count": 0,
        "scored_count": 0,
        "average_score": None,
        "prefecture_count": 0,
    }


@app.get("/api/v2/facets")
def facets() -> dict[str, list[dict[str, Any]]]:
    with database() as connection:
        prefectures = connection.execute(
            """
            SELECT p.prefecture AS value, count(*) AS count
              FROM places p JOIN dataset_versions d ON d.id = p.dataset_version_id
             WHERE d.status = 'published' AND p.prefecture <> ''
             GROUP BY p.prefecture ORDER BY p.prefecture
            """
        ).fetchall()
        categories = connection.execute(
            """
            SELECT p.category AS value, count(*) AS count
              FROM places p JOIN dataset_versions d ON d.id = p.dataset_version_id
             WHERE d.status = 'published' AND p.category <> ''
             GROUP BY p.category ORDER BY count(*) DESC, p.category
            """
        ).fetchall()
    return {"prefectures": prefectures, "categories": categories}


@app.get("/api/v2/admin/data-quality", dependencies=[Depends(require_admin)])
def admin_data_quality() -> dict[str, Any]:
    with database() as connection:
        row = connection.execute(
            """
            SELECT
              (SELECT count(*) FROM facilities) AS facilities,
              (SELECT count(*) FROM source_records WHERE record_status = 'active') AS active_source_records,
              (SELECT count(*) FROM source_records WHERE record_status = 'stale') AS stale_source_records,
              (SELECT count(*) FROM source_records WHERE verification_status = 'disputed') AS disputed_source_records,
              (SELECT count(*) FROM facility_source_links WHERE status = 'pending') AS pending_links,
              (SELECT count(*) FROM facility_source_links WHERE status = 'rejected') AS rejected_links,
              (SELECT count(*) FROM published_place_snapshots snapshot
                JOIN dataset_versions d ON d.id = snapshot.dataset_version_id
               WHERE d.status = 'published') AS published_snapshots
            """
        ).fetchone()
    return row or {}


@app.post("/api/v2/admin/import", dependencies=[Depends(require_admin)])
def admin_import(request: ImportRequest) -> dict[str, Any]:
    dataset_id, count = import_legacy(Path(request.path), source=request.source)
    with database() as connection:
        connection.execute(
            """
            INSERT INTO jobs (kind, payload)
            VALUES ('validate_dataset', jsonb_build_object('dataset_version_id', %s))
            """,
            (dataset_id,),
        )
        if request.auto_publish:
            connection.execute(
                """
                INSERT INTO jobs (kind, payload, available_at)
                VALUES (
                    'publish_dataset',
                    jsonb_build_object('dataset_version_id', %s),
                    now() + interval '2 seconds'
                )
                """,
                (dataset_id,),
            )
        connection.commit()
    return {"dataset_version_id": dataset_id, "record_count": count, "queued_validation": True}


@app.post("/api/v2/admin/jobs", dependencies=[Depends(require_admin)])
def enqueue_job(request: JobRequest) -> dict[str, int]:
    with database() as connection:
        row = connection.execute(
            "INSERT INTO jobs (kind, payload) VALUES (%s, %s::jsonb) RETURNING id",
            (request.kind, json.dumps(request.payload)),
        ).fetchone()
        connection.commit()
    if row is None:
        raise HTTPException(status_code=500, detail="failed to enqueue job")
    return {"job_id": int(row["id"])}
