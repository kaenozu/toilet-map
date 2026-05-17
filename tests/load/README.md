# Load Testing

Run with:
```bash
pip install locust
locust -f tests/load/locustfile.py --host http://localhost:8501
```

Then open http://localhost:8089 in browser.

## Scenarios
- `/health`: lightweight check (weight 1)
- `/`: full page load (weight 3)

## Metrics to watch
- Response time < 500ms (p95)
- Error rate < 1%
