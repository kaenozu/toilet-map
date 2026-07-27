"""
v2/backend/tests/integration/test_publish_pipeline.py

End-to-end integration tests for the legacy import -> validate -> resolve -> publish
pipeline running against a real PostgreSQL database.

Tests are marked `integration` + `slow` and skip automatically when
psycopg or a real PostgreSQL instance is unavailable.

Related: app/importer.py, app/worker.py, app/resolution.py, app/public_api.py
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from app.db import database
from app.importer import import_legacy
from app.worker import publish_dataset, validate_dataset

from .conftest import truncate_all

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def _make_fixture(*, extra: list[dict[str, object]] | None = None) -> Path:
    toilets: list[dict[str, object]] = [
        {
            "place_id": "it-1",
            "name": "Integration Test Toilet",
            "latitude": 35.6812,
            "longitude": 139.7671,
            "toilet_score": 85,
            "wheelchair": "yes",
            "changing_table": "yes",
            "opening_hours": "24/7",
            "reviews": ["いつも清潔で快適です", "車椅子でも使いやすい"],
        },
        {
            "place_id": "it-2",
            "name": "Second Test Facility",
            "latitude": 35.6820,
            "longitude": 139.7680,
            "toilet_score": 65,
            "wheelchair": "no",
            "reviews": ["普通のトイレ"],
        },
    ]
    if extra:
        toilets.extend(extra)
    path = Path("/tmp") / "toilet-map-it-fixture.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(
            {"metadata": {"snapshot_id": "it-test", "source": "ci"}, "toilets": toilets},
            handle,
        )
    return path


def _count(connection, query: str, params: list[object] | None = None) -> int:
    row = connection.execute(query, params or []).fetchone()
    if row is None:
        return 0
    values = list(row.values()) if isinstance(row, dict) else row
    return int(values[0])


class TestImport:
    """Each import test is independent — clean slate before each."""

    @pytest.fixture(autouse=True)
    def _clean(self, _schema: None) -> None:
        truncate_all()

    def test_import_creates_dataset_and_records(self, db) -> None:
        fixture = _make_fixture()
        dataset_id, count = import_legacy(fixture, source="it-test")
        assert count == 2
        places_count = _count(
            db,
            "SELECT count(*) FROM places WHERE dataset_version_id = %s",
            [dataset_id],
        )
        assert places_count == 2
        state = db.execute(
            "SELECT status::text FROM dataset_versions WHERE id = %s",
            [dataset_id],
        ).fetchone()
        assert state["status"] == "staging"

    def test_import_rejects_empty_fixture(self, db) -> None:
        path = Path("/tmp") / "toilet-map-empty.json.gz"
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump({"metadata": {}, "toilets": []}, handle)
        with pytest.raises(ValueError, match="no valid places"):
            import_legacy(path, source="it-empty")

    def test_import_rejects_missing_coordinates(self, db) -> None:
        path = Path("/tmp") / "toilet-map-no-coords.json.gz"
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump(
                {
                    "metadata": {},
                    "toilets": [
                        {"place_id": "bad-1", "name": "No Coords"},
                        {
                            "place_id": "bad-2",
                            "name": "Empty Coords",
                            "latitude": None,
                            "longitude": None,
                        },
                    ],
                },
                handle,
            )
        with pytest.raises(ValueError, match="no valid places"):
            import_legacy(path, source="it-bad")


class TestPipeline:
    """Full pipeline test — import, validate, guard, resolve, publish, verify."""

    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def _setup_and_teardown(cls, _schema: None) -> None:
        truncate_all()
        yield
        truncate_all()

    @pytest.fixture(scope="class")
    def dataset_id(self, _schema: None) -> int:
        fixture = _make_fixture()
        d_id, count = import_legacy(fixture, source="it-pipeline")
        assert count == 2
        return d_id

    def test_import_creates_data(self, dataset_id: int, db) -> None:
        places_count = _count(
            db,
            "SELECT count(*) FROM places WHERE dataset_version_id = %s",
            [dataset_id],
        )
        sources_count = _count(
            db,
            "SELECT count(*) FROM source_records WHERE dataset_version_id = %s",
            [dataset_id],
        )
        assert places_count == 2
        assert sources_count == 2

    def test_validate_succeeds(self, dataset_id: int) -> None:
        validate_dataset(dataset_id)
        with database() as connection:
            state = connection.execute(
                "SELECT status::text FROM dataset_versions WHERE id = %s",
                [dataset_id],
            ).fetchone()
        assert state["status"] == "validated"

    def test_resolve_and_publish(self, dataset_id: int) -> None:
        validate_dataset(dataset_id)
        publish_dataset(dataset_id)
        with database() as connection:
            state = connection.execute(
                "SELECT status::text FROM dataset_versions WHERE id = %s",
                [dataset_id],
            ).fetchone()
            assert state["status"] == "published"
            snapshots = _count(
                connection,
                "SELECT count(*) FROM published_place_snapshots WHERE dataset_version_id = %s",
                [dataset_id],
            )
            assert snapshots == 2

    def test_published_place_has_trust_score(self, dataset_id: int, db) -> None:
        snapshots = db.execute(
            """
            SELECT id, toilet_score, trust_score, source_count,
                   verification_status::text
              FROM published_place_snapshots
             WHERE dataset_version_id = %s
             ORDER BY id
            """,
            [dataset_id],
        ).fetchall()
        assert len(snapshots) == 2
        for row in snapshots:
            assert row["trust_score"] is not None
            assert row["source_count"] >= 1
            assert row["verification_status"] in ("unverified", "human_verified")

    def test_api_serves_published_places(self, dataset_id: int) -> None:
        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app) as client:
            resp = client.get("/api/v2/places?wheelchair=true&min_trust=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        names = [item["name"] for item in data["items"]]
        assert "Integration Test Toilet" in names


class TestMigrations:
    """Migration application and idempotency."""

    @pytest.fixture(autouse=True)
    def _clean(self, _schema: None) -> None:
        truncate_all()

    def test_all_migrations_applied(self, db) -> None:
        rows = db.execute(
            "SELECT version, name FROM schema_migrations ORDER BY version"
        ).fetchall()
        versions = [row["version"] for row in rows]
        assert versions == ["0001", "0002", "0003"]

    def test_reapply_is_idempotent(self) -> None:
        from app.db import apply_schema
        from app.migrations import migration_directory

        applied = apply_schema(migration_directory())
        assert applied == []


class TestV1Compatibility:
    """Verify v1 JSON field mapping survives import → publish unchanged."""

    @pytest.fixture(autouse=True)
    def _clean(self, _schema: None) -> None:
        truncate_all()

    @pytest.fixture(scope="class")
    def fixture_path(self) -> Path:
        toilets = [
            {
                "place_id": "gp-1001",
                "data_id": 42,
                "source_id": "src-001",
                "name": "V1 Compat Toilet",
                "address": "東京都千代田区丸の内1-9-1",
                "prefecture": "東京都",
                "category": "駅",
                "latitude": 35.6812,
                "longitude": 139.7671,
                "toilet_score": 83.5,
                "confidence": 0.92,
                "phone": "03-1234-5678",
                "rating": 4.2,
                "review_count": 15,
                "wheelchair": "yes",
                "changing_table": "no",
            },
            {
                "source_id": "src-002",
                "name": "No PlaceId Facility",
                "address": "埼玉県さいたま市大宮区",
                "prefecture": "埼玉県",
                "category": "公園",
                "latitude": 35.9067,
                "longitude": 139.6238,
                "toilet_score": 42.0,
                "confidence": 0.55,
            },
        ]
        path = Path("/tmp") / "toilet-map-v1-compat.json.gz"
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump(
                {"metadata": {"snapshot_id": "v1-compat-test"}, "toilets": toilets},
                handle,
            )
        return path

    @pytest.fixture(scope="class")
    def dataset_id(self, fixture_path: Path) -> int:
        d_id, count = import_legacy(fixture_path, source="v1-compat")
        assert count == 2
        return d_id

    def test_stable_key_preserves_place_id(self, dataset_id: int, db) -> None:
        rows = db.execute(
            "SELECT stable_key, name FROM places WHERE dataset_version_id = %s ORDER BY id",
            [dataset_id],
        ).fetchall()
        assert rows[0]["stable_key"] == "gp-1001"
        assert rows[0]["name"] == "V1 Compat Toilet"
        assert rows[1]["stable_key"] == "src-002"

    def test_stable_key_falls_back_through_source_id(self, dataset_id: int, db) -> None:
        rows = db.execute(
            "SELECT stable_key, name FROM places WHERE dataset_version_id = %s ORDER BY id",
            [dataset_id],
        ).fetchall()
        assert rows[1]["stable_key"] == "src-002"

    def test_score_preserved_after_import(self, dataset_id: int, db) -> None:
        rows = db.execute(
            "SELECT toilet_score::numeric(5,2) AS score FROM places WHERE dataset_version_id = %s ORDER BY id",
            [dataset_id],
        ).fetchall()
        assert float(rows[0]["score"]) == 83.5
        assert float(rows[1]["score"]) == 42.0

    def test_coordinates_preserved(self, dataset_id: int, db) -> None:
        rows = db.execute(
            """
            SELECT ST_Y(location::geometry) AS lat, ST_X(location::geometry) AS lng
              FROM places WHERE dataset_version_id = %s ORDER BY id
            """,
            [dataset_id],
        ).fetchall()
        assert abs(float(rows[0]["lat"]) - 35.6812) < 0.0001
        assert abs(float(rows[0]["lng"]) - 139.7671) < 0.0001
        assert abs(float(rows[1]["lat"]) - 35.9067) < 0.0001
        assert abs(float(rows[1]["lng"]) - 139.6238) < 0.0001

    def test_v1_fields_mapped_to_attributes(self, dataset_id: int, db) -> None:
        row = db.execute(
            "SELECT attributes::text FROM places WHERE dataset_version_id = %s ORDER BY id LIMIT 1",
            [dataset_id],
        ).fetchone()
        attrs = json.loads(row["attributes"])
        assert attrs.get("phone") == "03-1234-5678"
        assert attrs.get("rating") == 4.2
        assert attrs.get("wheelchair") == "yes"
        assert attrs.get("changing_table") == "no"

    def test_provider_records_compatibility(self, dataset_id: int, db) -> None:
        rows = db.execute(
            """
            SELECT pr.external_id, pr.provider, p.stable_key
              FROM provider_records pr
              JOIN places p ON p.id = pr.place_id
             WHERE pr.dataset_version_id = %s
             ORDER BY pr.id
            """,
            [dataset_id],
        ).fetchall()
        assert rows[0]["external_id"] == "src-001"
        assert rows[0]["stable_key"] == "gp-1001"
        assert rows[1]["external_id"] == "src-002"

    def test_published_snapshot_matches_v1_input(self, dataset_id: int, db) -> None:
        validate_dataset(dataset_id)
        publish_dataset(dataset_id)

        snapshots = db.execute(
            """
            SELECT stable_key, name, toilet_score::numeric(5,2) AS score,
                   ST_Y(location::geometry) AS lat, ST_X(location::geometry) AS lng,
                   prefecture, attributes::text AS attrs
              FROM published_place_snapshots
             WHERE dataset_version_id = %s
             ORDER BY id
            """,
            [dataset_id],
        ).fetchall()
        assert len(snapshots) == 2

        s0 = snapshots[0]
        assert s0["stable_key"] == "gp-1001"
        assert float(s0["score"]) == 83.5
        assert abs(float(s0["lat"]) - 35.6812) < 0.0001
        assert abs(float(s0["lng"]) - 139.7671) < 0.0001
        assert s0["prefecture"] == "東京都"

        s1 = snapshots[1]
        assert s1["stable_key"] == "src-002"
        assert float(s1["score"]) == 42.0
        assert abs(float(s1["lat"]) - 35.9067) < 0.0001
        assert abs(float(s1["lng"]) - 139.6238) < 0.0001
        assert s1["prefecture"] == "埼玉県"

    def test_reimport_is_idempotent(self, fixture_path: Path, dataset_id: int, db) -> None:
        d_id2, count2 = import_legacy(fixture_path, source="v1-compat-2")
        assert count2 == 2
        assert d_id2 != dataset_id

        for d_id in (dataset_id, d_id2):
            rows = db.execute(
                "SELECT stable_key, toilet_score::numeric(5,2) FROM places WHERE dataset_version_id = %s ORDER BY id",
                [d_id],
            ).fetchall()
            assert rows[0]["stable_key"] == "gp-1001"
            assert float(rows[0]["toilet_score"]) == 83.5
            assert rows[1]["stable_key"] == "src-002"
            assert float(rows[1]["toilet_score"]) == 42.0


class TestAPI:
    """API behaviour without published data (empty state)."""

    @pytest.fixture(autouse=True)
    def _clean(self, _schema: None) -> None:
        truncate_all()

    def test_health(self) -> None:
        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app) as client:
            resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_stats_empty_when_no_published_data(self) -> None:
        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app) as client:
            resp = client.get("/api/v2/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["record_count"] == 0

    def test_places_empty_when_no_published_data(self) -> None:
        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app) as client:
            resp = client.get("/api/v2/places")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []
