# Getting Started

## Quick Start

```bash
git clone https://github.com/kaenozu/toilet-map.git
cd toilet-map
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501 in your browser.

## Docker

```bash
docker build -t toilet-map .
docker run -p 8501:8501 toilet-map
```

## Development

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
pytest tests/e2e tests/visual -q
python scripts/update_screenshot_baselines.py
python -m playwright install chromium
ruff check .
```
