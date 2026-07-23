# Toilet Map v2

Toilet Map v2 is the production replacement for the original Streamlit application. It uses PostgreSQL + PostGIS as the single source of truth and publishes only fully validated dataset versions.

## Included

- responsive Next.js + Leaflet map UI
- FastAPI read API with search, score, category, prefecture and bounding-box filters
- PostgreSQL/PostGIS schema with versioned datasets
- canonical `facilities` that remain stable across dataset versions
- source-level observations with provenance, confidence, verification state and freshness
- explicit source-to-facility resolution with pending, matched and rejected decisions
- versioned public read-model snapshots
- legacy `data/toilets.json.gz` importer with compatibility dual writes
- provider discovery/normalization boundary for Google Maps JSONL and future open-data sources
- database-backed validation/publication worker with retries
- transactional publication that atomically builds snapshots and supersedes the previous dataset
- multidimensional score storage for cleanliness, odor, congestion, freshness, equipment, accessibility and child friendliness
- Docker Compose development and migration stack
- backend, frontend, API, database and container CI

## Data model

The ingestion model deliberately separates an actual facility from observations made by individual sources.

```text
provider -> source_records -> facility_source_links -> facilities
                                                \
                                                 -> facility_scores / score_evidence

dataset_versions -> places (compatibility read model)
                 -> published_place_snapshots (versioned canonical read model)
```

`source_records` preserve source type, provider ID, raw payload, content hash, confidence, verification status, fetch time and expiry. A source record is not considered a canonical facility until a `facility_source_links` decision is `matched`.

The current public places API remains backed by `places` during the migration. Imports dual-write canonical facilities and source records, and publication builds `published_place_snapshots`. This allows the frontend to remain compatible while the provider and entity-resolution layers are introduced incrementally.

## Start locally

```bash
export ADMIN_API_KEY=replace-this-value
docker compose -f v2/docker-compose.yml up --build -d
```

Services:

- frontend: `http://localhost:3000`
- backend/OpenAPI: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`

## Import and publish the existing dataset

The migration service mounts the repository's existing `data/` directory read-only, imports the canonical gzip snapshot, validates it and publishes it transactionally.

```bash
docker compose -f v2/docker-compose.yml --profile tools run --rm migrate
```

The command is equivalent to:

```bash
python -m app.cli init-db
python -m app.cli import-legacy /data/toilets.json.gz --publish
```

Re-running the importer creates a new dataset version. The old published version remains visible until validation succeeds and publication commits.

Applying the schema to an existing v2 database backfills canonical facilities, source records, exact legacy links and a snapshot for the currently published dataset. It does not remove or rename the compatibility tables.

## Operational commands

```bash
python -m app.cli status
python -m app.cli data-quality
python -m app.cli validate DATASET_ID
python -m app.cli publish DATASET_ID
python -m app.cli resolve-sources
python -m app.cli expire-sources
python -m app.worker
```

Administrative API calls require the `X-Admin-Key` header matching `ADMIN_API_KEY`.

Useful endpoints:

- `GET /api/v2/places/{place_id}` includes matched source provenance and dimensional scores
- `GET /api/v2/facilities/{facility_id}/provenance` returns the canonical entity and source decisions
- `GET /api/v2/admin/data-quality` reports active/stale sources, pending/rejected links and snapshot counts

## Publication guarantees

1. Collection/import writes only to a staging dataset.
2. Validation checks names, coordinates, duplicate keys, score ranges and canonical source links.
3. Only a `validated` dataset can be published.
4. Publication rebuilds versioned canonical snapshots before changing the published pointer.
5. Publication supersedes the old version and promotes the new version in one transaction.
6. Public API queries remain restricted to the single `published` dataset during migration.
7. Failed, partial or unresolved imports never become visible.

## Provider implementation contract

Providers should implement three separate operations:

1. `discover()` retrieves immutable raw records.
2. `normalize()` converts a raw record into a common observation without deciding facility identity.
3. `provenance()` declares the source type, default confidence, verification state and licensing metadata.

Entity resolution happens after normalization. A provider must not silently merge its observation into a canonical facility.

## Production cutover

1. Provision PostgreSQL with PostGIS.
2. Set `DATABASE_URL`, `ADMIN_API_KEY`, `CORS_ORIGINS` and `NEXT_PUBLIC_API_BASE_URL`.
3. Apply `v2/backend/schema.sql` or run `python -m app.cli init-db`.
4. Run `python -m app.cli data-quality` and confirm there are no pending links for the release dataset.
5. Import and publish the current canonical snapshot.
6. Deploy backend and worker from `v2/backend/Dockerfile`.
7. Deploy frontend from `v2/frontend/Dockerfile`.
8. Verify `/health`, `/api/v2/stats`, provenance, map rendering and one filtered search.
9. Route production traffic to v2. Keep the Streamlit deployment available for rollback until the first successful scheduled refresh.
