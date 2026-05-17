# Data Pipeline

## Flow

```
Scraper (Docker/gosom) → raw JSONL → process_data.py → toilets.json.gz → to_sqlite.py → toilets.db
```

## Automation

```bash
cd batch && auto_expand_pipeline.bat
```

Stages:
1. Data gap analysis
2. Docker scraping
3. Process + merge
4. Quality verification
5. Cleanup

## Scoring

Score = (raw_score + 5) × 10  (range: -5 to +5 → 0 to 100)
