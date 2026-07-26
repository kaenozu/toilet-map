# v2 Production Cutover Runbook

## Overview

This document defines the step-by-step procedure for promoting the v2 Preview
environment to Production. Each step has a clear pass/fail criterion and a
rollback path.

## Prerequisites

- [ ] Preview rehearsal passed (see docs/rehearsals/2026-07-26-v2-local-preview-cutover.md)
- [ ] PR #104 (worker healthcheck + evidence fix) merged
- [ ] All services built and tagged with a release version
- [ ] Production DB backup confirmed exists and is restorable
- [ ] Production environment variables audited (secrets, CORS, URLs)

## Phase 1 — Database Migration

### 1.1 Backup Production DB

```bash
pg_dump -Fc -f backup-$(date +%Y%m%d).dump toilet_map
```

**Verification:** File exists and size > 100MB (expected ~50-100MB for 1349 facilities).

### 1.2 Migration Status Check

```bash
python -m app.cli migration-status
```

**Pass:** All migrations are at expected versions.
**Fail:** Do not proceed. Investigate and fix migration state.

### 1.3 Apply Migrations

```bash
python -m app.cli init-db
```

**Pass:** Returns list of applied migrations matching expected checksums.
**Fail:** Restore from backup, fix migration, retry.

### 1.4 Verify Migration Re-applies Cleanly

```bash
python -m app.cli init-db
```

**Pass:** No new migrations applied (idempotent).
**Fail:** Migration is not idempotent — block deployment.

## Phase 2 — Data Import

### 2.1 Import Legacy Data

```bash
python -m app.cli import-legacy /data/toilets.json.gz
```

**Pass:** `record_count` matches expected (1,349).
**Fail:** Do not publish. Investigate data integrity.

### 2.2 Validate

```bash
python -m app.cli data-quality
```

**Pass:** `pending_links` = 0, `pending_reports` = 0.
**Fail:** Investigate pending records before publishing.

### 2.3 Publish

```bash
python -m app.cli import-legacy /data/toilets.json.gz --publish
```

**Pass:** `published=True`, `record_count` confirms.
**Fail:** Existing publication data is preserved (transactional).

### 2.4 Post-Publish Quality

```bash
python -m app.cli data-quality
```

**Pass:** `published_snapshots` = 1,349.
**Fail:** Publication is incomplete — rollback and retry.

## Phase 3 — Service Deployment

### 3.1 Deploy Database

```bash
docker compose up -d db
```

**Pass:** Container healthy, pg_isready succeeds.

### 3.2 Deploy Backend

```bash
docker compose up -d backend
```

**Pass:** `curl localhost:8000/health` returns `{"status":"ok"}`.
**Rollback:** Stop backend, keep DB as-is.

### 3.3 Deploy Worker

```bash
docker compose up -d worker
```

**Pass:** Worker starts without crash (healthcheck disabled — verify via logs).

### 3.4 Deploy Frontend

```bash
docker compose up -d frontend
```

**Pass:** HTTP 200 on frontend URL.
**Rollback:** Stop frontend, users see v1 until resolved.

## Phase 4 — Smoke Tests

### 4.1 API Smoke

```bash
curl -s http://localhost:8000/api/v2/places?limit=1  # items array, total >= 1349
curl -s http://localhost:8000/api/v2/facets          # categories + prefectures populated
curl -s http://localhost:8000/api/v2/stats            # record_count >= 1349
```

**Pass:** All endpoints return expected data.

### 4.2 Frontend Smoke

Open frontend URL:
- [ ] Map loads with markers
- [ ] Search returns results
- [ ] Category filter works
- [ ] Facility card shows score and provenance

### 4.3 Admin Smoke

- [ ] Admin dashboard loads
- [ ] Data quality endpoint accessible
- [ ] Pending reports visible (if any)

## Phase 5 — PUBLIC_READ_MODEL Rollback Drill

### 5.1 Activate Rollback Mode

```bash
PUBLIC_READ_MODEL=places docker compose up -d backend
```

**Verify:** `curl -s http://localhost:8000/api/v2/places?limit=1` returns data
from `places` table (compatible with old schema).

### 5.2 Restore Normal Mode

```bash
docker compose up -d backend
```

**Verify:** `curl -s http://localhost:8000/api/v2/places?limit=1` returns data
from `published_place_snapshots` table.

## Phase 6 — Monitoring (Post-Deployment)

### 6.1 Immediate (first 15 minutes)

- [ ] API error rate: < 1%
- [ ] API latency p95: < 500ms
- [ ] Worker no crash in logs
- [ ] Search returns expected results

### 6.2 Short-term (first hour)

- [ ] No spike in 5xx errors
- [ ] Frontend rendering without errors
- [ ] No unexpected data discrepancies

### 6.3 Extended (24 hours)

- [ ] All automated health checks passing
- [ ] No regression in user-reported data quality
- [ ] Worker jobs completing successfully

## Phase 7 — Finalize

### 7.1 Verification Report

Record the following in a dated report:
- Production commit SHA
- Migration checksums
- Import record count
- Published snapshot count
- Smoke test results (API, Frontend, Admin)
- Rollback drill result
- Monitoring observations (15min, 1hr, 24hr)

### 7.2 Go/No-Go

- **Go:** All phases pass. Proceed to v1 deprecation planning.
- **No-Go:** Any phase fails. Rollback via PUBLIC_READ_MODEL=places,
  fix issue, schedule new deployment window.

## Rollback Quick Reference

| Scenario | Action |
|---|---|
| API returns errors | PUBLIC_READ_MODEL=places, restart backend |
| Data corruption | Restore DB from backup |
| Frontend broken | Stop frontend, users keep v1 |
| Migration fails | Restore DB, fix migration, retry |
| Worker crashes | Stop worker, fix, redeploy |
| Critical regression | Full rollback to v1, investigate |
