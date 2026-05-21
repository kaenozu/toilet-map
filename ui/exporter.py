"""
ui/exporter.py
Export toilet data in GeoJSON, KML, and GPX formats.
Related: app.py, ui/sidebar.py
"""
import json
from xml.sax.saxutils import escape

import pandas as pd
import streamlit as st

from ui.types import ToiletDict


def to_geojson(toilets: list[ToiletDict]) -> str:
    features = []
    for t in toilets:
        lat = t.get("lat")
        lng = t.get("lng")
        if lat is None or lng is None:
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "title": t.get("title", ""),
                "score": t.get("toilet_score"),
                "address": t.get("address", ""),
                "review_count": t.get("toilet_review_count", 0),
            },
        })
    return json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, indent=2)


def to_kml(toilets: list[ToiletDict]) -> str:
    placemarks = []
    for t in toilets:
        lat = t.get("lat")
        lng = t.get("lng")
        if lat is None or lng is None:
            continue
        name = escape(t.get("title", "") or "")
        score = t.get("toilet_score", "")
        placemarks.append(f"""  <Placemark>
    <name>{name}</name>
    <description>Score: {score}</description>
    <Point><coordinates>{lng},{lat},0</coordinates></Point>
  </Placemark>""")
    return '<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2">\n<Document>\n' + "\n".join(placemarks) + "\n</Document>\n</kml>"


def to_gpx(toilets: list[ToiletDict]) -> str:
    wpts = []
    for t in toilets:
        lat = t.get("lat")
        lng = t.get("lng")
        if lat is None or lng is None:
            continue
        name = escape(t.get("title", "") or "")
        wpts.append(f'  <wpt lat="{lat}" lon="{lng}"><name>{name}</name></wpt>')
    return '<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">\n' + "\n".join(wpts) + "\n</gpx>"


def render_export_ui(filtered_df: pd.DataFrame, map_items: list, selected_pref: str, t: dict) -> None:
    """Render export format selector and download button for toilets data."""
    if len(filtered_df) > 0:
        export_format = st.selectbox(
            "エクスポート形式",
            ["CSV", "GeoJSON", "KML", "GPX"],
            key="export_format",
        )
        if export_format == "CSV":
            data = filtered_df.to_csv(index=False).encode("utf-8-sig")
            mime = "text/csv"
            ext = "csv"
        elif export_format == "GeoJSON":
            data = to_geojson(map_items).encode("utf-8")
            mime = "application/geo+json"
            ext = "geojson"
        elif export_format == "KML":
            data = to_kml(map_items).encode("utf-8")
            mime = "application/vnd.google-earth.kml+xml"
            ext = "kml"
        else:
            data = to_gpx(map_items).encode("utf-8")
            mime = "application/gpx+xml"
            ext = "gpx"
        st.download_button(
            f"📥 {export_format}ダウンロード",
            data,
            f"toilets_{selected_pref}.{ext}",
            mime,
            use_container_width=True,
        )
