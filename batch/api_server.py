"""
batch/api_server.py
FastAPI server with CORS, rate limiting, API key auth, and GraphQL.
Related: app_settings.py, data/toilets.db, batch/graphql_schema.py
"""
import logging
import os
import re
import sqlite3
from collections import Counter
from contextlib import asynccontextmanager

from db_utils import load_json
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app_config import DB_PATH
from app_settings import settings
from batch import schema as db_schema

logger = logging.getLogger(__name__)

try:
    from strawberry.fastapi import GraphQLRouter

    from batch.graphql_schema import schema as graphql_schema
except Exception as exc:  # pragma: no cover - optional dependency fallback
    GraphQLRouter = None
    graphql_schema = None
    logger.warning("GraphQL disabled: %s", exc)

limiter = Limiter(key_func=get_remote_address)

API_KEY = os.environ.get("TOILET_MAP_API_KEY", "")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(api_key_header)):
    """Verify API key if configured. If no key set, allow all requests."""
    if not API_KEY:
        return True
    if api_key == API_KEY:
        return True
    raise HTTPException(status_code=403, detail="Invalid API key")


DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "toilets.json.gz")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Toilet Map API",
    description="API for toilet cleanliness map data",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GraphQL
if GraphQLRouter and graphql_schema:
    graphql_app = GraphQLRouter(graphql_schema)
    app.include_router(
        graphql_app,
        prefix="/graphql",
        tags=["GraphQL"],
        dependencies=[Depends(verify_api_key)],
    )


def _custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Toilet Map API",
        version="1.0.0",
        description="API for toilet cleanliness map data",
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = _custom_openapi


@app.get("/health", tags=["System"])
@limiter.limit(settings.api_rate_limit)
def health_check(request: Request):
    """Return system health status."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            count = conn.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
            row = conn.execute("SELECT value FROM metadata WHERE key='last_updated'").fetchone()
            last_updated = row[0] if row else None
            schema_version = db_schema.get_schema_version(conn) if hasattr(db_schema, 'get_schema_version') else "unknown"
        return {
            "status": "ok",
            "db_connected": True,
            "toilet_count": count,
            "last_updated": last_updated,
            "schema_version": schema_version,
        }
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "error", "detail": str(e)})


@app.get("/api/toilets", tags=["toilets"], summary="トイレ一覧を取得", response_model=dict)
@limiter.limit(settings.api_rate_limit)
def list_toilets(
    request: Request,
    prefecture: str = Query(None, description="Filter by prefecture name"),
    min_score: float = Query(0.0, description="Minimum toilet score filter"),
    max_score: float = Query(100.0, description="Maximum toilet score filter"),
    q: str = Query(None, description="Search query (name, address, category)"),
    limit: int = Query(100, le=1000, description="Max results per page"),
    offset: int = Query(0, description="Result offset for pagination"),
):
    """Return a paginated list of toilets with optional filtering by prefecture, score range, and text search."""
    data = load_json(DATA_PATH)
    toilets = data.get("toilets", [])
    if prefecture:
        toilets = [t for t in toilets if t.get("prefecture") == prefecture]
    toilets = [t for t in toilets if min_score <= t.get("toilet_score", 0) <= max_score]
    if q:
        words = [w.lower() for w in re.split(r"[\s,、]+", q.strip()) if w]
        if words:
            filtered = []
            for t in toilets:
                target = (t.get("title", "") + t.get("address", "") + t.get("category", "")).lower()
                if all(w in target for w in words):
                    filtered.append(t)
            toilets = filtered
    return {"total": len(toilets), "toilets": toilets[offset:offset + limit]}


@app.get("/api/toilets/{toilet_id}", tags=["toilets"], summary="個別トイレを取得", response_model=dict)
@limiter.limit(settings.api_rate_limit)
def get_toilet(request: Request, toilet_id: int = None):
    """Return a single toilet by its index (0-based position in the dataset)."""
    data = load_json(DATA_PATH)
    toilets = data.get("toilets", [])
    if 0 <= toilet_id < len(toilets):
        return toilets[toilet_id]
    return JSONResponse(content={"error": "not found"}, status_code=404)


@app.get("/api/stats", tags=["stats"], summary="全体統計を取得", response_model=dict)
@limiter.limit(settings.api_rate_limit)
def stats(request: Request):
    """Return aggregate statistics: total toilets, scored count, average score, and per-prefecture breakdown."""
    data = load_json(DATA_PATH)
    toilets = data.get("toilets", [])
    pref_counts = Counter(t.get("prefecture", "不明") for t in toilets)
    scores = [t.get("toilet_score", 0) for t in toilets]
    avg_score = sum(scores) / len(scores) if scores else 0
    return {
        "total": len(toilets),
        "scored": sum(1 for s in scores if s > 0),
        "avg_score": round(avg_score, 1),
        "prefectures": dict(pref_counts.most_common()),
    }


@app.get("/api/stats/distribution", tags=["stats"], summary="スコア分布を取得", response_model=dict)
@limiter.limit(settings.api_rate_limit)
def score_distribution(request: Request):
    """Return score distribution across predefined buckets (0-34, 35-49, 50-64, 65-79, 80-100)."""
    data = load_json(DATA_PATH)
    toilets = data.get("toilets", [])
    scored = [t for t in toilets if t.get("toilet_score", 0) > 0]
    if not scored:
        return {"total": 0, "distribution": []}
    buckets = [
        (80, 101, "80-100"), (65, 80, "65-79"), (50, 65, "50-64"),
        (35, 50, "35-49"), (0, 35, "0-34"),
    ]
    distribution = []
    for lo, hi, label in buckets:
        count = sum(1 for t in scored if lo <= t["toilet_score"] < hi)
        distribution.append({"label": label, "count": count, "pct": round(count / len(scored) * 100, 1)})
    return {"total": len(scored), "distribution": distribution}
