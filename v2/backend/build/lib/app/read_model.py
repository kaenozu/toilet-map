"""Public snapshot read-model helpers and trust calculation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class TrustInputs:
    confidence: float | None
    verification_status: str
    fetched_at: datetime
    expires_at: datetime | None = None


def calculate_trust_score(inputs: TrustInputs, *, now: datetime | None = None) -> float:
    current = now or datetime.now(UTC)
    confidence = inputs.confidence if inputs.confidence is not None else 0.4
    verification_factor = {
        "human_verified": 1.0,
        "automatically_verified": 0.9,
        "unverified": 0.65,
        "disputed": 0.2,
        "stale": 0.1,
        "rejected": 0.0,
    }.get(inputs.verification_status, 0.4)
    age_days = max(0, (current - inputs.fetched_at).days)
    if inputs.expires_at is not None and inputs.expires_at <= current:
        freshness_factor = 0.2
    elif age_days >= 365:
        freshness_factor = 0.5
    elif age_days >= 180:
        freshness_factor = 0.7
    else:
        freshness_factor = 1.0
    return round(max(0.0, min(100.0, confidence * verification_factor * freshness_factor * 100)), 2)


@dataclass(frozen=True)
class PublicReadModel:
    table: str
    id_expression: str
    source_record_expression: str
    trust_expression: str
    source_count_expression: str
    verification_expression: str
    last_verified_expression: str


def public_read_model() -> PublicReadModel:
    if os.environ.get("PUBLIC_READ_MODEL", "snapshot").casefold() == "places":
        return PublicReadModel(
            table="places",
            id_expression="p.id",
            source_record_expression="p.source_record_id",
            trust_expression="NULL::float",
            source_count_expression="0",
            verification_expression="'unverified'::text",
            last_verified_expression="NULL::timestamptz",
        )
    return PublicReadModel(
        table="published_place_snapshots",
        id_expression="COALESCE(p.legacy_place_id, p.id)",
        source_record_expression="p.source_record_id",
        trust_expression="p.trust_score::float",
        source_count_expression="p.source_count",
        verification_expression="p.verification_status::text",
        last_verified_expression="p.last_verified_at",
    )
