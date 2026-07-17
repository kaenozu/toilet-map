from __future__ import annotations

import re
import unicodedata
from uuid import NAMESPACE_URL, uuid5

_SPACE = re.compile(r"\s+")


def normalize(value: object | None) -> str:
    normalized = unicodedata.normalize("NFKC", "" if value is None else str(value))
    return _SPACE.sub(" ", normalized.strip().casefold())


def build_place_id(
    *,
    source: str,
    source_place_id: str | None,
    title: str,
    address: str | None,
    latitude: float,
    longitude: float,
    data_id: str | None = None,
) -> str:
    source_key = normalize(source)
    if not source_key:
        raise ValueError("source is required")

    upstream_id = normalize(source_place_id) or normalize(data_id)
    if upstream_id:
        identity = f"{source_key}:upstream:{upstream_id}"
    else:
        title_key = normalize(title)
        if not title_key:
            raise ValueError("title is required when no upstream ID exists")
        identity = (
            f"{source_key}:fallback:{title_key}:{normalize(address)}:"
            f"{latitude:.6f}:{longitude:.6f}"
        )
    return str(uuid5(NAMESPACE_URL, identity))


def build_toilet_id(place_id: str, toilet_type: str = "unknown") -> str:
    return str(uuid5(NAMESPACE_URL, f"toilet:{place_id}:{normalize(toilet_type)}"))


def build_review_id(
    place_id: str,
    *,
    source_review_id: str | None,
    content_hash: str,
) -> str:
    review_identity = normalize(source_review_id) or normalize(content_hash)
    if not review_identity:
        raise ValueError("source_review_id or content_hash is required")
    return str(uuid5(NAMESPACE_URL, f"review:{place_id}:{review_identity}"))
