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

- All state managed via `st.session_state` (see `ui/session_state.py`)
- Caching via `st.cache_data` (data) and `st.cache_resource` (DB connection)
