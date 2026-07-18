"""Regression coverage for the full-source review fixes."""

import gzip
import json
import os
import sqlite3

import db_utils
import pandas as pd
import process_data
import scoring
import to_sqlite
import utils

from ui.filters import search_toilets


def _place(**overrides):
    value = {
        "place_id": "abc",
        "title": "テストトイレ",
        "category": "公共トイレ",
        "address": "東京都千代田区",
        "latitude": 35.0,
        "longitude": 139.0,
        "phone": "03-0000-0000",
        "review_rating": 4.0,
        "review_count": 10,
        "link": "https://maps.example/a",
        "user_reviews": [{"Description": "トイレがきれい", "Rating": 5}],
    }
    value.update(overrides)
    return value


def _toilet(source_id="place_id:1", title="A"):
    return {
        "source_id": source_id,
        "title": title,
        "category": "公園",
        "address": "東京都千代田区",
        "lat": 35.0,
        "lng": 139.0,
        "phone": "03-0000-0000",
        "rating": 4.0,
        "review_count": 10,
        "link": "https://maps.example/a",
        "is_public_toilet": True,
        "toilet_score": 80.0,
        "confidence": 0.8,
        "toilet_review_count": 2,
        "prefecture": "東京都",
        "sample_reviews": [],
        "top_keywords": [],
    }


def test_complete_negative_phrases_are_not_self_negated():
    for text in ["トイレが使えない", "トイレは紙がない", "トイレが掃除されていない"]:
        score, _ = scoring.score_toilet_from_review(text)
        assert score < 0


def test_complete_positive_phrase_with_internal_negation_scores_positive():
    score, matched = scoring.score_toilet_from_review("トイレは匂いがしない")
    assert score > 0
    assert "+匂いがしない" in matched


def test_external_negation_does_not_leak_to_later_keyword():
    score, matched = scoring.score_toilet_from_review("トイレは清潔ではないが広い")
    assert score > 0
    assert "+清潔" not in matched
    assert "+広い" in matched


def test_english_toilet_at_sentence_start_is_detected():
    assert scoring.mentions_toilet("Restroom is clean")
    assert scoring.mentions_toilet("Bathroom was dirty")


def test_invalid_external_numbers_do_not_crash():
    result = process_data.process_place(_place(review_rating="bad", review_count="bad"))
    assert result is not None
    assert result["rating"] == 0.0
    assert result["review_count"] == 0


def test_provider_identity_phone_and_link_survive_processing():
    result = process_data.process_place(_place())
    assert result is not None
    assert result["source_id"] == "place_id:abc"
    assert result["phone"] == "03-0000-0000"
    assert result["link"] == "https://maps.example/a"


def test_same_coordinates_with_different_provider_ids_survive_sqlite():
    connection = sqlite3.connect(":memory:")
    cursor = connection.cursor()
    db_utils.ensure_schema(cursor)
    db_utils.upsert_toilets(cursor, [_toilet("place_id:1", "A"), _toilet("place_id:2", "B")])
    assert cursor.execute("SELECT COUNT(*) FROM toilets").fetchone()[0] == 2


def test_canonical_records_without_provider_id_get_distinct_fallback_ids(tmp_path):
    first = _toilet("", "A")
    second = _toilet("", "B")
    json_path = tmp_path / "data.json.gz"
    with gzip.open(json_path, "wt", encoding="utf-8") as file:
        json.dump({"metadata": {}, "toilets": [first, second]}, file)
    db_path = tmp_path / "data.db"
    assert to_sqlite._convert_core(str(json_path), str(db_path), False) == 2


def test_search_treats_regex_and_like_characters_literally_and_uses_and():
    frame = pd.DataFrame([
        {"title": "東京 [100%]", "address": "東京都港区_A", "category": "公園", "toilet_score": 80},
        {"title": "東京駅", "address": "東京都千代田区", "category": "駅", "toilet_score": 60},
    ])
    assert list(search_toilets(frame, "[")["title"]) == ["東京 [100%]"]
    assert list(search_toilets(frame, "東京 港区")["title"]) == ["東京 [100%]"]


def test_atomic_gzip_save(tmp_path):
    path = tmp_path / "data.json.gz"
    utils.save_json(str(path), {"ok": True}, compress=True)
    with gzip.open(path, "rt", encoding="utf-8") as file:
        assert json.load(file) == {"ok": True}
    assert not list(tmp_path.glob("*.tmp"))


def test_posix_file_lock_module_is_available():
    if os.name != "nt":
        assert utils.fcntl is not None
