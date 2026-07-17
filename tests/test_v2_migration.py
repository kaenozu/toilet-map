from __future__ import annotations

import json

from toilet_map_v2.database import connect
from toilet_map_v2.migration import migrate
from toilet_map_v2.repository import ToiletMapRepository


def test_idempotent_and_distinct_same_coordinates(tmp_path) -> None:
    source = tmp_path / "legacy.json"
    database = tmp_path / "v2.db"
    source.write_text(
        json.dumps(
            [
                {
                    "place_id": "a",
                    "title": "A",
                    "latitude": 35,
                    "longitude": 139,
                    "toilet_score": 88,
                    "toilet_reviews_count": 3,
                    "reviews": [{"text": "clean"}],
                },
                {
                    "place_id": "b",
                    "title": "B",
                    "latitude": 35,
                    "longitude": 139,
                    "toilet_score": 70,
                    "toilet_reviews_count": 1,
                    "reviews": [{"text": "ok"}],
                },
            ]
        ),
        encoding="utf-8",
    )

    assert migrate(source, database).reviews_inserted == 2
    repository = ToiletMapRepository(database)
    assert repository.counts().places == 2
    assert repository.counts().toilets == 2
    assert repository.counts().reviews == 2

    second = migrate(source, database)
    assert repository.counts().places == 2
    assert repository.counts().toilets == 2
    assert repository.counts().reviews == 2
    assert second.duplicate_reviews == 2


def test_unrated_null_and_rejections(tmp_path) -> None:
    source = tmp_path / "legacy.json"
    database = tmp_path / "v2.db"
    report_path = tmp_path / "reports" / "migration.json"
    source.write_text(
        json.dumps(
            [
                {
                    "title": "park",
                    "lat": 36.1,
                    "lng": 139.4,
                    "score": 50,
                    "review_count": 0,
                },
                {"title": "bad", "lat": "NaN", "lng": 139.4},
                {"lat": 36.1, "lng": 139.4},
            ]
        ),
        encoding="utf-8",
    )

    result = migrate(source, database, report_path)
    with connect(database) as connection:
        score, status = connection.execute(
            "SELECT score, score_status FROM toilets"
        ).fetchone()
        rejection_count = connection.execute(
            "SELECT COUNT(*) FROM migration_rejections"
        ).fetchone()[0]

    assert score is None
    assert status == "unrated"
    assert rejection_count == 2
    assert result.rejection_reasons == {
        "invalid_coordinates": 1,
        "missing_title": 1,
    }
    assert json.loads(report_path.read_text(encoding="utf-8"))["rejected_count"] == 2


def test_migration_populates_all_required_v2_columns(tmp_path) -> None:
    source = tmp_path / "legacy.json"
    database = tmp_path / "v2.db"
    source.write_text(
        json.dumps(
            [
                {
                    "data_id": "upstream-1",
                    "name": "Central Park",
                    "lat": 35.0,
                    "lon": 139.0,
                    "url": "https://example.invalid/place",
                    "rating": 4.2,
                    "reviews_count": 12,
                    "toilet_score": 90,
                    "toilet_reviews_count": 4,
                    "reviews": [
                        {
                            "id": "review-1",
                            "text": "Clean toilet",
                            "stars": 5,
                            "published_at": "2026-01-01T00:00:00+00:00",
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    migrate(source, database)
    repository = ToiletMapRepository(database)
    toilets = repository.list_toilets()

    assert len(toilets) == 1
    assert toilets[0]["title"] == "Central Park"
    assert toilets[0]["score_status"] == "rated"
    assert toilets[0]["external_url"] == "https://example.invalid/place"

    with connect(database) as connection:
        assert connection.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'"
        ).fetchone()[0] == "1"
        place = connection.execute("SELECT * FROM places").fetchone()
        toilet = connection.execute("SELECT * FROM toilets").fetchone()
        review = connection.execute("SELECT * FROM reviews").fetchone()

    assert place["first_seen_at"]
    assert place["last_seen_at"]
    assert place["is_active"] == 1
    assert toilet["toilet_type"] == "unknown"
    assert toilet["scored_at"]
    assert review["collected_at"]
    assert review["is_toilet_related"] == 1
