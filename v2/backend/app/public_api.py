"""Public FastAPI routes backed by immutable published snapshots."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .db import database
from .read_model import public_read_model
from .reports import DuplicateReportError, ReportPayload, ReportType, create_report

router = APIRouter()


class FacilityReportRequest(BaseModel):
    report_type: ReportType
    note: str = Field(default="", max_length=1000)
    occurred_at: datetime | None = None


def _boolean_attribute(conditions: list[str], key: str, value: bool | None, params: list[object]) -> None:
    if value is None:
        return
    truthy = "lower(COALESCE(p.attributes->>%s, '')) IN ('yes', 'true', 'designated', '1')"
    conditions.append(truthy if value else f"NOT ({truthy})")
    params.append(key)


@router.get("/health")
def health() -> dict[str, str]:
    with database() as connection:
        connection.execute("SELECT 1").fetchone()
    return {"status": "ok"}


@router.get("/api/v2/places")
def list_places(
    prefecture: str | None = None,
    category: str | None = None,
    q: str | None = Query(None, max_length=200),
    min_score: float | None = Query(None, ge=0, le=100),
    min_trust: float | None = Query(None, ge=0, le=100),
    include_unscored: bool = True,
    wheelchair: bool | None = None,
    changing_table: bool | None = None,
    fee: bool | None = None,
    open_24h: bool | None = None,
    north: float | None = Query(None, ge=-90, le=90),
    south: float | None = Query(None, ge=-90, le=90),
    east: float | None = Query(None, ge=-180, le=180),
    west: float | None = Query(None, ge=-180, le=180),
    latitude: float | None = Query(None, ge=-90, le=90),
    longitude: float | None = Query(None, ge=-180, le=180),
    radius_m: int = Query(5000, ge=100, le=50000),
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    model = public_read_model()
    conditions: list[str] = ["d.status = 'published'", "f.status = 'active'"]
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
    if min_trust is not None and model.table == "published_place_snapshots":
        conditions.append("p.trust_score >= %s")
        params.append(min_trust)

    _boolean_attribute(conditions, "wheelchair", wheelchair, params)
    _boolean_attribute(conditions, "changing_table", changing_table, params)
    if fee is not None:
        conditions.append(
            "lower(COALESCE(p.attributes->>'fee', 'no')) IN ('yes', 'true', '1')"
            if fee
            else "lower(COALESCE(p.attributes->>'fee', 'no')) NOT IN ('yes', 'true', '1')"
        )
    if open_24h is not None:
        conditions.append(
            "COALESCE(p.attributes->>'opening_hours', '') = '24/7'"
            if open_24h
            else "COALESCE(p.attributes->>'opening_hours', '') <> '24/7'"
        )

    bounds = (north, south, east, west)
    if any(value is not None for value in bounds):
        if not all(value is not None for value in bounds):
            raise HTTPException(status_code=422, detail="north, south, east and west must be supplied together")
        assert north is not None and south is not None and east is not None and west is not None
        if south >= north:
            raise HTTPException(status_code=422, detail="south must be lower than north")
        conditions.append("ST_Intersects(p.location::geometry, ST_MakeEnvelope(%s, %s, %s, %s, 4326))")
        params.extend([west, south, east, north])

    distance_sql = "NULL::float"
    order_sql = "p.toilet_score DESC NULLS LAST, p.id"
    if latitude is not None or longitude is not None:
        if latitude is None or longitude is None:
            raise HTTPException(status_code=422, detail="latitude and longitude must be supplied together")
        point_sql = "ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography"
        conditions.append(f"ST_DWithin(p.location, {point_sql}, %s)")
        params.extend([longitude, latitude, radius_m])
        distance_sql = f"ST_Distance(p.location, {point_sql})::float"
        order_sql = "distance_m, p.toilet_score DESC NULLS LAST, p.id"
        distance_params: list[object] = [longitude, latitude]
    else:
        distance_params = []

    where_sql = " AND ".join(conditions)
    select_sql = f"""
        SELECT {model.id_expression} AS id, p.facility_id,
               {model.source_record_expression} AS source_record_id,
               p.stable_key, p.name, p.address, p.prefecture, p.category,
               ST_Y(p.location::geometry) AS latitude,
               ST_X(p.location::geometry) AS longitude,
               p.toilet_score::float AS toilet_score,
               p.confidence::float AS confidence,
               p.review_count, p.attributes,
               {model.trust_expression} AS trust_score,
               {model.source_count_expression} AS source_count,
               {model.verification_expression} AS verification_status,
               {model.last_verified_expression} AS last_verified_at,
               {distance_sql} AS distance_m,
               d.id AS dataset_version_id, d.published_at
          FROM {model.table} p
          JOIN dataset_versions d ON d.id = p.dataset_version_id
          JOIN facilities f ON f.id = p.facility_id
         WHERE {where_sql}
         ORDER BY {order_sql}
         LIMIT %s OFFSET %s
    """
    count_sql = f"""
        SELECT count(*) AS total
          FROM {model.table} p
          JOIN dataset_versions d ON d.id = p.dataset_version_id
          JOIN facilities f ON f.id = p.facility_id
         WHERE {where_sql}
    """
    with database() as connection:
        count_row = connection.execute(count_sql, params).fetchone()
        total = int(count_row["total"] if count_row else 0)
        rows = connection.execute(select_sql, [*distance_params, *params, limit, offset]).fetchall()
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@router.get("/api/v2/places/{place_id}")
def get_place(place_id: int) -> dict[str, Any]:
    model = public_read_model()
    id_condition = "p.id = %s" if model.table == "places" else "COALESCE(p.legacy_place_id, p.id) = %s"
    with database() as connection:
        row = connection.execute(
            f"""
            SELECT {model.id_expression} AS id, p.facility_id,
                   {model.source_record_expression} AS source_record_id,
                   p.stable_key, p.name, p.address, p.prefecture, p.category,
                   ST_Y(p.location::geometry) AS latitude,
                   ST_X(p.location::geometry) AS longitude,
                   p.toilet_score::float AS toilet_score,
                   p.confidence::float AS confidence,
                   p.review_count, p.attributes,
                   {model.trust_expression} AS trust_score,
                   {model.source_count_expression} AS source_count,
                   {model.verification_expression} AS verification_status,
                   {model.last_verified_expression} AS last_verified_at,
                   d.published_at
              FROM {model.table} p
              JOIN dataset_versions d ON d.id = p.dataset_version_id
              JOIN facilities f ON f.id = p.facility_id
             WHERE {id_condition} AND d.status = 'published' AND f.status = 'active'
            """,
            (place_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="place not found")
        facility_id = row["facility_id"]
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
                   evidence_count, source_count, model_version, last_observed_at,
                   calculation_basis, calculated_at
              FROM facility_scores
             WHERE facility_id = %s
             ORDER BY dimension, calculated_at DESC
            """,
            (facility_id,),
        ).fetchall()
    return {**row, "sources": sources, "dimension_scores": scores}


