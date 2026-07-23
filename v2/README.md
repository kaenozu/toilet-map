# Toilet Map v2

This directory contains the replacement architecture. The existing Streamlit application remains untouched until v2 reaches feature parity.

## Architecture

- `frontend/`: Next.js map UI
- `backend/`: FastAPI read API and administration endpoints
- `worker/`: database-backed scrape and scoring jobs
- PostgreSQL + PostGIS is the single source of truth
- external place providers are adapters behind a protocol

## Local start

```bash
docker compose -f v2/docker-compose.yml up --build
```

Services:

- frontend: http://localhost:3000
- backend: http://localhost:8000/docs
- PostgreSQL: localhost:5432

## Publication model

Collectors write to staging records attached to a `dataset_version`. A version is published only after validation succeeds. Readers always query the latest published version, so partially completed runs are never visible.

## Migration sequence

1. Establish schema, API and worker state machine.
2. Import the current canonical JSON snapshot.
3. Add Google Maps scraper adapter and open-data adapters.
4. Reach UI feature parity.
5. Switch production traffic from Streamlit to v2.
