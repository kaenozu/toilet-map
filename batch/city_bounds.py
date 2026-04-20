"""
city_bounds.py
日本の市区町村のバウンディングボックスを取得・キャッシュする
Nominatim API (OSM) を使用し、結果をローカルJSONにキャッシュ

使い方:
    from city_bounds import get_city_bounds, filter_raw_data
    bounds = get_city_bounds("羽生市", "埼玉県")

関連: scrape_runner.py, process_data.py
"""
import json
import os
import time
import urllib.request
import urllib.parse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(SCRIPT_DIR, "city_bounds_cache.json")


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


def get_city_bounds(city: str, prefecture: str = "") -> dict | None:
    """市区町村のバウンディングボックスを返す
    Returns: {"south": float, "north": float, "west": float, "east": float} or None
    """
    cache = _load_cache()
    key = f"{prefecture}{city}"
    if key in cache:
        return cache[key]

    query = f"{city}, {prefecture}, Japan" if prefecture else f"{city}, Japan"
    params = urllib.parse.urlencode({
        "q": query,
        "format": "json",
        "limit": 1,
        "polygon_geojson": 0,
        "accept-language": "ja",
    })
    url = f"https://nominatim.openstreetmap.org/search?{params}"

    req = urllib.request.Request(url, headers={"User-Agent": "toilet-map-bounds/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            results = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  [city_bounds] Failed to fetch bounds for {key}: {e}")
        return None

    time.sleep(1.1)

    if not results:
        print(f"  [city_bounds] No results for: {query}")
        return None

    bb = results[0].get("boundingbox")
    if not bb or len(bb) < 4:
        return None

    bounds = {
        "south": float(bb[0]),
        "north": float(bb[1]),
        "west": float(bb[2]),
        "east": float(bb[3]),
    }

    cache[key] = bounds
    _save_cache(cache)
    print(f"  [city_bounds] Fetched {key}: "
          f"S={bounds['south']:.4f} N={bounds['north']:.4f} "
          f"W={bounds['west']:.4f} E={bounds['east']:.4f}")
    return bounds


def is_in_bounds(lat: float, lng: float, bounds: dict) -> bool:
    return (bounds["south"] <= lat <= bounds["north"] and
            bounds["west"] <= lng <= bounds["east"])


def filter_raw_data(input_path: str, output_path: str,
                    city_name: str, bounds: dict | None = None) -> tuple[int, int]:
    """JSONLを都市名(住所)とバウンディングボックスでフィルタ
    OR logic: 住所一致 OR 座標範囲内 → 保持
    Returns: (total_count, kept_count)
    """
    kept = 0
    total = 0

    with open(input_path, "r", encoding="utf-8") as inf, \
         open(output_path, "w", encoding="utf-8") as outf:
        for line in inf:
            total += 1
            stripped = line.strip()
            if not stripped:
                continue

            try:
                entry = json.loads(stripped)
            except json.JSONDecodeError:
                continue

            address_match = city_name in entry.get("address", "")

            coord_match = False
            if bounds:
                lat = entry.get("latitude")
                lng = entry.get("longtitude") or entry.get("longitude")
                if lat and lng:
                    coord_match = is_in_bounds(float(lat), float(lng), bounds)

            if address_match or coord_match:
                outf.write(stripped + "\n")
                kept += 1

    return total, kept


def main():
    """CLI: 指定都市のバウンディングボックスを表示"""
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
