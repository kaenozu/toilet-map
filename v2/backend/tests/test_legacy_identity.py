"""Tests for deterministic legacy stable-key collision handling."""

from __future__ import annotations

import pytest

from app.legacy_identity import resolve_stable_key_collisions


def _record(
    *,
    stable_key: str = "shared",
    latitude: float = 35.0,
    longitude: float = 139.0,
    marker: str = "a",
) -> dict[str, object]:
    return {
        "stable_key": stable_key,
        "name": "Public toilet",
        "address": "Same displayed address",
        "latitude": latitude,
        "longitude": longitude,
        "raw_payload": {"marker": marker},
    }


def test_unique_stable_key_is_preserved() -> None:
    record = _record(stable_key="unique")

    assert resolve_stable_key_collisions([record]) == [record]


def test_distinct_locations_receive_order_independent_keys() -> None:
    first = _record(latitude=35.0, longitude=139.0, marker="first")
    second = _record(latitude=35.001, longitude=139.001, marker="second")

    forward = resolve_stable_key_collisions([first, second])
    reverse = resolve_stable_key_collisions([second, first])

    forward_keys = {str(item["stable_key"]) for item in forward}
    reverse_keys = {str(item["stable_key"]) for item in reverse}
    assert forward_keys == reverse_keys
    assert len(forward_keys) == 2
    assert all(key.startswith("shared:location:") for key in forward_keys)


def test_exact_duplicate_payload_is_collapsed() -> None:
    duplicate = _record()

    resolved = resolve_stable_key_collisions([duplicate, dict(duplicate)])

    assert resolved == [duplicate]


def test_distinct_records_at_same_location_fail_explicitly() -> None:
    first = _record(marker="first")
    second = _record(marker="second")

    with pytest.raises(ValueError, match="same normalized location"):
        resolve_stable_key_collisions([first, second])
