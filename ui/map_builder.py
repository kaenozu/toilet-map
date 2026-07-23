"""Folium map construction."""

from __future__ import annotations

import math

import folium
from folium.plugins import MarkerCluster

from app_config import (
    NORMAL_MARKER_RADIUS,
    POPUP_FIX_JS,
    PREFECTURE_CENTERS,
    PUBLIC_MARKER_RADIUS,
    TILE_ATTRIBUTIONS,
)

from .helpers import get_score_style
from .popups import build_popup_html
from .types import ToiletDict

CLUSTER_THRESHOLDS = [(500, 50), (1000, 80), (float("inf"), 100)]
FIT_BOUNDS_PADDING = (24, 24)
FIT_BOUNDS_EPSILON = 0.01
MAX_MAP_MARKERS = 1500


def _coerce_coordinate(value: object) -> float | None:
    try:
        coordinate = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return coordinate if math.isfinite(coordinate) else None


def _collect_valid_toilets(toilets: list[ToiletDict]) -> list[tuple[ToiletDict, float, float]]:
    """Preserve distinct records even when they share the same coordinates."""
    valid: list[tuple[ToiletDict, float, float]] = []
    for toilet in toilets:
        lat, lng = _coerce_coordinate(toilet.get("lat")), _coerce_coordinate(toilet.get("lng"))
        if lat is None or lng is None or not (-90 <= lat <= 90 and -180 <= lng <= 180):
            continue
        valid.append((toilet, lat, lng))
    return valid


def _select_map_toilets(toilets: list[ToiletDict], limit: int = MAX_MAP_MARKERS) -> list[ToiletDict]:
    """Bound generated Folium HTML while keeping the highest-confidence records."""
    if len(toilets) <= limit:
        return toilets
    return sorted(
        toilets,
        key=lambda item: (
            float(item.get("confidence") or 0),
            int(item.get("toilet_review_count") or 0),
            float(item.get("toilet_score") or 0),
        ),
        reverse=True,
    )[:limit]


def _collect_valid_coordinates(toilets: list[ToiletDict]) -> list[tuple[float, float]]:
    return [(lat, lng) for _, lat, lng in _collect_valid_toilets(toilets)]


def calc_cluster_radius(count: int) -> int:
    for threshold, radius in CLUSTER_THRESHOLDS:
        if count < threshold:
            return radius
    return 100


def calc_map_center(selected_pref: str, meta: dict, prefecture_stats: dict) -> tuple[float, float, int]:
    if selected_pref != "全て" and selected_pref in PREFECTURE_CENTERS:
        stats = prefecture_stats.get(selected_pref)
        if stats and stats.get("count", 0) >= 5:
            return stats["center_lat"], stats["center_lng"], 11
        lat, lng = PREFECTURE_CENTERS[selected_pref]
        return lat, lng, 11
    return meta["center_lat"], meta["center_lng"], meta["zoom"]


def _calc_fit_bounds(toilets: list[ToiletDict]) -> list[list[float]] | None:
    coordinates = _collect_valid_coordinates(toilets)
    if not coordinates:
        return None
    lats, lngs = [lat for lat, _ in coordinates], [lng for _, lng in coordinates]
    south, north, west, east = min(lats), max(lats), min(lngs), max(lngs)
    if south == north:
        south -= FIT_BOUNDS_EPSILON
        north += FIT_BOUNDS_EPSILON
    if west == east:
        west -= FIT_BOUNDS_EPSILON
        east += FIT_BOUNDS_EPSILON
    return [[south, west], [north, east]]


def _create_map(center_lat: float, center_lng: float, zoom: int, tile: str) -> folium.Map:
    if tile in TILE_ATTRIBUTIONS:
        map_object = folium.Map(
            location=[center_lat, center_lng],
            zoom_start=zoom,
            tiles=None,
            control_scale=True,
            prefer_canvas=True,
        )
        folium.TileLayer(tiles=tile, attr=TILE_ATTRIBUTIONS[tile], name="OpenTopoMap").add_to(map_object)
        return map_object
    return folium.Map(
        location=[center_lat, center_lng],
        zoom_start=zoom,
        tiles=tile,
        control_scale=True,
        prefer_canvas=True,
    )


def build_map(
    toilets: list[ToiletDict],
    center_lat: float,
    center_lng: float,
    zoom: int,
    tile: str = "OpenStreetMap",
) -> folium.Map:
    map_object = _create_map(center_lat, center_lng, zoom, tile)
    map_object.get_root().html.add_child(folium.Element(POPUP_FIX_JS))  # type: ignore[attr-defined]
    selected_toilets = _select_map_toilets(toilets)
    valid_toilets = _collect_valid_toilets(selected_toilets)
    cluster = MarkerCluster(
        options={
            "maxClusterRadius": calc_cluster_radius(len(valid_toilets)),
            "spiderfyOnMaxZoom": True,
            "disableClusteringAtZoom": 15,
        },
        name="トイレ",
    ).add_to(map_object)
    for toilet, lat, lng in valid_toilets:
        color, emoji, _ = get_score_style(toilet["toilet_score"])
        radius = PUBLIC_MARKER_RADIUS if toilet["is_public_toilet"] else NORMAL_MARKER_RADIUS
        folium.CircleMarker(
            location=[lat, lng],
            radius=radius,
            color="white",
            weight=2,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            popup=folium.Popup(build_popup_html(toilet), max_width=320, auto_pan=True),
            tooltip=f"{emoji} {toilet['title']}",
        ).add_to(cluster)
    if bounds := _calc_fit_bounds(selected_toilets):
        map_object.fit_bounds(bounds, padding=FIT_BOUNDS_PADDING)
    return map_object
