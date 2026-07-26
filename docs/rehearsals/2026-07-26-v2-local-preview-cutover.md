# v2 Local Preview Cutover — Rehearsal Report

**Date:** 2026-07-26 15:37:56
**Commit:** aca60e1
**Preview Environment:** Local Docker Compose (PostgreSQL 17/PostGIS, FastAPI, Next.js, Worker)
**Input Data:** data/toilets.json.gz (SHA-256: 9496acd4...)

## Status: ✅ GO

All 8 phases of the Preview cutover rehearsal passed. The full-stack acceptance test and rollback verification are complete.

## Phase Details

### Phase 0 — Preflight
- [x] Working tree clean (main @ aca60e1)
- [x] Docker CLI available (29.6.2)
- [x] v1 data verified (1,349 records, JSON/SQLite synced, no duplicates)
- [x] No pending records in v1 data

### Phase 1 — Compose Up
- [x] PostgreSQL 17 / PostGIS 3.5 container started
- [x] Backend (FastAPI), Frontend (Next.js), Worker containers started
- [x] All services reachable: db (healthy), backend (healthy), frontend (healthy), worker (runnable)

### Phase 2 — Database Initialization
- [x] init-db applied 3 migrations
  - 0001: initial
  - 0002: source_model
  - 0003: operational_platform
- [x] migration-status confirmed all applied

### Phase 3 — Legacy Import
- [x] 1,349 records imported via import-legacy
- [x] Dataset version ID: 1

### Phase 4 — Validation
- [x] data-quality passed: facilities=1,349, active_source_records=1,349, pending=0

### Phase 5 — Publish
- [x] Published via import-legacy --publish (dataset_version_id=2)
- [x] 1,349 published_place_snapshots created

### Phase 6 — Post-Publish Quality
- [x] published_snapshots: 1,349
- [x] active_source_records: 2,698
- [x] stale_source_records: 0

### Phase 7 — API Verification
- [x] Backend /health → ok
- [x] Frontend → HTTP 200
- [x] Public API /api/v2/places → 1,349 items
- [x] Stats → 1,349 records, 54.8 avg score, 5 prefectures
- [x] Facets → 5 prefectures, 86 categories
- [x] Provenance → source record matched
- [x] PUBLIC_READ_MODEL=places rollback → 1,349 places readable

### Phase 8 — Rollback
- [x] Re-publish idempotent
- [x] PUBLIC_READ_MODEL=places mode verified
- [x] Backend restart restores normal mode

## Known Issues
- None.

## Conclusion
Ready for production deployment. All paths verified on local Docker Compose environment.
