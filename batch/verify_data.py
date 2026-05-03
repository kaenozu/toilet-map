"""
verify_data.py
Phase 1 スクレイピング後のデータ品質を検証
実行: python verify_data.py
関連: data/toilets.json.gz, batch/queries.d/
"""
import json
import os
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data")
DATA_PATHS = [
    os.path.join(DATA_DIR, "toilets.json.gz"),
    os.path.join(DATA_DIR, "toilets.json"),
]
QUERIES_D = os.path.join(os.path.dirname(__file__), "queries.d")

KANTO_PREFECTURES = ["埼玉県", "東京都", "千葉県", "神奈川県", "茨城県", "栃木県", "群馬県"]


def load_data():
    for path in DATA_PATHS:
        if os.path.exists(path):
            if path.endswith(".gz"):
                import gzip
                with gzip.open(path, "rt", encoding="utf-8") as f:
                    return json.load(f)
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError(DATA_PATHS[0])


def count_queries_for_pref(pref: str) -> int:
    """queries.d/<pref>/batch_001.txt のクエリ数をカウント"""
    path = os.path.join(QUERIES_D, pref, "batch_001.txt")
    if not os.path.exists(path):
        return 0
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for line in f if (stripped := line.strip()) and not stripped.startswith("#"))


def main():
    print("=" * 60)
    print("  Data Verification - Kanto Phase 1")
    print("=" * 60)
    print()

    data = load_data()
    toilets = data["toilets"]
    meta = data.get("metadata", {})

    # 基本統計
    print("[SUMMARY]")
    print(f"  Total toilets    : {len(toilets)}")
    print(f"  With reviews     : {meta.get('scored', 'N/A')}")
    print(f"  Public toilets   : {meta.get('public_toilets', 'N/A')}")
    print(f"  Last updated     : {meta.get('last_updated', 'N/A')}")
    print()

    # 都道府県別
    pref_counts = Counter(t.get("prefecture", "不明") for t in toilets)
    print("[PREFECTURE DISTRIBUTION]")
    for pref in KANTO_PREFECTURES:
        cnt = pref_counts.get(pref, 0)
        expected = count_queries_for_pref(pref)
        status = "OK" if cnt > 0 else "WARN"
        print(f"  {status} {pref}: {cnt} toilets (expected ~{expected} queries × ~12 results)")
    others = {p: c for p, c in pref_counts.items() if p not in KANTO_PREFECTURES}
    if others:
        print(f"  Others: {others}")
    print()

    # データ completeness
    missing_score = sum(1 for t in toilets if t.get("toilet_score") is None)
    missing_pref = sum(1 for t in toilets if not t.get("prefecture"))
    missing_addr = sum(1 for t in toilets if not t.get("address"))
    print("[COMPLETENESS]")
    print(f"  Missing score     : {missing_score}/{len(toilets)}")
    print(f"  Missing prefecture: {missing_pref}/{len(toilets)}")
    print(f"  Missing address   : {missing_addr}/{len(toilets)}")
    print()

    # 重複チェック（同じ title+address）
    seen = {}
    duplicates = []
    for t in toilets:
        key = (t.get("title", ""), t.get("address", ""))
        if key in seen:
            duplicates.append((key, t["link"]))
        else:
            seen[key] = t["link"]
    if duplicates:
        print(f"[DUPLICATES] {len(duplicates)} duplicate records found:")
        for (title, addr), link in duplicates[:5]:
            print(f"  - {title} / {addr[:30]}...")
    else:
        print("[DUPLICATES] None found")
    print()

    # スコア分布
    scores = [t["toilet_score"] for t in toilets if t.get("toilet_score") is not None]
    if scores:
        print("[SCORE DISTRIBUTION]")
        for s in [5, 4, 3, 2, 1]:
            pct = sum(1 for x in scores if x >= s and x < s + 1) / len(scores) * 100
            print(f"  {s}.0 - {s+1:.1f}: {pct:.1f}%")
    print()

    print("=" * 60)
    print("  Verification complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
