# Toilet Cleanliness Map

A project for collecting, reconciling, scoring, and mapping public-toilet information.

The repository currently keeps two implementations during the v2 migration:

- **v2 (new platform):** Next.js + FastAPI + PostgreSQL/PostGIS, with provenance-aware observations, canonical facilities, immutable publication snapshots, and an administrator workflow
- **v1 (existing application):** Streamlit + SQLite, retained for service and data-pipeline compatibility during rollout

See [`v2/README.md`](v2/README.md) for the complete v2 architecture, migration, import, publication, and rollback procedures.

## v2 Overview

```text
provider discovery
  -> source_records
  -> facility_source_links / facility_match_candidates
  -> facilities
  -> dimension_observations / facility_scores
  -> published_place_snapshots
  -> FastAPI / Next.js map
```

Key capabilities:

- separates long-lived `facilities` from provider-specific `source_records`
- records explicit `pending`, `matched`, and `rejected` resolution decisions
- publishes immutable snapshots while preserving legacy place identifiers
- exposes cleanliness, odor, congestion, freshness, equipment, accessibility, and child-friendliness dimensions
- filters by trust, freshness, equipment, and distance from the current location
- provides an `/admin` workflow for matching, facility creation, and rejection
- runs versioned, checksummed SQL migrations and a leased, idempotent PostgreSQL job queue
- keeps the Streamlit application and compatibility tables available during migration

## v2 Quick Start

### Full stack with Docker Compose

```bash
cd v2
cp .env.example .env
docker compose up --build
```

Services:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- PostgreSQL/PostGIS: `localhost:5432`
- Admin UI: `http://localhost:3000/admin`

### Frontend-only validation

The frontend can be type-checked and built without Docker:

```bash
cd v2/frontend
npm install --no-audit --no-fund
npm run typecheck
npm run build
```

CI uses Node.js 22. npm dependencies under `v2/frontend` are also monitored by Dependabot.

### Backend validation

Run this with PostgreSQL/PostGIS available:

```bash
cd v2/backend
pip install '.[dev]'
python -m app.cli init-db
python -m app.cli migration-status
pytest -q
```

## v2 Operational Commands

```bash
cd v2/backend

python -m app.cli import-legacy ../../data/toilets.json.gz --source legacy-json
python -m app.cli validate DATASET_ID
python -m app.cli publish DATASET_ID
python -m app.cli data-quality
python -m app.cli migration-status
python -m app.cli ingest-osm --region kumagaya
python -m app.cli generate-candidates
python -m app.worker
```

Before production rollout, use Preview to validate a clean database, migrations, legacy import, publication, API responses, and the frontend. Failed publication keeps the existing published dataset active. `PUBLIC_READ_MODEL=places` is a temporary read-model rollback switch.

## v1 Streamlit Application

### Features

- interactive map and score display
- prefecture and category filters
- current-location distance sorting
- freshness metadata
- Japanese and English UI

### Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

For Streamlit Cloud:

```bash
streamlit run streamlit_app.py
```

### Data Pipeline

```text
Google Maps Scraper (Docker)
  -> raw JSONL
  -> batch/process_data.py
  -> data/toilets.json.gz
  -> batch/to_sqlite.py
  -> data/toilets.db
```

## Repository Layout

```text
toilet-map/
├── app.py                    # v1 Streamlit application
├── ui/                       # v1 UI
├── batch/                    # v1 pipeline and compatibility API
├── data/                     # canonical JSON and SQLite snapshot
├── tests/                    # v1 regression tests
└── v2/
    ├── backend/              # FastAPI, PostgreSQL, migrations, worker
    ├── frontend/             # Next.js, Leaflet, admin UI
    ├── docker-compose.yml
    └── README.md
```

## Validation

### v1

```bash
ruff check . --no-fix
mypy .
pytest tests/ -v
python batch/verify_data.py
```

### v2

```bash
ruff check v2/backend --no-fix
cd v2/backend && pytest -q
cd ../frontend && npm run typecheck && npm run build
docker compose -f v2/docker-compose.yml config
docker compose -f v2/docker-compose.yml build
```

CI validates v1 and v2 separately. The v2 Compose smoke workflow covers a clean database, migrations, legacy import, API, and frontend startup.

## Legacy Score Mapping

| Score | Icon | Label |
|-------|------|-------|
| 80–100 | ✨ | Very clean |
| 65–79 | 😊 | Clean |
| 50–64 | 😐 | Average |
| 35–49 | 😨 | Slightly concerning |
| 0–34 | 💩 | Needs attention |

Score = `(raw_score + 5) × 10`, mapping −5…+5 to 0…100.

## Operational Notes

- `data/toilets.json.gz` and `data/toilets.db` remain committed v1 delivery artifacts.
- Raw scraping intermediates stay ignored.
- Do not apply production migrations, publish production datasets, or run live provider ingestion before Preview validation and backup.
