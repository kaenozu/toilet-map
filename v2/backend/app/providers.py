from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class SearchQuery:
    text: str
    prefecture: str = ""
    city: str = ""


@dataclass(frozen=True)
class RawPlace:
    provider: str
    external_id: str
    name: str
    latitude: float
    longitude: float
    address: str = ""
    prefecture: str = ""
    category: str = ""
    payload: dict[str, Any] | None = None


class PlaceProvider(Protocol):
    name: str

    def search(self, query: SearchQuery) -> list[RawPlace]: ...


class JsonlProvider:
    """Adapter for google-maps-scraper JSONL output and offline fixtures."""

    name = "google-maps-jsonl"

    def __init__(self, path: Path) -> None:
        self.path = path

    def search(self, query: SearchQuery) -> list[RawPlace]:
        results: list[RawPlace] = []
        with self.path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    continue
                name = str(payload.get("title") or payload.get("name") or "").strip()
                external_id = str(payload.get("place_id") or payload.get("data_id") or payload.get("cid") or "")
                latitude = payload.get("latitude", payload.get("lat"))
                longitude = payload.get("longitude", payload.get("lng"))
                try:
                    lat = float(latitude)
                    lon = float(longitude)
                except (TypeError, ValueError):
                    continue
                searchable = f"{name} {payload.get('address', '')}".casefold()
                if query.text and query.text.casefold() not in searchable:
                    continue
                address = str(payload.get("address") or "")
                if query.prefecture and query.prefecture not in address:
                    continue
                if query.city and query.city not in address:
                    continue
                results.append(
                    RawPlace(
                        provider=self.name,
                        external_id=external_id or f"{lat}:{lon}:{name}",
                        name=name,
                        latitude=lat,
                        longitude=lon,
                        address=address,
                        prefecture=query.prefecture,
                        category=str(payload.get("category") or ""),
                        payload=payload,
                    )
                )
        return results


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, PlaceProvider] = {}

    def register(self, provider: PlaceProvider) -> None:
        if provider.name in self._providers:
            raise ValueError(f"provider already registered: {provider.name}")
        self._providers[provider.name] = provider

    def get(self, name: str) -> PlaceProvider:
        try:
            return self._providers[name]
        except KeyError as exc:
            raise LookupError(f"unknown provider: {name}") from exc
