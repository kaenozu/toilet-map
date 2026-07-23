from __future__ import annotations

from dataclasses import dataclass
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
    category: str = ""
    payload: dict[str, Any] | None = None


class PlaceProvider(Protocol):
    name: str

    def search(self, query: SearchQuery) -> list[RawPlace]: ...


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
