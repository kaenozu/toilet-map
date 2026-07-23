"""Resolve ambiguous legacy stable keys without dropping distinct facilities."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable
from typing import Any


def _raw_payload_fingerprint(record: dict[str, Any]) -> str:
    canonical = json.dumps(
        record["raw_payload"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _location_disambiguator(record: dict[str, Any]) -> str:
    canonical = "|".join(
        (
            str(record["name"]),
            str(record["address"]),
            f"{float(record['latitude']):.7f}",
            f"{float(record['longitude']):.7f}",
        )
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def resolve_stable_key_collisions(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return import records with deterministic, collision-free stable keys.

    Exact duplicate payloads are collapsed. Distinct records sharing a legacy key
    receive location-derived suffixes so input ordering cannot change identity.
    Ambiguous records at the same normalized location fail explicitly rather than
    being silently overwritten.
    """
    items = list(records)
    groups: dict[str, list[int]] = defaultdict(list)
    for index, item in enumerate(items):
        groups[str(item["stable_key"])].append(index)

    skipped: set[int] = set()
    replacements: dict[int, str] = {}
    for stable_key, indexes in groups.items():
        if len(indexes) < 2:
            continue

        unique_indexes: list[int] = []
        seen_payloads: set[str] = set()
        for index in indexes:
            fingerprint = _raw_payload_fingerprint(items[index])
            if fingerprint in seen_payloads:
                skipped.add(index)
                continue
            seen_payloads.add(fingerprint)
            unique_indexes.append(index)

        if len(unique_indexes) < 2:
            continue

        seen_locations: set[str] = set()
        for index in unique_indexes:
            suffix = _location_disambiguator(items[index])
            if suffix in seen_locations:
                raise ValueError(
                    f"stable key {stable_key!r} maps multiple distinct records "
                    "to the same normalized location"
                )
            seen_locations.add(suffix)
            replacements[index] = f"{stable_key}:location:{suffix}"

    return [
        {**item, "stable_key": replacements.get(index, str(item["stable_key"]))}
        for index, item in enumerate(items)
        if index not in skipped
    ]
