"""FastAPI endpoint tests against a temporary SQLite snapshot."""

import sqlite3

import api_server
import db_utils
import pytest
from fastapi.testclient import TestClient

SAMPLE_TOILETS = [
    {
        "source_id": "place_id:a", "title": "トイレA 100%", "prefecture": "東京都",
        "toilet_score": 80, "address": "東京都新宿区_A", "category": "公園",
        "lat": 35.68, "lng": 139.69, "phone": "03", "rating": 4.0,
        "review_count": 10, "link": "https://maps.example/a", "is_public_toilet": True,
        "confidence": 0.8, "toilet_review_count": 2, "sample_reviews": [], "top_keywords": [],
    },
    {
        "source_id": "place_id:b", "title": "トイレB", "prefecture": "大阪府",
        "toilet_score": 60, "address": "大阪市", "category": "コンビニ",
        "lat": 34.69, "lng": 135.50, "phone": "", "rating": 3.0,
        "review_count": 5, "link": "", "is_public_toilet": False,
        "confidence": 0.5, "toilet_review_count": 1, "sample_reviews": [], "top_keywords": [],
    },
    {
        "source_id": "place_id:c", "title": "トイレC", "prefecture": "東京都",
        "toilet_score": 30, "address": "東京都渋谷区", "category": "駅",
        "lat": 35.70, "lng": 139.70, "phone": "", "rating": 2.0,
        "review_count": 2, "link": "", "is_public_toilet": True,
        "confidence": 0.2, "toilet_review_count": 1, "sample_reviews": [], "top_keywords": [],
    },
]


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "toilets.db"
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    db_utils.ensure_schema(cursor)
    db_utils.upsert_toilets(cursor, SAMPLE_TOILETS)
    db_utils.update_metadata_from_db(connection)
    connection.commit()
    connection.close()
    monkeypatch.setattr(api_server, "DB_PATH", str(db_path))
    monkeypatch.setattr(api_server, "JSON_PATH", str(tmp_path / "missing.json.gz"))
    monkeypatch.setattr(api_server, "ensure_database_current", lambda *_: None)
    return TestClient(api_server.app)


class TestListToilets:
    def test_all(self, client):
        response = client.get("/api/toilets")
        assert response.status_code == 200
        assert response.json()["total"] == 3

    def test_filter_by_prefecture(self, client):
        body = client.get("/api/toilets?prefecture=東京都").json()
        assert body["total"] == 2
        assert all(item["prefecture"] == "東京都" for item in body["toilets"])

    def test_filter_by_score_range(self, client):
        assert client.get("/api/toilets?min_score=40&max_score=100").json()["total"] == 2

    def test_limit_and_offset(self, client):
        body = client.get("/api/toilets?limit=1&offset=1").json()
        assert len(body["toilets"]) == 1
        assert body["toilets"][0]["source_id"] == "place_id:b"

    def test_empty_results(self, client):
        assert client.get("/api/toilets?prefecture=北海道").json()["total"] == 0

    def test_invalid_pagination_rejected(self, client):
        assert client.get("/api/toilets?limit=2000").status_code == 422
        assert client.get("/api/toilets?limit=0").status_code == 422
        assert client.get("/api/toilets?offset=-1").status_code == 422

    def test_reversed_score_range_rejected(self, client):
        assert client.get("/api/toilets?min_score=90&max_score=10").status_code == 422


class TestGetToilet:
    def test_stable_source_id_found(self, client):
        response = client.get("/api/toilets/place_id:a")
        assert response.status_code == 200
        assert response.json()["title"] == "トイレA 100%"

    def test_not_found(self, client):
        response = client.get("/api/toilets/place_id:missing")
        assert response.status_code == 404
        assert response.json()["detail"] == "not found"

    def test_numeric_database_position_is_not_public_id(self, client):
        assert client.get("/api/toilets/1").status_code == 404


class TestSearchToilets:
    def test_search_by_query(self, client):
        body = client.get("/api/toilets?q=トイレA").json()
        assert body["total"] == 1

    def test_search_no_match(self, client):
        assert client.get("/api/toilets?q=存在しない").json()["total"] == 0

    def test_multi_word_uses_and_semantics(self, client):
        body = client.get("/api/toilets?q=トイレA 新宿").json()
        assert body["total"] == 1
        assert body["toilets"][0]["source_id"] == "place_id:a"

    def test_like_wildcards_are_literal(self, client):
        assert client.get("/api/toilets?q=%").json()["total"] == 1
        assert client.get("/api/toilets?q=_A").json()["total"] == 1


class TestStats:
    def test_basic(self, client):
        body = client.get("/api/stats").json()
        assert body["total"] == 3
        assert body["scored"] == 3
        assert body["prefectures"]["東京都"] == 2

    def test_score_distribution(self, client):
        body = client.get("/api/stats/distribution").json()
        assert body["total"] == 3
        assert len(body["distribution"]) == 5
        assert sum(bucket["count"] for bucket in body["distribution"]) == 3
