"""
ui/exporter.py
Export toilet data in GeoJSON, KML, and GPX formats.
Related: app.py, ui/sidebar.py
"""
import json
from xml.sax.saxutils import escape

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
