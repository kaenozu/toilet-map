"""Provider contracts and concrete Google Maps/OSM adapters."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol


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
class Region:
    key: str
    label: str
    prefecture: str
    city: str
    south: float
    west: float
    north: float
    east: float

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return self.south, self.west, self.north, self.east


OSM_REGIONS: dict[str, Region] = {
    # Hokkaido / Tohoku
    "hokkaido": Region("hokkaido", "北海道", "北海道", "北海道", 41.3, 139.5, 45.5, 145.8),
    "aomori": Region("aomori", "青森県", "青森県", "青森県", 40.2, 140.0, 41.5, 141.7),
    "iwate": Region("iwate", "岩手県", "岩手県", "岩手県", 38.9, 140.7, 40.4, 142.0),
    "miyagi": Region("miyagi", "宮城県", "宮城県", "宮城県", 37.7, 140.4, 38.9, 141.7),
    "akita": Region("akita", "秋田県", "秋田県", "秋田県", 39.0, 139.5, 40.4, 140.9),
    "yamagata": Region("yamagata", "山形県", "山形県", "山形県", 37.7, 139.6, 39.2, 140.7),
    "fukushima": Region("fukushima", "福島県", "福島県", "福島県", 36.9, 139.3, 38.0, 141.0),
    # Kanto
    "ibaraki": Region("ibaraki", "茨城県", "茨城県", "茨城県", 35.8, 139.8, 36.9, 140.9),
    "tochigi": Region("tochigi", "栃木県", "栃木県", "栃木県", 36.2, 139.3, 37.0, 140.2),
    "gunma": Region("gunma", "群馬県", "群馬県", "群馬県", 36.0, 138.4, 36.9, 139.6),
    "saitama": Region("saitama", "埼玉県", "埼玉県", "埼玉県", 35.8, 139.0, 36.2, 139.9),
    "chiba": Region("chiba", "千葉県", "千葉県", "千葉県", 34.9, 139.7, 36.0, 141.0),
    "tokyo": Region("tokyo", "東京都", "東京都", "東京都", 35.5, 139.1, 35.9, 140.0),
    "kanagawa": Region("kanagawa", "神奈川県", "神奈川県", "神奈川県", 35.1, 138.9, 35.6, 139.8),
    # Chubu
    "niigata": Region("niigata", "新潟県", "新潟県", "新潟県", 36.9, 137.5, 38.6, 139.9),
    "toyama": Region("toyama", "富山県", "富山県", "富山県", 36.4, 136.8, 37.0, 137.6),
    "ishikawa": Region("ishikawa", "石川県", "石川県", "石川県", 36.1, 136.2, 37.6, 137.4),
    "fukui": Region("fukui", "福井県", "福井県", "福井県", 35.4, 135.4, 36.3, 136.8),
    "yamanashi": Region("yamanashi", "山梨県", "山梨県", "山梨県", 35.3, 138.2, 36.0, 139.1),
    "nagano": Region("nagano", "長野県", "長野県", "長野県", 35.3, 137.3, 36.9, 138.7),
    "gifu": Region("gifu", "岐阜県", "岐阜県", "岐阜県", 35.1, 136.2, 36.5, 137.7),
    "shizuoka": Region("shizuoka", "静岡県", "静岡県", "静岡県", 34.5, 137.4, 35.6, 139.2),
    "aichi": Region("aichi", "愛知県", "愛知県", "愛知県", 34.6, 136.7, 35.4, 137.7),
    # Kansai
    "mie": Region("mie", "三重県", "三重県", "三重県", 33.5, 135.8, 35.2, 136.9),
    "shiga": Region("shiga", "滋賀県", "滋賀県", "滋賀県", 34.8, 135.8, 35.6, 136.4),
    "kyoto": Region("kyoto", "京都府", "京都府", "京都府", 34.7, 135.0, 35.8, 136.1),
    "osaka": Region("osaka", "大阪府", "大阪府", "大阪府", 34.3, 135.2, 34.9, 135.7),
    "hyogo": Region("hyogo", "兵庫県", "兵庫県", "兵庫県", 34.1, 134.2, 35.7, 135.5),
    "nara": Region("nara", "奈良県", "奈良県", "奈良県", 33.4, 135.5, 34.8, 136.2),
    "wakayama": Region("wakayama", "和歌山県", "和歌山県", "和歌山県", 33.1, 135.0, 34.3, 136.0),
    # Chugoku
    "tottori": Region("tottori", "鳥取県", "鳥取県", "鳥取県", 35.0, 133.2, 35.6, 134.5),
    "shimane": Region("shimane", "島根県", "島根県", "島根県", 34.2, 131.6, 36.2, 133.5),
    "okayama": Region("okayama", "岡山県", "岡山県", "岡山県", 34.4, 133.2, 35.3, 134.3),
    "hiroshima": Region("hiroshima", "広島県", "広島県", "広島県", 34.1, 132.0, 34.9, 133.4),
    "yamaguchi": Region("yamaguchi", "山口県", "山口県", "山口県", 33.7, 130.7, 34.8, 132.4),
    # Shikoku
    "tokushima": Region("tokushima", "徳島県", "徳島県", "徳島県", 33.5, 133.8, 34.2, 134.8),
    "kagawa": Region("kagawa", "香川県", "香川県", "香川県", 34.0, 133.5, 34.5, 134.4),
    "ehime": Region("ehime", "愛媛県", "愛媛県", "愛媛県", 32.9, 132.3, 34.2, 133.2),
    "kochi": Region("kochi", "高知県", "高知県", "高知県", 32.9, 132.6, 33.8, 134.4),
    # Kyushu
    "fukuoka": Region("fukuoka", "福岡県", "福岡県", "福岡県", 33.0, 130.0, 34.0, 131.2),
    "saga": Region("saga", "佐賀県", "佐賀県", "佐賀県", 33.0, 129.8, 33.6, 130.5),
    "nagasaki": Region("nagasaki", "長崎県", "長崎県", "長崎県", 32.5, 128.5, 33.5, 130.2),
    "kumamoto": Region("kumamoto", "熊本県", "熊本県", "熊本県", 32.1, 130.0, 33.2, 131.2),
    "oita": Region("oita", "大分県", "大分県", "大分県", 32.7, 130.8, 33.7, 132.1),
    "miyazaki": Region("miyazaki", "宮崎県", "宮崎県", "宮崎県", 31.3, 130.8, 32.8, 131.8),
    "kagoshima": Region("kagoshima", "鹿児島県", "鹿児島県", "鹿児島県", 27.7, 128.5, 32.1, 131.2),
    # Okinawa
    "okinawa": Region("okinawa", "沖縄県", "沖縄県", "沖縄県", 24.0, 122.9, 28.0, 131.3),
}


@dataclass(frozen=True)
class FetchRequest:
    text: str = ""
    prefecture: str = ""
    city: str = ""
    bbox: tuple[float, float, float, float] | None = None


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
    observed_at: datetime | None = None
    expires_at: datetime | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
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
        latitude = payload.get("latitude")
        if latitude is None:
            latitude = payload.get("lat")
        longitude = payload.get("longitude")
        if longitude is None:
            longitude = payload.get("lng")
        if latitude is None or longitude is None:
            return None
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
            attributes={"opening_hours": payload.get("opening_hours")},
            payload=payload,
        )

    def provenance(self) -> Provenance:
        return Provenance(self.name, self.source_type, 0.6, VerificationStatus.UNVERIFIED)

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
