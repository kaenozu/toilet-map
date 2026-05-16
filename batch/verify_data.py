"""
batch/verify_data.py
Phase 1 スクレイピング後のデータ品質を検証
実行: python verify_data.py
関連: data/toilets.json.gz, batch/queries.d/, quality_metrics.py
"""
import gzip
import json
import os

from quality_metrics import (
    _format_duplicate_key,
    collect_quality_metrics,
    collect_sqlite_metrics,
    compare_sqlite_metrics,
    evaluate_quality_gate,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data")
DATA_PATHS = [
    os.path.join(DATA_DIR, "toilets.json.gz"),
    os.path.join(DATA_DIR, "toilets.json"),
]
DB_PATH = os.path.join(DATA_DIR, "toilets.db")
QUERIES_D = os.path.join(os.path.dirname(__file__), "queries.d")

KANTO_PREFECTURES = ["埼玉県", "東京都", "千葉県", "神奈川県", "茨城県", "栃木県", "群馬県"]


def load_data():
    for path in DATA_PATHS:
        if os.path.exists(path):
            if path.endswith(".gz"):
                with gzip.open(path, "rt", encoding="utf-8") as f:
                    return json.load(f)
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError(DATA_PATHS[0])


def get_expected_prefectures() -> list[str]:
    if not os.path.isdir(QUERIES_D):
        return KANTO_PREFECTURES
    prefectures = []
    for entry in sorted(os.listdir(QUERIES_D)):
        pref_dir = os.path.join(QUERIES_D, entry)
        if not os.path.isdir(pref_dir):
            continue
        if any(name.startswith("batch_") and name.endswith(".txt") for name in os.listdir(pref_dir)):
            prefectures.append(entry)
    return prefectures or KANTO_PREFECTURES


def count_queries_for_pref(pref: str) -> int:
    pref_dir = os.path.join(QUERIES_D, pref)
    if not os.path.isdir(pref_dir):
        return 0
    total = 0
    for name in sorted(os.listdir(pref_dir)):
        if not (name.startswith("batch_") and name.endswith(".txt")):
            continue
        path = os.path.join(pref_dir, name)
        with open(path, encoding="utf-8") as f:
            total += sum(1 for line in f if (stripped := line.strip()) and not stripped.startswith("#"))
    return total


def main():
    expected_prefectures = get_expected_prefectures()
    if expected_prefectures == KANTO_PREFECTURES:
        label = "Kanto Phase 1"
    elif len(expected_prefectures) == 1:
        label = expected_prefectures[0]
    else:
        label = f"{len(expected_prefectures)} prefectures"

    print("=" * 60)
    print(f"  Data Verification - {label}")
    print("=" * 60)
    print()

    data = load_data()
    toilets = data["toilets"]
    meta = data.get("metadata", {})

    metrics = collect_quality_metrics(toilets)
    sqlite_metrics = collect_sqlite_metrics(DB_PATH)
    errors, warnings = evaluate_quality_gate(metrics, expected_prefectures)

    if sqlite_metrics:
        compare_meta = dict(meta)
        compare_meta.setdefault("prefecture_counts", metrics["prefecture_counts"])
        sqlite_errors, sqlite_warnings = compare_sqlite_metrics(compare_meta, sqlite_metrics)
        errors.extend(sqlite_errors)
        warnings.extend(sqlite_warnings)

    print("[SUMMARY]")
    print(f"  Total toilets    : {metrics['total']}")
    print(f"  With reviews     : {meta.get('scored', 'N/A')}")
    print(f"  Public toilets   : {meta.get('public_toilets', 'N/A')}")
    print(f"  Last updated     : {meta.get('last_updated', 'N/A')}")
    print()

    pref_counts = metrics["prefecture_counts"]
    print("[PREFECTURE DISTRIBUTION]")
    for pref in expected_prefectures:
        cnt = pref_counts.get(pref, 0)
        expected = count_queries_for_pref(pref)
        status = "OK" if cnt > 0 else "WARN"
        print(f"  {status} {pref}: {cnt} toilets (expected ~{expected} queries x ~12 results)")
    others = {p: c for p, c in pref_counts.items() if p not in KANTO_PREFECTURES}
    if others:
        print(f"  Others: {others}")
    print()

    print("[COMPLETENESS]")
    print(f"  Missing score     : {metrics['missing_score']}/{metrics['total']}")
    print(f"  Missing prefecture: {metrics['missing_prefecture']}/{metrics['total']}")
    print(f"  Missing address   : {metrics['missing_address']}/{metrics['total']}")
    print()

    if sqlite_metrics:
        print("[SQLITE]")
        print(f"  Total toilets    : {sqlite_metrics['total']}")
        print(f"  With reviews     : {sqlite_metrics['scored']}")
        print(f"  Public toilets   : {sqlite_metrics['public_toilets']}")
        print(f"  Last updated     : {sqlite_metrics['metadata'].get('last_updated', 'N/A')}")
        print(f"  DB synced at     : {sqlite_metrics['metadata'].get('db_synced_at', 'N/A')}")
        print()

    duplicates = metrics["duplicates"]
    if duplicates:
        print(f"[DUPLICATES] {len(duplicates)} duplicate records found:")
        for duplicate in duplicates[:5]:
            print(f"  - {_format_duplicate_key(duplicate['key'])}")
    else:
        print("[DUPLICATES] None found")
    print()

    scores = [t["toilet_score"] for t in toilets if t.get("toilet_score") is not None]
    if scores:
        print("[SCORE DISTRIBUTION]")
        buckets = [(80, 101, "✨ 80-100"), (65, 80, "😊 65-79"), (50, 65, "😐 50-64"), (35, 50, "😨 35-49"), (0, 35, "💩 0-34")]
        for lo, hi, label in buckets:
            count = sum(1 for x in scores if lo <= x < hi)
            pct = count / len(scores) * 100
            print(f"  {label}: {count}件 ({pct:.1f}%)")
    print()

    if warnings:
        print("[WARNINGS]")
        for warning in warnings:
            print(f"  - {warning}")
        print()

    if errors:
        print("[ERRORS]")
        for error in errors:
            print(f"  - {error}")
        print()

    print("=" * 60)
    print("  Verification complete")
    print("=" * 60)

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
