"""
tests/test_api_server.py
batch/api_server.py の FastAPI エンドポイントテスト
"""
import sqlite3

import pytest
from fastapi.testclient import TestClient

SAMPLE_TOILETS = [
    {"title": "トイレA", "prefecture": "東京都", "toilet_score": 80, "address": "東京都新宿区", "category": "公園"},
    {"title": "トイレB", "prefecture": "大阪府", "toilet_score": 60, "address": "大阪市", "category": "コンビニ"},
    {"title": "トイレC", "prefecture": "東京都", "toilet_score": 30, "address": "東京都渋谷区", "category": "駅"},
]


@pytest.fixture
def client(monkeypatch):
    import api_server
    monkeypatch.setattr(api_server, "load_json", lambda _: {"toilets": SAMPLE_TOILETS})
    return TestClient(api_server.app)


class TestListToilets:
    def test_all(self, client):
        resp = client.get("/api/toilets")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert len(body["toilets"]) == 3

    def test_filter_by_prefecture(self, client):
        resp = client.get("/api/toilets?prefecture=東京都")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert all(t["prefecture"] == "東京都" for t in body["toilets"])

    def test_filter_by_score_range(self, client):
        resp = client.get("/api/toilets?min_score=40&max_score=100")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2

    def test_limit_and_offset(self, client):
        resp = client.get("/api/toilets?limit=1&offset=1")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["toilets"]) == 1
        assert body["toilets"][0]["title"] == "トイレB"

    def test_empty_results(self, client):
        resp = client.get("/api/toilets?prefecture=北海道")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0

    def test_invalid_limit_rejected(self, client):
        resp = client.get("/api/toilets?limit=2000")
        assert resp.status_code == 422


class TestGetToilet:
    def test_found(self, client):
        resp = client.get("/api/toilets/0")
        assert resp.status_code == 200
        assert resp.json()["title"] == "トイレA"

    def test_not_found(self, client):
        resp = client.get("/api/toilets/999")
        assert resp.status_code == 404
        assert resp.json() == {"error": "not found"}

    def test_negative_id(self, client):
        resp = client.get("/api/toilets/-1")
        assert resp.status_code == 404


class TestStats:
    def test_basic(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert body["scored"] == 3
        assert "東京都" in body["prefectures"]

    def test_empty_data(self, monkeypatch):
        import api_server
        monkeypatch.setattr(api_server, "load_json", lambda _: {"toilets": []})
        c = TestClient(api_server.app)
        resp = c.get("/api/stats")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


class TestSearchToilets:
    def test_search_by_query(self, client):
        resp = client.get("/api/toilets?q=トイレA")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["toilets"][0]["title"] == "トイレA"

    def test_search_no_match(self, client):
        resp = client.get("/api/toilets?q=存在しない")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_search_multi_word(self, client):
        resp = client.get("/api/toilets?q=トイレA 新宿")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["toilets"][0]["title"] == "トイレA"


class TestScoreDistribution:
    def test_score_distribution(self, client):
        resp = client.get("/api/stats/distribution")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert len(body["distribution"]) == 5

    def test_score_distribution_empty(self, monkeypatch):
        import api_server
        monkeypatch.setattr(api_server, "load_json", lambda _: {"toilets": []})
        c = TestClient(api_server.app)
        resp = c.get("/api/stats/distribution")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


class TestHealthCheck:
    def test_health_ok(self, tmp_path, monkeypatch):
        import api_server

        db_path = tmp_path / "toilets.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE toilets (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO metadata (key, value) VALUES ('last_updated', '2026-05-18 00:00:00')")
        conn.commit()
        conn.close()

        monkeypatch.setattr(api_server, "DB_PATH", str(db_path))
        monkeypatch.setattr(api_server.db_schema, "get_schema_version", lambda conn: "test-schema", raising=False)

        resp = TestClient(api_server.app).get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["db_connected"] is True
        assert body["toilet_count"] == 0
        assert body["schema_version"] == "test-schema"

    def test_health_failure_returns_503(self, monkeypatch):
        import api_server

        def fake_connect(*args, **kwargs):
            raise sqlite3.OperationalError("boom")

        monkeypatch.setattr(api_server.sqlite3, "connect", fake_connect)

        resp = TestClient(api_server.app).get("/health")
        assert resp.status_code == 503
        assert resp.json()["status"] == "error"
