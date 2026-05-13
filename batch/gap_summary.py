"""
batch/gap_summary.py
データギャップ分析のサマリーを表示する（auto_expand_pipeline.batから呼び出し）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db_utils import load_json
from gap_analyzer import find_gaps, get_stats

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "toilets.json.gz")


def print_gap_summary():
    data = load_json(DATA_PATH)
    toilets = data.get("toilets", []) if isinstance(data, dict) else []
    stats = get_stats(toilets)
    gaps = find_gaps(stats, include_catalog=True)
    print(f"  Total toilets: {stats['total']}")
    print(f"  Scored: {stats['scored']}")
    print(f"  Avg score: {stats['score_avg']}")
    print(f"  Underserved areas (count > threshold): {len(gaps)}")
    if gaps:
        print()
        print("  Top underserved:")
        for g in gaps[:5]:
            print(f"    {g['prefecture']} {g['city']} ({g['count']} toilets)")


if __name__ == "__main__":
    print_gap_summary()
