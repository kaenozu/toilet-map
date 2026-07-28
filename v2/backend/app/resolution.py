"""Facility candidate generation and administrator resolution decisions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .db_types import DbConnection


class ResolutionAction(StrEnum):
    MATCH = "match"
    REJECT = "reject"
    NEW_FACILITY = "new_facility"


@dataclass(frozen=True)
class CandidateMetrics:
    distance_m: float
    name_similarity: float
    address_similarity: float


def candidate_score(metrics: CandidateMetrics, *, max_distance_m: float = 300.0) -> float:
    distance_score = max(0.0, 1.0 - metrics.distance_m / max_distance_m)
    return round(
        max(
            0.0,
            min(
                1.0,
                metrics.name_similarity * 0.45
                + metrics.address_similarity * 0.25
                + distance_score * 0.30,
            ),
        ),
        4,
    )


def generate_match_candidates(
    connection: DbConnection,
    *,
    dataset_version_id: int | None = None,
    source_record_id: int | None = None,
    max_distance_m: float = 300.0,
    minimum_score: float = 0.35,
) -> int:
    """Generate review candidates; this function never merges facilities automatically."""
    row = connection.execute(
        """
        WITH pending AS (
          SELECT sr.id, sr.name, sr.address, sr.location
            FROM source_records sr
            JOIN facility_source_links link ON link.source_record_id = sr.id
           WHERE link.status = 'pending'
             AND sr.record_status = 'active'
             AND sr.location IS NOT NULL
             AND (%s::BIGINT IS NULL OR sr.dataset_version_id = %s)
             AND (%s::BIGINT IS NULL OR sr.id = %s)
        ), scored AS (
          SELECT pending.id AS source_record_id,
                 facility.id AS facility_id,
                 ST_Distance(pending.location, facility.location) AS distance_m,
                 similarity(lower(pending.name), lower(facility.name)) AS name_similarity,
                 CASE
                   WHEN pending.address = '' OR facility.address = '' THEN 0
                   ELSE similarity(lower(pending.address), lower(facility.address))
                 END AS address_similarity
            FROM pending
            JOIN facilities facility
              ON facility.status IN ('active', 'temporarily_closed')
             AND ST_DWithin(pending.location, facility.location, %s)
        ), ranked AS (
          SELECT *,
                 LEAST(1.0, GREATEST(0.0,
                   name_similarity * 0.45
                   + address_similarity * 0.25
                   + GREATEST(0.0, 1.0 - distance_m / %s) * 0.30
                 )) AS candidate_score
            FROM scored
        ), changed AS (
          INSERT INTO facility_match_candidates (
            source_record_id, facility_id, distance_m, name_similarity,
            address_similarity, candidate_score, reason, updated_at
          )
          SELECT source_record_id, facility_id, distance_m, name_similarity,
                 address_similarity, candidate_score,
                 jsonb_build_object(
                   'distance_weight', 0.30,
                   'name_weight', 0.45,
                   'address_weight', 0.25
                 ),
                 now()
            FROM ranked
           WHERE candidate_score >= %s
          ON CONFLICT (source_record_id, facility_id) DO UPDATE SET
            distance_m = EXCLUDED.distance_m,
            name_similarity = EXCLUDED.name_similarity,
            address_similarity = EXCLUDED.address_similarity,
            candidate_score = EXCLUDED.candidate_score,
            reason = EXCLUDED.reason,
            dismissed_at = NULL,
            updated_at = now()
          RETURNING id
        )
        SELECT count(*) AS total FROM changed
        """,
        (
            dataset_version_id,
            dataset_version_id,
            source_record_id,
            source_record_id,
            max_distance_m,
            max_distance_m,
            minimum_score,
        ),
    ).fetchone()
    return int(row["total"] if row else 0)


def _create_facility_from_source(connection: DbConnection, source_record_id: int) -> int:
    row = connection.execute(
        """
        INSERT INTO facilities (
          canonical_key, name, address, prefecture, category, location, attributes,
          last_verified_at
        )
        SELECT source_type::text || ':' || lower(provider) || ':' || external_id,
               CASE WHEN btrim(name) = '' THEN '名称未設定トイレ' ELSE name END,
               address, prefecture, category, location,
               jsonb_build_object('created_from_source_record_id', id),
               COALESCE(observed_at, fetched_at)
          FROM source_records
         WHERE id = %s AND location IS NOT NULL
        ON CONFLICT (canonical_key) DO UPDATE SET
          name = EXCLUDED.name,
          address = EXCLUDED.address,
          prefecture = EXCLUDED.prefecture,
          category = EXCLUDED.category,
          location = EXCLUDED.location,
          updated_at = now()
        RETURNING id
        """,
        (source_record_id,),
    ).fetchone()
    if row is None:
        raise ValueError("source record cannot create a facility")
    return int(row["id"])


def decide_source_record(
    connection: DbConnection,
    *,
    source_record_id: int,
    action: ResolutionAction,
    facility_id: int | None,
    decided_by: str,
    reason: str,
) -> dict[str, Any]:
    source = connection.execute(
        "SELECT id FROM source_records WHERE id = %s FOR UPDATE",
        (source_record_id,),
    ).fetchone()
    if source is None:
        raise LookupError("source record not found")
    if action is ResolutionAction.NEW_FACILITY:
        facility_id = _create_facility_from_source(connection, source_record_id)
    if action is ResolutionAction.MATCH and facility_id is None:
        raise ValueError("facility_id is required for a match decision")
    if action is ResolutionAction.MATCH:
        facility = connection.execute(
            "SELECT id FROM facilities WHERE id = %s AND status <> 'removed'",
            (facility_id,),
        ).fetchone()
        if facility is None:
            raise LookupError("facility not found")

    if action in {ResolutionAction.MATCH, ResolutionAction.NEW_FACILITY}:
        method = "human_match" if action is ResolutionAction.MATCH else "human_new_facility"
        connection.execute(
            """
            UPDATE facility_source_links
               SET facility_id = %s,
                   status = 'matched',
                   match_method = %s,
                   match_score = 1.0,
                   decision_reason = %s,
                   decided_at = now(),
                   decided_by = %s
             WHERE source_record_id = %s
            """,
            (facility_id, method, reason, decided_by, source_record_id),
        )
        connection.execute(
            """
            UPDATE source_records
               SET verification_status = 'human_verified', record_status = 'active'
             WHERE id = %s
            """,
            (source_record_id,),
        )
    else:
        connection.execute(
            """
            UPDATE facility_source_links
               SET facility_id = NULL,
                   status = 'rejected',
                   match_method = 'human_reject',
                   match_score = NULL,
                   decision_reason = %s,
                   decided_at = now(),
                   decided_by = %s
             WHERE source_record_id = %s
            """,
            (reason, decided_by, source_record_id),
        )
        connection.execute(
            """
            UPDATE source_records
               SET verification_status = 'rejected', record_status = 'rejected'
             WHERE id = %s
            """,
            (source_record_id,),
        )

    connection.execute(
        "UPDATE facility_match_candidates SET dismissed_at = now() WHERE source_record_id = %s",
        (source_record_id,),
    )
    return {
        "source_record_id": source_record_id,
        "action": action.value,
        "facility_id": facility_id,
        "reason": reason,
    }


def pending_source_records(connection: DbConnection, *, limit: int = 100) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT sr.id, sr.source_type::text AS source_type, sr.provider, sr.external_id,
               sr.name, sr.address, sr.prefecture, sr.category,
               ST_Y(sr.location::geometry) AS latitude,
               ST_X(sr.location::geometry) AS longitude,
               sr.confidence::float AS confidence,
               sr.verification_status::text AS verification_status,
               sr.fetched_at,
               COALESCE(jsonb_agg(
                 jsonb_build_object(
                   'facility_id', candidate.facility_id,
                   'name', facility.name,
                   'address', facility.address,
                   'distance_m', candidate.distance_m::float,
                   'name_similarity', candidate.name_similarity::float,
                   'address_similarity', candidate.address_similarity::float,
                   'candidate_score', candidate.candidate_score::float
                 ) ORDER BY candidate.candidate_score DESC
               ) FILTER (WHERE candidate.id IS NOT NULL), '[]'::jsonb) AS candidates
          FROM source_records sr
          JOIN facility_source_links link ON link.source_record_id = sr.id AND link.status = 'pending'
          LEFT JOIN facility_match_candidates candidate
            ON candidate.source_record_id = sr.id AND candidate.dismissed_at IS NULL
          LEFT JOIN facilities facility ON facility.id = candidate.facility_id
         GROUP BY sr.id
         ORDER BY sr.fetched_at, sr.id
         LIMIT %s
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def decision_audit_payload(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False, sort_keys=True)
