# Toilet Cleanliness Map

Auto-judges toilet cleanliness from Google Maps reviews, displayed on a Streamlit map with Folium.

## Features

- Interactive map with MarkerCluster
- Cleanliness scoring (0–100)
- Filtering by prefecture / category
- GPS-based current location
- Free-text search (name, address, category)
- i18n: English / Japanese
- Mobile responsive layout
- Dark mode support
- Collapsible sidebar

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Data Pipeline

```
Google Maps Scraper (Docker) → raw JSONL
  → process_data.py → data/toilets.json.gz (canonical JSON)
    → to_sqlite.py → data/toilets.db (SQLite cache)
```

## Scoring

| Score | Icon | Label        |
|-------|------|--------------|
| 0–34  | 💩   | Needs attention |
| 35–49 | 😨   | Slightly concerning |
| 50–64 | 😐   | Average      |
| 65–79 | 😊   | Clean        |
| 80–100| ✨   | Very clean   |

Score = (raw_score + 5) × 10 (maps −5…+5 → 0…100).

## Tech Stack

- **App**: Python 3.11+ / Streamlit / Folium / streamlit-folium / Pandas
- **Scraping**: Docker / Google Maps Scraper
- **Data**: JSON / JSONL / SQLite
- **Testing**: pytest (589 tests)
- **Lint**: ruff

## Commands

| Purpose | Command |
|---------|---------|
| Run app | `streamlit run app.py` |
| Run tests | `pytest tests/ -v` |
| Lint | `ruff check . --no-fix` |
| Process raw data | `cd batch && python process_data.py raw_data.json ../data/toilets.json.gz --incremental` |
| Sync SQLite | `cd batch && python to_sqlite.py ../data/toilets.json.gz --incremental` |
| Auto pipeline | `batch/auto_expand_pipeline.bat` |
