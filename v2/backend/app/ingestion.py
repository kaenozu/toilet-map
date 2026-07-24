"""Persist normalized provider observations without implicit facility merging."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from psycopg import Connection

from .providers import FetchRequest, NormalizedObservation, SourceProvider
from .resolution import generate_match_candidates


@dataclass(frozen=True)
class IngestionResult:
    discovered: int
    normalized: int
    inserted: int
    reused: int
    pending: int
    candidates: int


def observation_hash(observation: NormalizedObservation) -> str:
    payload = observation.payload or {
        "provider": observation.provider,
        "external_id": observation.external_id,
        "name": observation.name,
        "latitude": observation.latitude,
        "longitude": observation.longitude,
        "address": observation.address,
        "attributes": observation.attributes,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _insert_source_record(
    connection: Connection,
    *,
    provider: SourceProvider,
    observation: NormalizedObservation,
) -> tuple[int, bool]:
    provenance = provider.provenance()
    content_hash = observation_hash(observation)
    row = connection.execute(
        """
        INSERT INTO source_records (
          dataset_version_id, source_type, provider, external_id, name, address, prefecture,
          category, location, confidence, verification_status, observed_at, expires_at,
          raw_payload, content_hash
        ) VALUES (
          NULL, %s, %s, %s, %s, %s, %s, %s,
          ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
          %s, %s, %s, %s, %s::jsonb, %s
        )
        ON CONFLICT (provider, external_id, content_hash) WHERE dataset_version_id IS NULL
        DO NOTHING
        RETURNING id
        """,
        (
            provenance.source_type.value,
            observation.provider,
            observation.external_id,
            observation.name,
            observation.address,
            observation.prefecture,
            observation.category,
            observation.longitude,
            observation.latitude,
            observation.confidence
            if observation.confidence is not None
            else provenance.default_confidence,
            observation.verification_status.value,
            observation.observed_at,
            observation.expires_at,
            json.dumps(observation.payload or {}, ensure_ascii=False),
            content_hash,
        ),
    ).fetchone()
    if row is None:
        existing = connection.execute(
            """
            SELECT id FROM source_records
             WHERE dataset_version_id IS NULL
               AND provider = %s AND external_id = %s AND content_hash = %s
            """,
            (observation.provider, observation.external_id, content_hash),
        ).fetchone()
        if existing is None:
            raise RuntimeError("source observation conflict could not be resolved")
        return int(existing["id"]), False
    source_record_id = int(row["id"])
    connection.execute(
        """
        UPDATE source_records
           SET record_status = 'superseded', superseded_by = %s
         WHERE dataset_version_id IS NULL
           AND provider = %s
           AND external_id = %s
           AND id <> %s
           AND record_status = 'active'
        """,
        (source_record_id, observation.provider, observation.external_id, source_record_id),
    )
    return source_record_id, True


def _link_source_record(connection: Connection, source_record_id: int) -> bool:
    previous = connection.execute(
        """
        SELECT previous_link.facility_id
          FROM source_records current_record
          JOIN source_records previous_record
            ON previous_record.provider = current_record.provider
           AND previous_record.external_id = current_record.external_id
           AND previous_record.id <> current_record.id
          JOIN facility_source_links previous_link
            ON previous_link.source_record_id = previous_record.id
           AND previous_link.status = 'matched'
         WHERE current_record.id = %s
         ORDER BY previous_record.fetched_at DESC, previous_record.id DESC
         LIMIT 1
        """,
        (source_record_id,),
    ).fetchone()
    if previous is not None:
        connection.execute(
            """
            INSERT INTO facility_source_links (
              facility_id, source_record_id, status, match_method, match_score,
              decision_reason, decided_at, decided_by
            ) VALUES (%s, %s, 'matched', 'provider_external_id', 1.0,
                      'Reused an earlier exact provider/external-ID decision', now(), 'system')
            ON CONFLICT (source_record_id) DO UPDATE SET
              facility_id = EXCLUDED.facility_id,
              status = 'matched',
              match_method = EXCLUDED.match_method,
              match_score = EXCLUDED.match_score,
              decision_reason = EXCLUDED.decision_reason,
              decided_at = now(),
              decided_by = 'system'
            """,
            (previous["facility_id"], source_record_id),
        )
        return True
    connection.execute(
        """
        INSERT INTO facility_source_links (source_record_id, status)
        VALUES (%s, 'pending')
        ON CONFLICT (source_record_id) DO NOTHING
        """,
        (source_record_id,),
    )
    return False


def ingest_provider(
    connection: Connection,
    provider: SourceProvider,
    request: FetchRequest,
) -> IngestionResult:
    discovered = 0
    normalized_count = 0
    inserted = 0
    reused = 0
    pending = 0
    inserted_source_ids: list[int] = []

    for raw_record in provider.discover(request):
        discovered += 1
        observation = provider.normalize(raw_record)
        if observation is None:
            continue
        normalized_count += 1
        source_record_id, was_inserted = _insert_source_record(
            connection,
            provider=provider,
            observation=observation,
        )
        if not was_inserted:
            continue
        inserted += 1
        inserted_source_ids.append(source_record_id)
        if _link_source_record(connection, source_record_id):
            reused += 1
        else:
            pending += 1

    candidates = 0
    for source_record_id in inserted_source_ids:
        candidates += generate_match_candidates(connection, source_record_id=source_record_id)
    return IngestionResult(discovered, normalized_count, inserted, reused, pending, candidates)


def ingestion_stats(result: IngestionResult) -> dict[str, int]:
    return {
        "discovered": result.discovered,
        "normalized": result.normalized,
        "inserted": result.inserted,
        "reused": result.reused,
        "pending": result.pending,
        "candidates": result.candidates,
    }


def iso_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
