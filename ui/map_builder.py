"""
ui/map_builder.py
Folium 地図構築・マーカー配置
app.py から分離
"""
import folium
from folium.plugins import MarkerCluster
from app_config import (
    PUBLIC_MARKER_RADIUS,
    NORMAL_MARKER_RADIUS,
    POPUP_FIX_JS,
    PREFECTURE_CENTERS,
    get_score_style,
)
from .popups import build_popup_html
from .types import ToiletDict


CLUSTER_THRESHOLDS = [(500, 50), (1000, 80), (float("inf"), 100)]
FIT_BOUNDS_PADDING = (24, 24)
FIT_BOUNDS_EPSILON = 0.01


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
    return meta["center_lat"], meta["center_lng"], meta["zoom"]


def _calc_fit_bounds(toilets: list[ToiletDict]) -> list[list[float]] | None:
    """マーカーを包む bounds を返す。1点だけの場合は少しだけ広げる。"""
    coords = [
        (t.get("lat"), t.get("lng"))
        for t in toilets
        if t.get("lat") is not None and t.get("lng") is not None
    ]
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


def build_map(
    toilets: list[ToiletDict],
    center_lat: float,
    center_lng: float,
    zoom: int,
    tile: str = "OpenStreetMap",
) -> folium.Map:
    m = folium.Map(
        location=[center_lat, center_lng],
        zoom_start=zoom,
        tiles=tile,
        control_scale=True,
        prefer_canvas=True,  # large datasets: use Canvas renderer for performance
    )
    m.get_root().html.add_child(folium.Element(POPUP_FIX_JS))

    cluster = MarkerCluster(
        options={"maxClusterRadius": calc_cluster_radius(len(toilets)), "spiderfyOnMaxZoom": True},
        name="トイレ",
    ).add_to(m)

    for t in toilets:
        color, emoji, _ = get_score_style(t["toilet_score"])
        radius = PUBLIC_MARKER_RADIUS if t["is_public_toilet"] else NORMAL_MARKER_RADIUS

        popup_html = build_popup_html(t)
        folium.CircleMarker(
            location=[t["lat"], t["lng"]],
            radius=radius,
            color="white",
            weight=2,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            popup=folium.Popup(popup_html, max_width=320, auto_pan=True),
            tooltip=f"{emoji} {t['title']}",
        ).add_to(cluster)

    bounds = _calc_fit_bounds(toilets)
    if bounds:
        m.fit_bounds(bounds, padding=FIT_BOUNDS_PADDING)

    return m