"""User-submitted facility reports and administrator decisions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from .db_types import DbConnection


class DuplicateReportError(ValueError):
    """Raised when the same report was already accepted for the same day."""


class ReportType(StrEnum):
    CLOSED = "closed"
    TEMPORARILY_CLOSED = "temporarily_closed"
    BROKEN = "broken"
    WRONG_LOCATION = "wrong_location"
    ACCESSIBILITY = "accessibility"
    CLEANLINESS = "cleanliness"
    OTHER = "other"


@dataclass(frozen=True)
class ReportPayload:
    report_type: ReportType
    note: str = ""
    occurred_at: datetime | None = None


def report_fingerprint(facility_id: int, payload: ReportPayload, *, day: str | None = None) -> str:
    report_day = day or datetime.now(UTC).date().isoformat()
    canonical = json.dumps(
        {
            "facility_id": facility_id,
            "report_type": payload.report_type.value,
            "note": payload.note.strip().casefold(),
            "day": report_day,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def create_report(connection: DbConnection, *, facility_id: int, payload: ReportPayload) -> dict[str, object]:
    facility = connection.execute(
        """
        SELECT id, name, address, prefecture, category,
               ST_Y(location::geometry) AS latitude,
               ST_X(location::geometry) AS longitude
          FROM facilities
         WHERE id = %s AND status <> 'removed'
        """,
        (facility_id,),
    ).fetchone()
    if facility is None:
        raise LookupError("facility not found")
    fingerprint = report_fingerprint(facility_id, payload)
    # Serialize equal reports so the deduplication check cannot race with the insert.
    connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (fingerprint,))
    duplicate = connection.execute(
        "SELECT id FROM facility_reports WHERE fingerprint = %s",
        (fingerprint,),
    ).fetchone()
    if duplicate is not None:
        raise DuplicateReportError("duplicate facility report")
    raw_payload = {
        "report_type": payload.report_type.value,
        "note": payload.note.strip(),
        "occurred_at": payload.occurred_at.isoformat() if payload.occurred_at else None,
    }
    source_external_id = str(uuid4())
    content_hash = hashlib.sha256(
        json.dumps(raw_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    source = connection.execute(
        """
        INSERT INTO source_records (
          source_type, provider, external_id, name, address, prefecture, category,
          location, confidence, verification_status, observed_at, raw_payload, content_hash
        ) VALUES (
          'user_submission', 'user-submission', %s, %s, %s, %s, %s,
          ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
          0.35, 'unverified', %s, %s::jsonb, %s
        ) RETURNING id
        """,
        (
            source_external_id,
            facility["name"],
            facility["address"],
            facility["prefecture"],
            facility["category"],
            facility["longitude"],
            facility["latitude"],
            payload.occurred_at or datetime.now(UTC),
            json.dumps(raw_payload, ensure_ascii=False),
            content_hash,
        ),
    ).fetchone()
    if source is None:
        raise RuntimeError("failed to store report source record")
    source_record_id = int(source["id"])
    connection.execute(
        """
        INSERT INTO facility_source_links (
          facility_id, source_record_id, status, match_method, match_score,
          decision_reason, decided_at, decided_by
        ) VALUES (%s, %s, 'matched', 'explicit_facility_report', 1.0,
                  'Reporter selected the facility explicitly', now(), 'reporter')
        """,
        (facility_id, source_record_id),
    )
    row = connection.execute(
        """
        INSERT INTO facility_reports (
          facility_id, source_record_id, report_type, note, fingerprint
        ) VALUES (%s, %s, %s, %s, %s)
        RETURNING id, facility_id, report_type, note, status, created_at
        """,
        (facility_id, source_record_id, payload.report_type.value, payload.note.strip(), fingerprint),
    ).fetchone()
    if row is None:
        raise RuntimeError("failed to create report")
    return dict(row)


def pending_reports(connection: DbConnection, *, limit: int = 100) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT report.id, report.facility_id, facility.name, facility.address,
               report.report_type, report.note, report.status, report.created_at
          FROM facility_reports report
          JOIN facilities facility ON facility.id = report.facility_id
         WHERE report.status = 'pending'
         ORDER BY report.created_at, report.id
         LIMIT %s
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def decide_report(
    connection: DbConnection,
    *,
    report_id: int,
    accepted: bool,
    decided_by: str,
    reason: str,
) -> dict[str, object]:
    report = connection.execute(
        """
        SELECT id, facility_id, source_record_id, report_type, status
          FROM facility_reports WHERE id = %s FOR UPDATE
        """,
        (report_id,),
    ).fetchone()
    if report is None:
        raise LookupError("report not found")
    if report["status"] != "pending":
        raise ValueError("report has already been decided")
    status = "accepted" if accepted else "rejected"
    connection.execute(
        """
        UPDATE facility_reports
           SET status = %s, decided_at = now(), decided_by = %s, decision_reason = %s
         WHERE id = %s
        """,
        (status, decided_by, reason, report_id),
    )
    verification_status = "human_verified" if accepted else "rejected"
    record_status = "active" if accepted else "rejected"
    connection.execute(
        """
        UPDATE source_records SET verification_status = %s, record_status = %s
         WHERE id = %s
        """,
        (verification_status, record_status, report["source_record_id"]),
    )
    if accepted and report["report_type"] in {"closed", "temporarily_closed"}:
        connection.execute(
            "UPDATE facilities SET status = %s, updated_at = now() WHERE id = %s",
            (report["report_type"], report["facility_id"]),
        )
    return {
        "report_id": report_id,
        "facility_id": int(report["facility_id"]),
        "status": status,
        "report_type": report["report_type"],
    }
