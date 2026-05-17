# Architecture

## Overview

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Streamlit   │────▶│   SQLite DB   │◀────│  Scraper    │
│  (app.py)    │     │ (data/*.db)   │     │ (Docker)    │
└──────┬───────┘     └──────────────┘     └─────────────┘
       │
       ▼
┌─────────────┐
│   Folium     │
│   Map +      │
│   Markers    │
└─────────────┘
```

## Module Layout

- `app.py` — Entry point, UI orchestration
- `app_config.py` — Constants (now powered by `app_settings.py`)
- `app_settings.py` — Pydantic Settings with env override
- `ui/` — UI logic (sidebar, map, popups, pagination, filters, etc.)
- `batch/` — Data processing pipeline + API server
- `static/` — CSS, JS, PWA assets
- `tests/` — Unit, E2E, benchmark, i18n, a11y tests
