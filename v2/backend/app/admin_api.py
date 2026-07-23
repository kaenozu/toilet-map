"""Authenticated administrative ingestion, quality, resolution, and job routes."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from .db import database
from .importer import import_legacy
from .job_queue import EnqueueRequest, cancel_job, enqueue_job
from .reports import decide_report, pending_reports
from .resolution import (
    ResolutionAction,
    decide_source_record,
    generate_match_candidates,
    pending_source_records,
)

router = APIRouter(prefix="/api/v2/admin")
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "")


class ImportRequest(BaseModel):
    path: str = Field(default="/data/toilets.json.gz", min_length=1)
    source: str = Field(default="legacy-json", min_length=1, max_length=100)
    auto_publish: bool = False


class JobRequest(BaseModel):
    kind: str = Field(min_length=1, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=200)
    dataset_version_id: int | None = None
    provider: str | None = Field(default=None, max_length=100)
    max_attempts: int = Field(default=3, ge=1, le=20)
    retryable: bool = True


class ResolutionRequest(BaseModel):
    action: ResolutionAction
    facility_id: int | None = None
    reason: str = Field(min_length=1, max_length=1000)
    decided_by: str = Field(default="admin", min_length=1, max_length=100)


class ReportDecisionRequest(BaseModel):
    accepted: bool
    reason: str = Field(min_length=1, max_length=1000)
    decided_by: str = Field(default="admin", min_length=1, max_length=100)


class CandidateGenerationRequest(BaseModel):
    dataset_version_id: int | None = None
    source_record_id: int | None = None
    max_distance_m: float = Field(default=300, ge=10, le=5000)
    minimum_score: float = Field(default=0.35, ge=0, le=1)


def require_admin(x_admin_key: Annotated[str | None, Header()] = None) -> None:
    if not ADMIN_API_KEY or x_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin key")


@router.get("/data-quality", dependencies=[Depends(require_admin)])
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
              (SELECT count(*) FROM facility_reports WHERE status = 'pending') AS pending_reports,
              (SELECT count(*) FROM facilities f WHERE NOT EXISTS (
                 SELECT 1 FROM facility_source_links link
                  WHERE link.facility_id = f.id AND link.status = 'matched'
               )) AS facilities_without_sources,
              (SELECT count(*) FROM published_place_snapshots snapshot
                JOIN dataset_versions d ON d.id = snapshot.dataset_version_id
               WHERE d.status = 'published') AS published_snapshots
            """
        ).fetchone()
        migrations = connection.execute(
            "SELECT version, name, checksum, applied_at FROM schema_migrations ORDER BY version"
        ).fetchall()
    return {**(row or {}), "migrations": migrations}


@router.get("/source-records/pending", dependencies=[Depends(require_admin)])
def list_pending_sources(limit: int = Query(100, ge=1, le=500)) -> dict[str, object]:
    with database() as connection:
        items = pending_source_records(connection, limit=limit)
    return {"items": items, "total": len(items)}


@router.post("/source-records/{source_record_id}/decision", dependencies=[Depends(require_admin)])
def decide_source(source_record_id: int, request: ResolutionRequest) -> dict[str, Any]:
    try:
        with database() as connection:
            result = decide_source_record(
                connection,
                source_record_id=source_record_id,
                action=request.action,
                facility_id=request.facility_id,
                decided_by=request.decided_by,
                reason=request.reason,
            )
            connection.commit()
        return result
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/match-candidates/generate", dependencies=[Depends(require_admin)])
def generate_candidates(request: CandidateGenerationRequest) -> dict[str, int]:
    with database() as connection:
        total = generate_match_candidates(
            connection,
            dataset_version_id=request.dataset_version_id,
            source_record_id=request.source_record_id,
            max_distance_m=request.max_distance_m,
            minimum_score=request.minimum_score,
        )
        connection.commit()
    return {"generated": total}


@router.get("/reports/pending", dependencies=[Depends(require_admin)])
def list_pending_reports(limit: int = Query(100, ge=1, le=500)) -> dict[str, object]:
    with database() as connection:
        items = pending_reports(connection, limit=limit)
    return {"items": items, "total": len(items)}


@router.post("/reports/{report_id}/decision", dependencies=[Depends(require_admin)])
def resolve_report(report_id: int, request: ReportDecisionRequest) -> dict[str, object]:
    try:
        with database() as connection:
            result = decide_report(
                connection,
                report_id=report_id,
                accepted=request.accepted,
                decided_by=request.decided_by,
                reason=request.reason,
            )
            connection.commit()
        return result
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/import", dependencies=[Depends(require_admin)])
def admin_import(request: ImportRequest) -> dict[str, object]:
    dataset_id, count = import_legacy(Path(request.path), source=request.source)
    with database() as connection:
        validation_id, _ = enqueue_job(
            connection,
            EnqueueRequest(
                kind="validate_dataset",
                payload={"dataset_version_id": dataset_id},
                dataset_version_id=dataset_id,
                idempotency_key=f"validate-dataset:{dataset_id}",
            ),
        )
        publish_id = None
        if request.auto_publish:
            publish_id, _ = enqueue_job(
                connection,
                EnqueueRequest(
                    kind="publish_dataset",
                    payload={"dataset_version_id": dataset_id},
                    dataset_version_id=dataset_id,
                    parent_job_id=validation_id,
                    idempotency_key=f"publish-dataset:{dataset_id}",
                ),
            )
        connection.commit()
    return {
        "dataset_version_id": dataset_id,
        "record_count": count,
        "validation_job_id": validation_id,
        "publish_job_id": publish_id,
    }


@router.post("/jobs", dependencies=[Depends(require_admin)])
def create_job(request: JobRequest) -> dict[str, object]:
    with database() as connection:
        job_id, created = enqueue_job(
            connection,
            EnqueueRequest(
                kind=request.kind,
                payload=request.payload,
                idempotency_key=request.idempotency_key,
                dataset_version_id=request.dataset_version_id,
                provider=request.provider,
                max_attempts=request.max_attempts,
                retryable=request.retryable,
            ),
        )
        connection.commit()
    return {"job_id": job_id, "created": created}


@router.post("/jobs/{job_id}/cancel", dependencies=[Depends(require_admin)])
def stop_job(job_id: int) -> dict[str, object]:
    with database() as connection:
        cancelled = cancel_job(connection, job_id=job_id)
        connection.commit()
    if not cancelled:
        raise HTTPException(status_code=409, detail="job is already running or finished")
    return {"job_id": job_id, "cancelled": True}