@router.get("/api/v2/facilities/{facility_id}/provenance")
def facility_provenance(facility_id: int) -> dict[str, Any]:
    with database() as connection:
        facility = connection.execute(
            """
            SELECT id, canonical_key, status::text AS status, merged_into_id, name, address,
                   prefecture, category, ST_Y(location::geometry) AS latitude,
                   ST_X(location::geometry) AS longitude, attributes, last_verified_at,
                   created_at, updated_at
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


@router.get("/api/v2/stats")
def stats() -> dict[str, Any]:
    model = public_read_model()
    with database() as connection:
        row = connection.execute(
            f"""
            SELECT d.id AS dataset_version_id, d.published_at, count(p.id) AS record_count,
                   count(p.id) FILTER (WHERE p.toilet_score IS NOT NULL) AS scored_count,
                   avg(p.toilet_score)::float AS average_score,
                   count(DISTINCT NULLIF(p.prefecture, '')) AS prefecture_count
              FROM dataset_versions d
              LEFT JOIN {model.table} p
                ON p.dataset_version_id = d.id
               AND EXISTS (
                 SELECT 1 FROM facilities active_facility
                  WHERE active_facility.id = p.facility_id
                    AND active_facility.status = 'active'
               )
             WHERE d.status = 'published'
             GROUP BY d.id
            """
        ).fetchone()
    return row or {"dataset_version_id": None, "record_count": 0, "scored_count": 0, "average_score": None}


@router.get("/api/v2/facets")
def facets() -> dict[str, list[dict[str, Any]]]:
    model = public_read_model()
    with database() as connection:
        prefectures = connection.execute(
            f"""SELECT p.prefecture AS value, count(*) AS count FROM {model.table} p
                JOIN dataset_versions d ON d.id = p.dataset_version_id
                JOIN facilities f ON f.id = p.facility_id
                WHERE d.status = 'published' AND f.status = 'active' AND p.prefecture <> ''
                GROUP BY p.prefecture ORDER BY p.prefecture"""
        ).fetchall()
        categories = connection.execute(
            f"""SELECT p.category AS value, count(*) AS count FROM {model.table} p
                JOIN dataset_versions d ON d.id = p.dataset_version_id
                JOIN facilities f ON f.id = p.facility_id
                WHERE d.status = 'published' AND f.status = 'active' AND p.category <> ''
                GROUP BY p.category ORDER BY count(*) DESC, p.category"""
        ).fetchall()
    return {"prefectures": prefectures, "categories": categories}


@router.post("/api/v2/facilities/{facility_id}/reports", status_code=201)
def submit_facility_report(facility_id: int, request: FacilityReportRequest) -> dict[str, object]:
    try:
        with database() as connection:
            result = create_report(
                connection,
                facility_id=facility_id,
                payload=ReportPayload(request.report_type, request.note, request.occurred_at),
            )
            connection.commit()
        return result
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DuplicateReportError as exc:
        raise HTTPException(status_code=409, detail="同じ内容の報告はすでに受け付けています") from exc
