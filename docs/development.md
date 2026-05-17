# Development

## Setup

```bash
git clone https://github.com/kaenozu/toilet-map.git
cd toilet-map
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Commands

```bash
streamlit run app.py          # Run app
pytest tests/ -v              # Run all tests
ruff check .                  # Lint
pip-audit -r requirements.txt # Security audit
```

## Conventions

- One file, one responsibility (≤300 lines)
- Header comments required on all files
- Type hints required on all functions
- Test coverage ≥ 90%

## Project Structure

```
toilet-map/
├── app.py               # Streamlit entry point
├── app_config.py        # Default constants
├── app_settings.py      # Pydantic Settings
├── batch/               # Data processing
│   ├── api_server.py    # FastAPI server
│   ├── scoring.py       # Review scoring
│   ├── schema.py        # DB versioning
│   └── models.py        # Pydantic models
├── ui/                  # UI modules
│   ├── sidebar.py       # Sidebar controls
│   ├── map_builder.py   # Map construction
│   ├── filters.py       # Search/filter logic
│   └── ...
├── static/              # Static assets (CSS, JS, PWA)
├── data/                # Data files (git-tracked: JSON)
├── tests/               # All tests
│   ├── e2e/             # Playwright E2E
│   └── load/            # Locust load tests
└── docs/                # Documentation
```
