"""Persist score observations separately from facility-level aggregates."""

from __future__ import annotations

import json
from typing import Any

from .db_types import DbConnection
from .scoring import DIMENSION_SCORING_VERSION, DimensionScore, ScoreDimension


def store_dimension_observations(
    connection: DbConnection,
    *,
    facility_id: int,
    source_record_id: int,
    dimension_scores: dict[ScoreDimension, DimensionScore],
) -> None:
    for dimension, result in dimension_scores.items():
        if result.score is None:
            continue
        connection.execute(
            """
            INSERT INTO dimension_observations (
              facility_id, source_record_id, dimension, model_version, value,
              confidence, evidence_count, extraction_method, observed_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'keyword', now())
            ON CONFLICT (source_record_id, dimension, model_version) DO UPDATE SET
              facility_id = EXCLUDED.facility_id,
              value = EXCLUDED.value,
              confidence = EXCLUDED.confidence,
              evidence_count = EXCLUDED.evidence_count,
              observed_at = EXCLUDED.observed_at
            """,
            (
                facility_id,
                source_record_id,
                dimension.value,
                DIMENSION_SCORING_VERSION,
                result.score,
                result.confidence,
                result.evidence_count,
            ),
        )
        connection.execute(
            """
            INSERT INTO score_evidence (
              facility_id, source_record_id, dimension, model_version, value,
              reliability_weight, extraction_method, observed_at
            ) VALUES (%s, %s, %s, %s, %s, %s, 'keyword', now())
            ON CONFLICT (source_record_id, dimension, model_version) DO UPDATE SET
              facility_id = EXCLUDED.facility_id,
              value = EXCLUDED.value,
              reliability_weight = EXCLUDED.reliability_weight,
              observed_at = EXCLUDED.observed_at
            """,
            (
                facility_id,
                source_record_id,
                dimension.value,
                DIMENSION_SCORING_VERSION,
                result.score,
                result.confidence,
            ),
        )
    recalculate_facility_scores(connection, facility_id=facility_id)


def recalculate_facility_scores(connection: DbConnection, *, facility_id: int) -> None:
    connection.execute(
        """
        WITH aggregates AS (
          SELECT facility_id,
                 dimension,
                 model_version,
                 CASE
                   WHEN sum(confidence) = 0 THEN avg(value)
                   ELSE sum(value * confidence) / sum(confidence)
                 END AS score,
                 LEAST(1.0, avg(confidence) + ln(1 + count(*)) * 0.1) AS confidence,
                 sum(evidence_count)::INTEGER AS evidence_count,
                 count(DISTINCT source_record_id)::INTEGER AS source_count,
                 max(observed_at) AS last_observed_at,
                 jsonb_build_object(
                   'aggregation', 'confidence_weighted_mean',
                   'observation_count', count(*),
                   'source_count', count(DISTINCT source_record_id)
                 ) AS calculation_basis
            FROM dimension_observations
           WHERE facility_id = %s
           GROUP BY facility_id, dimension, model_version
        )
        INSERT INTO facility_scores (
          facility_id, dimension, model_version, score, confidence, evidence_count,
          source_count, last_observed_at, calculation_basis, calculated_at
        )
        SELECT facility_id, dimension, model_version, score, confidence, evidence_count,
               source_count, last_observed_at, calculation_basis, now()
          FROM aggregates
        ON CONFLICT (facility_id, dimension, model_version) DO UPDATE SET
          score = EXCLUDED.score,
          confidence = EXCLUDED.confidence,
          evidence_count = EXCLUDED.evidence_count,
          source_count = EXCLUDED.source_count,
          last_observed_at = EXCLUDED.last_observed_at,
          calculation_basis = EXCLUDED.calculation_basis,
          calculated_at = now()
        """,
        (facility_id,),
    )


def score_basis(result: DimensionScore) -> dict[str, Any]:
    return {
        "score": result.score,
        "confidence": result.confidence,
        "evidence_count": result.evidence_count,
        "positive_matches": result.positive_matches,
        "negative_matches": result.negative_matches,
    }


def encode_score_basis(result: DimensionScore) -> str:
    return json.dumps(score_basis(result), ensure_ascii=False, sort_keys=True)
