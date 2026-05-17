"""
scripts/profile.py
Performance profiling script using cProfile and pstats.
Related: ui/data_loader.py, ui/filters.py, app.py

Usage: python scripts/profile.py
"""
import cProfile
import pstats
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ui.data_loader import get_data_cache_token, load_toilet_data


def profile_data_loading():
    token = get_data_cache_token()
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(5):
        load_toilet_data(token)
    profiler.disable()
    stats = pstats.Stats(profiler).sort_stats("cumtime")
    stats.print_stats(20)
    print("\n--- By call count ---")
    stats.sort_stats("ncalls").print_stats(20)


def profile_pref_stats():
    """Profile just the pref_stats calculation."""
    import math
    import sqlite3

    import pandas as pd

    from app_config import DB_PATH

    conn = sqlite3.connect(DB_PATH)
    toilets = pd.read_sql("SELECT * FROM toilets", conn).to_dict("records")
    conn.close()

    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(100):
        pref_stats = {}
        for t in toilets:
            pref = t.get("prefecture")
            if not pref or (isinstance(pref, float) and math.isnan(pref)):
                continue
            if pref not in pref_stats:
                pref_stats[pref] = {"count": 0, "lat_sum": 0.0, "lng_sum": 0.0}
            pref_stats[pref]["count"] += 1
            pref_stats[pref]["lat_sum"] += t["lat"] or 0
            pref_stats[pref]["lng_sum"] += t["lng"] or 0
        for data in pref_stats.values():
            c = data.pop("count")
            data["center_lat"] = data.pop("lat_sum") / c if c else 0
            data["center_lng"] = data.pop("lng_sum") / c if c else 0
    profiler.disable()
    stats = pstats.Stats(profiler).sort_stats("cumtime")
    stats.print_stats(10)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Run all profiles")
    args = parser.parse_args()
    print("=== Profiling data loading ===")
    profile_data_loading()
    print("\n=== Profiling pref_stats ===")
    profile_pref_stats()
