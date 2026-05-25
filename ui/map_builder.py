"""
ui/map_builder.py
Folium 地図構築・マーカー配置
app.py から分離
"""
import logging
import math

import folium
import streamlit as st
from folium.plugins import HeatMap, MarkerCluster

from app_config import (
    NORMAL_MARKER_RADIUS,
    POPUP_FIX_JS,
    PREFECTURE_CENTERS,
    PUBLIC_MARKER_RADIUS,
)

from .helpers import get_score_style
from .popups import build_popup_html
from .types import ToiletDict

logger = logging.getLogger(__name__)

CLUSTER_THRESHOLDS = [(500, 50), (1000, 80), (float("inf"), 100)]
FIT_BOUNDS_PADDING = (24, 24)
FIT_BOUNDS_EPSILON = 0.01
COORD_DEDUPE_PRECISION = 6


def _resolve_tile_attribution(tile: str) -> str | None:
    """Return attribution for URL-based tiles required by Folium."""
    normalized = tile.lower()
    if "openstreetmap.org" in normalized:
        return "&copy; OpenStreetMap contributors"
    if "cartocdn.com" in normalized:
        return "&copy; OpenStreetMap contributors &copy; CARTO"
    return None


def _coerce_coordinate(value: object) -> float | None:
    try:
        coordinate = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(coordinate):
        return None
    return coordinate


def _coordinate_key(lat: float, lng: float) -> tuple[float, float]:
    return (round(lat, COORD_DEDUPE_PRECISION), round(lng, COORD_DEDUPE_PRECISION))


def _collect_valid_toilets(
    toilets: list[ToiletDict],
) -> list[tuple[ToiletDict, float, float]]:
    """重複座標を除外して有効なトイレデータを収集"""
    valid: list[tuple[ToiletDict, float, float]] = []
    seen: set[tuple[float, float]] = set()
    for toilet in toilets:
        lat = _coerce_coordinate(toilet.get("lat"))
        lng = _coerce_coordinate(toilet.get("lng"))
        if lat is None or lng is None:
            continue
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            continue
        key = _coordinate_key(lat, lng)
        if key in seen:
            continue
        seen.add(key)
        valid.append((toilet, lat, lng))
    return valid


def _collect_valid_coordinates(toilets: list[ToiletDict]) -> list[tuple[float, float]]:
    """_collect_valid_toilets から座標のみを抽出"""
    return [(lat, lng) for _, lat, lng in _collect_valid_toilets(toilets)]


def calc_cluster_radius(count: int) -> int:
    for threshold, radius in CLUSTER_THRESHOLDS:
        if count < threshold:
            return radius
    return 100


def calc_map_center(
    selected_pref: str,
    meta: dict,
    prefecture_stats: dict,
) -> tuple[float, float, int]:
    if selected_pref != "全て" and selected_pref in PREFECTURE_CENTERS:
        if selected_pref in prefecture_stats and prefecture_stats[selected_pref]["count"] >= 5:
            return (
                prefecture_stats[selected_pref]["center_lat"],
                prefecture_stats[selected_pref]["center_lng"],
                11,
            )
        lat, lng = PREFECTURE_CENTERS[selected_pref]
        return lat, lng, 11
    # "全て": use prefecture-weighted center instead of raw average
    if prefecture_stats:
        lat_sum = lng_sum = weight_sum = 0.0
        for s in prefecture_stats.values():
            w = s.get("count", 0)
            if w > 0:
                lat_sum += s.get("center_lat", 0) * w
                lng_sum += s.get("center_lng", 0) * w
                weight_sum += w
        if weight_sum > 0:
            return round(lat_sum / weight_sum, 4), round(lng_sum / weight_sum, 4), meta.get("zoom", 9)
    return meta["center_lat"], meta["center_lng"], meta["zoom"]


def _calc_fit_bounds(valid_toilets: list[tuple[ToiletDict, float, float]]) -> list[list[float]] | None:
    """マーカーを包む bounds を返す。1点だけの場合は少しだけ広げる。"""
    coords = [(lat, lng) for _, lat, lng in valid_toilets]
    if not coords:
        return None

    lats = [lat for lat, _ in coords]
    lngs = [lng for _, lng in coords]
    south = min(lats)
    north = max(lats)
    west = min(lngs)
    east = max(lngs)

    if south == north:
        south -= FIT_BOUNDS_EPSILON
        north += FIT_BOUNDS_EPSILON
    if west == east:
        west -= FIT_BOUNDS_EPSILON
        east += FIT_BOUNDS_EPSILON

    return [[south, west], [north, east]]


def add_heatmap(m: folium.Map, toilets: list[ToiletDict]) -> None:
    """Add an optional heatmap layer showing toilet density."""
    locations = []
    for toilet in toilets:
        lat = _coerce_coordinate(toilet.get("lat"))
        lng = _coerce_coordinate(toilet.get("lng"))
        if lat is None or lng is None:
            continue
        locations.append([lat, lng])
        if len(locations) >= 2000:
            break
    if locations:
        HeatMap(
            locations,
            radius=15,
            blur=10,
            max_zoom=12,
            min_opacity=0.3,
        ).add_to(m)


def build_map(
    toilets: list[ToiletDict],
    center_lat: float,
    center_lng: float,
    zoom: int,
    tile: str = "OpenStreetMap",
    show_heatmap: bool = False,
) -> folium.Map:
    try:
        attribution = _resolve_tile_attribution(tile)
        m = folium.Map(
            location=[center_lat, center_lng],
            zoom_start=zoom,
            tiles=tile,
            attr=attribution,
            control_scale=True,
            prefer_canvas=True,
        )
        m.get_root().html.add_child(folium.Element(POPUP_FIX_JS))

        valid_toilets = _collect_valid_toilets(toilets)

        cluster = MarkerCluster(
            options={
                "maxClusterRadius": calc_cluster_radius(len(valid_toilets)),
                "spiderfyOnMaxZoom": True,
                "disableClusteringAtZoom": 15,
            },
            name="トイレ",
        ).add_to(m)

        for t, lat, lng in valid_toilets:
            color, emoji, _ = get_score_style(t["toilet_score"])
            radius = PUBLIC_MARKER_RADIUS if t["is_public_toilet"] else NORMAL_MARKER_RADIUS

            popup_html = build_popup_html(t)
            folium.CircleMarker(
                location=[lat, lng],
                radius=radius,
                color="white",
                weight=2,
                fill=True,
                fill_color=color,
                fill_opacity=0.9,
                popup=folium.Popup(popup_html, max_width=320, auto_pan=True),
                tooltip=f"{emoji} {t['title']}",
            ).add_to(cluster)

        if show_heatmap:
            add_heatmap(m, toilets)

        bounds = _calc_fit_bounds(valid_toilets)
        if bounds:
            m.fit_bounds(bounds, padding=FIT_BOUNDS_PADDING)

        return m
    except Exception:
        logger.exception("Map build failed")
        st.warning("地図の生成に失敗しました。デフォルト地図を表示します。")
        return folium.Map(location=[35.68, 139.69], zoom_start=5)
