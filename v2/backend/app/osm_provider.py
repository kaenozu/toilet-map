"""Bounded OpenStreetMap toilet ingestion adapter."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .providers import (
    FetchRequest,
    NormalizedObservation,
    Provenance,
    RawRecord,
    SourceType,
    VerificationStatus,
)

UrlOpener = Callable[[Request, float], bytes]


def _default_url_opener(request: Request, timeout: float) -> bytes:
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - endpoint is configured by the operator.
        return response.read()


class OsmOverpassProvider:
    """Fetch a bounded toilet dataset from Overpass without deciding facility identity."""

    name = "openstreetmap-overpass"
    source_type = SourceType.OPENSTREETMAP

    def __init__(
        self,
        endpoint: str = "https://overpass-api.de/api/interpreter",
        *,
        opener: UrlOpener = _default_url_opener,
        timeout_seconds: float = 30,
    ) -> None:
        self.endpoint = endpoint
        self.opener = opener
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def query_for(request: FetchRequest) -> str:
        if request.bbox is None:
            raise ValueError("OSM discovery requires a bounded bbox")
        south, west, north, east = request.bbox
        bbox = f"{south},{west},{north},{east}"
        return (
            "[out:json][timeout:25];("
            f'node["amenity"="toilets"]({bbox});'
            f'way["amenity"="toilets"]({bbox});'
            f'relation["amenity"="toilets"]({bbox});'
            ");out center tags;"
        )

    def discover(self, request: FetchRequest) -> Iterable[RawRecord]:
        body = urlencode({"data": self.query_for(request)}).encode("utf-8")
        response = self.opener(
            Request(
                self.endpoint,
                data=body,
                headers={"User-Agent": "toilet-map/2.0 (+https://github.com/kaenozu/toilet-map)"},
                method="POST",
            ),
            self.timeout_seconds,
        )
        payload = json.loads(response.decode("utf-8"))
        elements = payload.get("elements", []) if isinstance(payload, dict) else []
        for element in elements:
            if not isinstance(element, dict):
                continue
            osm_type = str(element.get("type") or "")
            osm_id = element.get("id")
            if osm_type not in {"node", "way", "relation"} or osm_id is None:
                continue
            yield RawRecord(self.name, f"{osm_type}/{osm_id}", element)

    def _tags(self, payload: dict[str, object]) -> dict[str, object]:
        raw = payload.get("tags")
        return raw if isinstance(raw, dict) else {}

    def _center(self, payload: dict[str, object]) -> dict[str, object]:
        raw = payload.get("center")
        return raw if isinstance(raw, dict) else {}

    @staticmethod
    def _coord(payload: dict[str, object], center: dict[str, object]) -> tuple[float, float] | None:
        lat: Any = payload.get("lat")
        lon: Any = payload.get("lon")
        if lat is None or lon is None:
            lat = center.get("lat")
            lon = center.get("lon")
        if lat is None or lon is None:
            return None
        try:
            return float(lat), float(lon)
        except (TypeError, ValueError):
            return None

    def normalize(self, record: RawRecord) -> NormalizedObservation | None:
        payload = record.payload
        tags = self._tags(payload)
        center = self._center(payload)
        coords = self._coord(payload, center)
        if coords is None:
            return None
        lat, lon = coords
        name = str(tags.get("name") or tags.get("operator") or "公衆トイレ").strip()
        address_parts = [
            str(tags.get("addr:province") or ""),
            str(tags.get("addr:city") or ""),
            str(tags.get("addr:full") or tags.get("addr:street") or ""),
        ]
        address = "".join(part for part in address_parts if part)
        now = datetime.now(UTC)
        attributes = {
            key: tags[key]
            for key in (
                "access",
                "wheelchair",
                "fee",
                "unisex",
                "changing_table",
                "opening_hours",
                "operator",
                "toilets:disposal",
                "toilets:position",
            )
            if key in tags
        }
        return NormalizedObservation(
            provider=self.name,
            external_id=record.external_id,
            name=name,
            latitude=lat,
            longitude=lon,
            address=address,
            prefecture=str(tags.get("addr:province") or ""),
            category="public_toilet",
            confidence=0.75,
            verification_status=VerificationStatus.AUTOMATICALLY_VERIFIED,
            observed_at=now,
            expires_at=now + timedelta(days=180),
            attributes=attributes,
            payload=payload,
        )

    def provenance(self) -> Provenance:
        return Provenance(
            self.name,
            self.source_type,
            0.75,
            VerificationStatus.AUTOMATICALLY_VERIFIED,
            "https://www.openstreetmap.org/copyright",
        )
