# API Reference

## FastAPI Endpoints

The API server runs on port 8080:

```bash
python batch/api_server.py
```

### `GET /health`
System health status with DB connection and data freshness.

### `GET /toilets`
List toilets with pagination. Query params: `limit` (default 100), `offset`.

### `GET /stats`
Summary statistics: total count, average score.

### `GET /docs`
Interactive OpenAPI documentation (Swagger UI).

## Streamlit Internals

- State is coordinated through `st.session_state` in the UI modules (`ui/sidebar.py`, `ui/query_params.py`, `ui/pagination.py`, `ui/plugin_api.py`)
- Caching via `st.cache_data` (data) and `st.cache_resource` (DB connection)
