"""Observation identity tests."""

from app.ingestion import observation_hash
from app.providers import NormalizedObservation


def test_observation_hash_is_payload_order_independent() -> None:
    first = NormalizedObservation("p", "1", "A", 1, 2, payload={"a": 1, "b": 2})
    second = NormalizedObservation("p", "1", "A", 1, 2, payload={"b": 2, "a": 1})
    assert observation_hash(first) == observation_hash(second)
