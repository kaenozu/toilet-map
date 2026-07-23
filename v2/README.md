# Toilet Map v2

Toilet Map v2 is the production replacement for the original Streamlit application. It uses PostgreSQL + PostGIS as the single source of truth and publishes only fully validated dataset versions.

## Included

- responsive Next.js + Leaflet map UI
- FastAPI read API with search, score, category, prefecture and bounding-box filters
- PostgreSQL/PostGIS schema with versioned datasets
- legacy `data/toilets.json.gz` importer
- provider adapter boundary for Google Maps JSONL and future open-data sources
- database-backed validation/publication worker with retries
- transactional publication that atomically supersedes the previous dataset
- versioned score history schema and deterministic scoring module
- Docker Compose development and migration stack
- backend, frontend, API, database and container CI

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

## Operational commands

```bash
python -m app.cli status
python -m app.cli validate DATASET_ID
python -m app.cli publish DATASET_ID
python -m app.worker
```

Administrative API calls require the `X-Admin-Key` header matching `ADMIN_API_KEY`.

## Publication guarantees

1. Collection/import writes only to a staging dataset.
2. Validation checks non-empty data, names, coordinates, duplicate stable keys and score ranges.
3. Only a `validated` dataset can be published.
4. Publication supersedes the old version and promotes the new version in one transaction.
5. Public API queries are restricted to the single `published` dataset.
6. Failed or partial imports never become visible.

## Production cutover

1. Provision PostgreSQL with PostGIS.
2. Set `DATABASE_URL`, `ADMIN_API_KEY`, `CORS_ORIGINS` and `NEXT_PUBLIC_API_BASE_URL`.
3. Apply `v2/backend/schema.sql` or run `python -m app.cli init-db`.
4. Import and publish the current canonical snapshot.
5. Deploy backend and worker from `v2/backend/Dockerfile`.
6. Deploy frontend from `v2/frontend/Dockerfile`.
7. Verify `/health`, `/api/v2/stats`, map rendering and one filtered search.
8. Route production traffic to v2. Keep the Streamlit deployment available for rollback until the first successful scheduled refresh.
