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
    TILE_OPTIONS,
    get_score_style,
)
from ui.popups import build_popup_html


CLUSTER_THRESHOLDS = [(500, 50), (1000, 80), (float("inf"), 100)]


def calc_cluster_radius(count: int) -> int:
    for threshold, radius in CLUSTER_THRESHOLDS:
        if count < threshold:
            return radius
    return 100


def calc_map_center(
    selected_pref: str,
    meta: dict,
    pref_stats: dict,
) -> tuple[float, float, int]:
    if selected_pref != "全て" and selected_pref in PREFECTURE_CENTERS:
        if selected_pref in pref_stats and pref_stats[selected_pref]["count"] >= 5:
            return (
                pref_stats[selected_pref]["center_lat"],
                pref_stats[selected_pref]["center_lng"],
                11,
            )
        lat, lng = PREFECTURE_CENTERS[selected_pref]
        return lat, lng, 11
    return meta["center_lat"], meta["center_lng"], meta["zoom"]


def build_map(
    toilets: list,
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

    return m