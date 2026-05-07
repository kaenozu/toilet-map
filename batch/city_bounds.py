"""
batch/city_bounds.py
市区町村のバウンディングボックス取得・キャッシュ
Nominatim API 使用
"""
import json
import logging
import os
import time
import urllib.request
import urllib.parse
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(SCRIPT_DIR, "city_bounds_cache.json")

# 簡易ロガー
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', '%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def _load_cache() -> dict:
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache: dict):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def get_city_bounds(city: str, prefecture: str = "") -> Optional[dict]:
    cache = _load_cache()
    key = f"{prefecture}{city}"
    if key in cache:
        return cache[key]

    query = f"{city}, {prefecture}, Japan" if prefecture else f"{city}, Japan"
    params = urllib.parse.urlencode({
        "q": query, "format": "json", "limit": 1,
        "polygon_geojson": 0, "accept-language": "ja",
    })
    url = f"https://nominatim.openstreetmap.org/search?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "toilet-map-bounds/1.0"})

    results = None
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            results = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.warning(f"Failed to fetch bounds for {key}: {e}")
    finally:
        time.sleep(1.1)  # Nominatim rate limit: 1 req/sec

    if not results:
        logger.warning(f"No results for: {query}")
        return None

    bb = results[0].get("boundingbox")
    if not bb or len(bb) < 4:
        return None

    bounds = {
        "south": float(bb[0]), "north": float(bb[1]),
        "west": float(bb[2]), "east": float(bb[3]),
    }

    cache[key] = bounds
    _save_cache(cache)
    logger.info(f"Fetched {key}: S={bounds['south']:.4f} N={bounds['north']:.4f} W={bounds['west']:.4f} E={bounds['east']:.4f}")
    return bounds


def is_in_bounds(lat: float, lng: float, bounds: dict) -> bool:
    return bounds["south"] <= lat <= bounds["north"] and bounds["west"] <= lng <= bounds["east"]


def filter_raw_data(input_path: str, output_path: str, city_name: str, bounds: Optional[dict] = None) -> tuple[int, int]:
    kept = 0
    total = 0
    with open(input_path, "r", encoding="utf-8") as inf, open(output_path, "w", encoding="utf-8") as outf:
        for line in inf:
            total += 1
            stripped = line.strip()
            if not stripped:
                continue
            try:
                entry = json.loads(stripped)
            except json.JSONDecodeError:
                continue

            address_match = bool(city_name) and city_name in entry.get("address", "")
            coord_match = False
            if bounds:
                lat = entry.get("latitude")
                lng = entry.get("longitude")
                if lng is None:
                    lng = entry.get("longtitude")
                if lat and lng:
                    coord_match = is_in_bounds(float(lat), float(lng), bounds)

            if address_match or coord_match:
                outf.write(stripped + "\n")
                kept += 1

    return total, kept


def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python city_bounds.py <city> [prefecture]")
        print("  python city_bounds.py 羽生市 埼玉県")
        sys.exit(1)
    city = sys.argv[1]
    pref = sys.argv[2] if len(sys.argv) > 2 else ""
    bounds = get_city_bounds(city, pref)
    if bounds:
        print(json.dumps(bounds, indent=2))
    else:
        print(f"Could not find bounds for {city}")
        sys.exit(1)


if __name__ == "__main__":
    main()
