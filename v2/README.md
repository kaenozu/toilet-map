# Toilet Map v2

Toilet Map v2 is the production replacement for the original Streamlit application. It separates source observations from long-lived facilities and publishes immutable snapshots for the public API.

## Architecture

```text
provider discovery
  -> source_records
  -> facility_source_links / facility_match_candidates
  -> facilities
  -> dimension_observations / facility_scores
  -> published_place_snapshots
  -> public API / Next.js map
```

Compatibility tables (`places`, `provider_records`, `reviews`, `score_history`) remain available during migration. New imports dual-write both models. The public API reads `published_place_snapshots` by default and can temporarily fall back to `places` with `PUBLIC_READ_MODEL=places`.

## Features

- responsive Next.js + Leaflet map UI
- FastAPI search with score, trust, equipment, location, prefecture and bounding-box filters
- immutable published snapshots with legacy place IDs preserved
- stable canonical facility IDs across dataset versions
- source provenance, verification status, freshness and trust score
- explicit pending/matched/rejected source resolution
- administrator merge/new-facility/reject workflow
- bounded OpenStreetMap ingestion for Kumagaya, Gyoda and Fukaya
- user reports for closures, faults, wrong locations and accessibility issues
- multidimensional score observations and auditable aggregates
- leased, idempotent PostgreSQL job queue
- versioned SQL migrations with checksum validation
- Docker Compose development and CI against PostgreSQL/PostGIS

## Local start

```bash
cd v2
cp .env.example .env
docker compose up --build
```

Services:

- frontend: `http://localhost:3000`
- backend: `http://localhost:8000`
- PostgreSQL/PostGIS: `localhost:5432`

## Database migrations

`python -m app.cli init-db` is the authoritative schema operation. It discovers `v2/backend/migrations/*.sql`, obtains a PostgreSQL advisory lock, validates migration checksums and applies each pending migration in its own transaction.

```bash
cd v2/backend
python -m app.cli init-db
python -m app.cli migration-status
```

`schema.sql` is a thin `psql` bootstrap that includes the same versioned migration files. Production upgrades should use the migration runner so the applied version and checksum are recorded.

Current migration sequence:

```text
0001_initial
0002_source_model
0003_operational_platform
```

Before production application:

1. back up the database
2. run migration status
3. apply migrations in Preview
4. compare compatibility rows and snapshots
5. validate a staging dataset
6. publish it
7. verify the public API
8. retain the previous deployment for rollback

## Legacy import and publication

```bash
python -m app.cli import-legacy /data/toilets.json.gz --source legacy-json
python -m app.cli validate DATASET_ID
python -m app.cli publish DATASET_ID
```

Publication is transactional and revalidates canonical integrity inside the publication transaction. It rejects a dataset when:

- it contains no places
- `facility_id` is missing
- `source_record_id` is missing
- the place source is not matched to the same facility
- snapshot count differs from compatibility place count

The previously published dataset is not superseded until the new snapshot has been built successfully.

## OpenStreetMap ingestion

OSM ingestion is intentionally bounded. It stores observations and match candidates but never merges by distance or name automatically.

```bash
python -m app.cli ingest-osm --region kumagaya
python -m app.cli ingest-osm --region gyoda
python -m app.cli ingest-osm --region fukaya
python -m app.cli generate-candidates
```

Only an earlier exact `provider + external_id` decision is reused automatically. Name, address and distance produce review candidates only.

OSM attributes currently include:

- wheelchair
- changing table
- fee
- unisex
- opening hours
- access
- operator
- disposal and position tags

OSM data is attributed under the Open Database License. The provider exposes the OpenStreetMap copyright URL in provenance metadata.

## Data-quality administration

The administrator UI is available at `/admin`. Enter the same key configured as `ADMIN_API_KEY`.

Administrative API endpoints:

```text
GET  /api/v2/admin/data-quality
GET  /api/v2/admin/source-records/pending
POST /api/v2/admin/source-records/{id}/decision
POST /api/v2/admin/match-candidates/generate
GET  /api/v2/admin/reports/pending
POST /api/v2/admin/reports/{id}/decision
POST /api/v2/admin/import
POST /api/v2/admin/jobs
POST /api/v2/admin/jobs/{id}/cancel
```

Source decisions:

- `match`: link to an existing facility
- `new_facility`: create a facility from the source observation
- `reject`: reject the source observation

Candidate score uses name similarity, address similarity and distance. Candidate scores are advisory and do not trigger automatic merges.

## Public API

Useful endpoints:

```text
GET  /health
GET  /api/v2/places
GET  /api/v2/places/{legacy_place_id}
GET  /api/v2/facilities/{facility_id}/provenance
POST /api/v2/facilities/{facility_id}/reports
GET  /api/v2/stats
GET  /api/v2/facets
```

Selected place filters:

```text
q
prefecture
category
min_score
min_trust
wheelchair
changing_table
fee
open_24h
latitude + longitude + radius_m
north + south + east + west
```

The public response includes:

- stable `facility_id`
- compatibility place ID
- source record ID
- trust score
- verification status
- source count
- last verification time
- optional distance from the supplied current location

## Trust score

Trust combines source confidence, verification state and freshness. Human-verified recent records receive the highest score. Expired, stale, disputed and rejected observations are discounted heavily.

Trust score does not replace cleanliness score. It answers a different question: how reliable and current is the displayed facility information?

## User reports

The public UI can submit reports for:

- closed
- temporarily closed
- broken
- wrong location
- accessibility information
- cleanliness information
- other

Reports are stored as `user_submission` source records and remain pending until an administrator accepts or rejects them. A report never closes a facility automatically.

## Job queue

The worker supports:

```text
validate_dataset
publish_dataset
detect_stale_source_records
resolve_source_records
generate_match_candidates
ingest_osm
```

Jobs support idempotency keys, parent dependencies, leases, heartbeats, retry waits, cancellation, error classification and execution statistics. Expired leases are recovered instead of leaving jobs permanently running.

```bash
python -m app.worker
```

## Operational commands

```bash
python -m app.cli status
python -m app.cli data-quality
python -m app.cli resolve-sources
python -m app.cli expire-sources
python -m app.cli generate-candidates
```

## Production cutover

1. Provision PostgreSQL with PostGIS and `pg_trgm`.
2. Set `DATABASE_URL`, `ADMIN_API_KEY`, `CORS_ORIGINS`, `API_BASE_URL` and `PUBLIC_READ_MODEL=snapshot`.
3. Apply versioned migrations.
4. Run data quality and confirm no unresolved source records in the release dataset.
5. Import, validate and publish the release dataset.
6. Confirm snapshot count equals compatibility place count.
7. Deploy backend and worker.
8. Deploy frontend.
9. Verify health, search, trust filters, provenance, current-location search and one report submission.
10. Keep `PUBLIC_READ_MODEL=places` available only as a temporary rollback switch.
