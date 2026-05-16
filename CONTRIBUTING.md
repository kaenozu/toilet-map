# Contributing

## Setup

```bash
git clone <repo>
cd toilet-map
pip install -r requirements.txt
pre-commit install
```

## Development

```bash
# Run app
streamlit run app.py

# Run tests
pytest tests/ -v

# Run lint
ruff check .

# Run type check
mypy app.py app_config.py ui/ --ignore-missing-imports --follow-imports=silent

# Run pre-commit hooks
pre-commit run --all-files
```

## Project Structure

- `app.py` — Streamlit entry point
- `ui/` — UI components (sidebar, map, filters, i18n, etc.)
- `batch/` — Data processing pipeline (scraping, scoring, SQLite sync)
- `data/` — Canonical JSON + SQLite cache
- `tests/` — pytest test suite

## Pull Request Guidelines

1. Create a feature branch from `main`
2. Add tests for new functionality
3. Ensure all tests pass: `pytest tests/ -v`
4. Ensure ruff is clean: `ruff check .`
5. Open PR against `main`

## Code Style

- 1 file, 1 responsibility, max ~300 lines
- Type hints on all public functions
- Docstrings on all modules and public functions
- No unnecessary abstraction (YAGNI)
