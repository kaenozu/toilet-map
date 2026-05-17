"""
batch/graphql_schema.py
GraphQL schema for toilet-map using Strawberry.
Related: batch/api_server.py, data/toilets.db
"""
import sqlite3

import strawberry

from app_config import DB_PATH


@strawberry.type
class Toilet:
    place_id: str
    title: str | None = None
    lat: float | None = None
    lng: float | None = None
    score: float | None = None
    review_count: int = 0
    rating: float | None = None
    address: str | None = None
    prefecture: str | None = None


@strawberry.type
class Stats:
    total: int
    scored: int
    avg_score: float | None = None


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@strawberry.type
class Query:
    @strawberry.field
    def toilets(self, limit: int = 100, offset: int = 0, prefecture: str | None = None) -> list[Toilet]:
        conn = _get_db()
        if prefecture:
            cursor = conn.execute(
                "SELECT * FROM toilets WHERE prefecture = ? LIMIT ? OFFSET ?",
                (prefecture, limit, offset),
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM toilets LIMIT ? OFFSET ?", (limit, offset)
            )
        rows = [Toilet(**dict(row)) for row in cursor.fetchall()]
        conn.close()
        return rows

    @strawberry.field
    def toilet(self, place_id: str) -> Toilet | None:
        conn = _get_db()
        cursor = conn.execute("SELECT * FROM toilets WHERE place_id = ?", (place_id,))
        row = cursor.fetchone()
        conn.close()
        return Toilet(**dict(row)) if row else None

    @strawberry.field
    def stats(self) -> Stats:
        conn = _get_db()
        total = conn.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
        scored = conn.execute("SELECT COUNT(*) FROM toilets WHERE score IS NOT NULL").fetchone()[0]
        avg = conn.execute("SELECT AVG(score) FROM toilets WHERE score IS NOT NULL").fetchone()[0]
        conn.close()
        return Stats(total=total, scored=scored, avg_score=avg)


schema = strawberry.Schema(query=Query)
