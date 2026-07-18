"""Stable identity helpers shared by the scrape, JSON and SQLite layers."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping


def normalize_identity_text(value: object) -> str:
    """Normalize user-visible identity text without making locale assumptions."""
    return re.sub(r"\s+", "", str(value or "")).lower()


def build_fallback_source_id(
    record: Mapping[str, object],
    *,
    lat: float | None = None,
    lng: float | None = None,
) -> str:
    """Return the deterministic title/address/coordinate identity."""
    if lat is None:
        try:
            raw_lat = record.get("lat") if record.get("lat") is not None else record.get("latitude")
            lat = float(raw_lat)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            lat = None
    if lng is None:
        raw_lng = record.get("lng")
        if raw_lng is None:
            raw_lng = record.get("longitude")
        if raw_lng is None:
            raw_lng = record.get("longtitude")
        try:
            lng = float(raw_lng)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            lng = None

    title = normalize_identity_text(record.get("title"))
    address = normalize_identity_text(record.get("address"))
    coordinate_part = ""
    if lat is not None and lng is not None:
        coordinate_part = f"{lat:.6f},{lng:.6f}"
    payload = f"{title}|{address}|{coordinate_part}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"fallback:{digest}"


def build_source_id(
    record: Mapping[str, object],
    *,
    lat: float | None = None,
    lng: float | None = None,
) -> str:
    """Return a stable ID, preferring provider IDs and using a deterministic fallback."""
    existing = str(record.get("source_id") or "").strip()
    if existing:
        return existing

    place_id = str(record.get("place_id") or "").strip()
    if place_id:
        return f"place_id:{place_id}"

    data_id = str(record.get("data_id") or "").strip()
    if data_id:
        return f"data_id:{data_id}"

    return build_fallback_source_id(record, lat=lat, lng=lng)
