from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable, Protocol


class SourceType(StrEnum):
    GOOGLE_MAPS = "google_maps"
    OPENSTREETMAP = "openstreetmap"
    MUNICIPALITY_OPEN_DATA = "municipality_open_data"
    USER_SUBMISSION = "user_submission"
    ADMIN = "admin"
    LEGACY = "legacy"


class VerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    AUTOMATICALLY_VERIFIED = "automatically_verified"
    HUMAN_VERIFIED = "human_verified"
    DISPUTED = "disputed"
    REJECTED = "rejected"
    STALE = "stale"


@dataclass(frozen=True)
class FetchRequest:
    text: str = ""
    prefecture: str = ""
    city: str = ""


@dataclass(frozen=True)
class RawRecord:
    provider: str
    external_id: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class NormalizedObservation:
    provider: str
    external_id: str
    name: str
    latitude: float
    longitude: float
    address: str = ""
    prefecture: str = ""
    category: str = ""
    confidence: float | None = None
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class Provenance:
    provider: str
    source_type: SourceType
    default_confidence: float | None
    verification_status: VerificationStatus
    license_url: str | None = None


class SourceProvider(Protocol):
    name: str
    source_type: SourceType

    def discover(self, request: FetchRequest) -> Iterable[RawRecord]: ...

    def normalize(self, record: RawRecord) -> NormalizedObservation | None: ...

    def provenance(self) -> Provenance: ...


# Compatibility contract retained while callers migrate to SourceProvider.
SearchQuery = FetchRequest
RawPlace = NormalizedObservation


class PlaceProvider(Protocol):
    name: str

    def search(self, query: SearchQuery) -> list[RawPlace]: ...


class JsonlProvider:
    """Google Maps JSONL adapter that emits raw observations before normalization."""

    name = "google-maps-jsonl"
    source_type = SourceType.GOOGLE_MAPS

    def __init__(self, path: Path) -> None:
        self.path = path

    def discover(self, request: FetchRequest) -> Iterable[RawRecord]:
        with self.path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    continue
                name = str(payload.get("title") or payload.get("name") or "").strip()
                address = str(payload.get("address") or "")
                searchable = f"{name} {address}".casefold()
                if request.text and request.text.casefold() not in searchable:
                    continue
                if request.prefecture and request.prefecture not in address:
                    continue
                if request.city and request.city not in address:
                    continue
                external_id = str(payload.get("place_id") or payload.get("data_id") or payload.get("cid") or "")
                yield RawRecord(provider=self.name, external_id=external_id, payload=payload)

    def normalize(self, record: RawRecord) -> NormalizedObservation | None:
        payload = record.payload
        name = str(payload.get("title") or payload.get("name") or "").strip()
        latitude = payload.get("latitude", payload.get("lat"))
        longitude = payload.get("longitude", payload.get("lng"))
        try:
            lat = float(latitude)
            lon = float(longitude)
        except (TypeError, ValueError):
            return None
        if not name or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None
        external_id = record.external_id or f"{lat}:{lon}:{name}"
        return NormalizedObservation(
            provider=self.name,
            external_id=external_id,
            name=name,
            latitude=lat,
            longitude=lon,
            address=str(payload.get("address") or ""),
            prefecture=str(payload.get("prefecture") or ""),
            category=str(payload.get("category") or ""),
            confidence=0.6,
            verification_status=VerificationStatus.UNVERIFIED,
            payload=payload,
        )

    def provenance(self) -> Provenance:
        return Provenance(
            provider=self.name,
            source_type=self.source_type,
            default_confidence=0.6,
            verification_status=VerificationStatus.UNVERIFIED,
        )

    def search(self, query: SearchQuery) -> list[RawPlace]:
        return [item for record in self.discover(query) if (item := self.normalize(record)) is not None]


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, SourceProvider] = {}

    def register(self, provider: SourceProvider) -> None:
        if provider.name in self._providers:
            raise ValueError(f"provider already registered: {provider.name}")
        self._providers[provider.name] = provider

    def get(self, name: str) -> SourceProvider:
        try:
            return self._providers[name]
        except KeyError as exc:
            raise LookupError(f"unknown provider: {name}") from exc
