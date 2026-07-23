from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from psycopg import Connection

from .providers import SourceType, VerificationStatus


@dataclass(frozen=True)
class EntityIds:
    facility_id: int
    source_record_id: int


def payload_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def canonical_facility_key(source_type: SourceType, provider: str, external_id: str) -> str:
    if source_type is SourceType.LEGACY:
        return f"legacy:{external_id}"
    return f"{source_type.value}:{provider.casefold()}:{external_id}"


def source_type_from_provider(provider: str, *, legacy_import: bool = False) -> SourceType:
    if legacy_import:
        return SourceType.LEGACY
    normalized = provider.casefold()
    if "openstreetmap" in normalized or normalized == "osm":
        return SourceType.OPENSTREETMAP
    if "google" in normalized:
        return SourceType.GOOGLE_MAPS
    if "municipal" in normalized or "open-data" in normalized or "opendata" in normalized:
        return SourceType.MUNICIPALITY_OPEN_DATA
    if "submission" in normalized or "user" in normalized:
        return SourceType.USER_SUBMISSION
    if "admin" in normalized:
        return SourceType.ADMIN
    return SourceType.LEGACY


def upsert_legacy_entity(
    connection: Connection,
    *,
    dataset_id: int,
    provider: str,
    item: dict[str, Any],
) -> EntityIds:
    external_id = str(item["stable_key"])
    source_type = source_type_from_provider(provider, legacy_import=True)
    content_hash = payload_hash(item["raw_payload"])
    source_row = connection.execute(
        """
        INSERT INTO source_records (
          dataset_version_id, source_type, provider, external_id, name, address, prefecture,
          category, location, confidence, verification_status, raw_payload, content_hash
        ) VALUES (
          %s, %s, %s, %s, %s, %s, %s,
          %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
          %s, %s, %s::jsonb, %s
        )
        ON CONFLICT (dataset_version_id, provider, external_id) DO UPDATE SET
          name = EXCLUDED.name,
          address = EXCLUDED.address,
          prefecture = EXCLUDED.prefecture,
          category = EXCLUDED.category,
          location = EXCLUDED.location,
          confidence = EXCLUDED.confidence,
          verification_status = EXCLUDED.verification_status,
          raw_payload = EXCLUDED.raw_payload,
          content_hash = EXCLUDED.content_hash,
          fetched_at = now(),
          record_status = 'active'
        RETURNING id
        """,
        (
            dataset_id,
            source_type.value,
            provider,
            external_id,
            item["name"],
            item["address"],
            item["prefecture"],
            item["category"],
            item["longitude"],
            item["latitude"],
            item["confidence"],
            VerificationStatus.UNVERIFIED.value,
            json.dumps(item["raw_payload"], ensure_ascii=False),
            content_hash,
        ),
    ).fetchone()
    if source_row is None:
        raise RuntimeError("failed to upsert source record")
    source_record_id = int(source_row["id"])

    canonical_key = canonical_facility_key(source_type, provider, external_id)
    facility_row = connection.execute(
        """
        INSERT INTO facilities (
          canonical_key, name, address, prefecture, category, location, attributes
        ) VALUES (
          %s, %s, %s, %s, %s,
          ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
          %s::jsonb
        )
        ON CONFLICT (canonical_key) DO UPDATE SET
          name = EXCLUDED.name,
          address = EXCLUDED.address,
          prefecture = EXCLUDED.prefecture,
          category = EXCLUDED.category,
          location = EXCLUDED.location,
          attributes = facilities.attributes || EXCLUDED.attributes,
          updated_at = now()
        RETURNING id
        """,
        (
            canonical_key,
            item["name"],
            item["address"],
            item["prefecture"],
            item["category"],
            item["longitude"],
            item["latitude"],
            json.dumps(item["attributes"], ensure_ascii=False),
        ),
    ).fetchone()
    if facility_row is None:
        raise RuntimeError("failed to upsert facility")
    facility_id = int(facility_row["id"])

    connection.execute(
        """
        INSERT INTO facility_source_links (
          facility_id, source_record_id, status, match_method, match_score,
          decision_reason, decided_at, decided_by
        ) VALUES (%s, %s, 'matched', 'legacy_stable_key', 1.0, %s, now(), 'system')
        ON CONFLICT (source_record_id) DO UPDATE SET
          facility_id = EXCLUDED.facility_id,
          status = 'matched',
          match_method = EXCLUDED.match_method,
          match_score = EXCLUDED.match_score,
          decision_reason = EXCLUDED.decision_reason,
          decided_at = now(),
          decided_by = EXCLUDED.decided_by
        """,
        (facility_id, source_record_id, "Legacy import stable key"),
    )
    return EntityIds(facility_id=facility_id, source_record_id=source_record_id)
