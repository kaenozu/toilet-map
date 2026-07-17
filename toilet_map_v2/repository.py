from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .database import connect, initialize


@dataclass(frozen=True, slots=True)
class DatabaseCounts:
    places: int
    toilets: int
    reviews: int
    rejections: int


class ToiletMapRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        initialize(self.path)

    def connect(self) -> sqlite3.Connection:
        return connect(self.path)

    def counts(self) -> DatabaseCounts:
        with self.connect() as connection:
            return DatabaseCounts(
                places=self._count(connection, "places"),
                toilets=self._count(connection, "toilets"),
                reviews=self._count(connection, "reviews"),
                rejections=self._count(connection, "migration_rejections"),
            )

    def get_toilet(self, toilet_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    toilets.id,
                    toilets.toilet_type,
                    toilets.score,
                    toilets.confidence,
                    toilets.review_count,
                    toilets.score_status,
                    toilets.scoring_version,
                    toilets.scored_at,
                    places.id AS place_id,
                    places.title,
                    places.category,
                    places.address,
                    places.latitude,
                    places.longitude,
                    places.external_url,
                    places.is_active
                FROM toilets
                JOIN places ON places.id = toilets.place_id
                WHERE toilets.id = ?
                """,
                (toilet_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def list_toilets(self, *, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        if offset < 0:
            raise ValueError("offset must be non-negative")

        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    toilets.id,
                    toilets.toilet_type,
                    toilets.score,
                    toilets.confidence,
                    toilets.review_count,
                    toilets.score_status,
                    toilets.scoring_version,
                    places.id AS place_id,
                    places.title,
                    places.category,
                    places.address,
                    places.latitude,
                    places.longitude,
                    places.external_url
                FROM toilets
                JOIN places ON places.id = toilets.place_id
                WHERE places.is_active = 1
                ORDER BY places.id, toilets.toilet_type
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _count(connection: sqlite3.Connection, table: str) -> int:
        allowed_tables = {"places", "toilets", "reviews", "migration_rejections"}
        if table not in allowed_tables:
            raise ValueError("unsupported table")
        row = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return int(row[0])
