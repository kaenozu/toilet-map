"""
verify_data.py
Phase 1 スクレイピング後のデータ品質を検証
実行: python verify_data.py
関連: data/toilets.json.gz, batch/queries.d/
"""
import json
import os
from collections import Counter
from typing import Iterable

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data")
DATA_PATHS = [
    os.path.join(DATA_DIR, "toilets.json.gz"),
    os.path.join(DATA_DIR, "toilets.json"),
]
QUERIES_D = os.path.join(os.path.dirname(__file__), "queries.d")

KANTO_PREFECTURES = ["埼玉県", "東京都", "千葉県", "神奈川県", "茨城県", "栃木県", "群馬県"]
MAX_MISSING_SCORE_RATE = 0.2
MAX_MISSING_PREFECTURE_RATE = 0.1
MAX_MISSING_ADDRESS_RATE = 0.1
MAX_DUPLICATE_RATE = 0.02


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


def collect_quality_metrics(toilets: list[dict]) -> dict:
    """検証で使う集計値を一か所にまとめる。"""
    pref_counts = Counter(t.get("prefecture", "不明") for t in toilets)
    missing_score = sum(1 for t in toilets if t.get("toilet_score") is None)
    missing_pref = sum(1 for t in toilets if not t.get("prefecture"))
    missing_addr = sum(1 for t in toilets if not t.get("address"))

    seen = {}
    duplicates = []
    for toilet in toilets:
        key = (toilet.get("title", ""), toilet.get("address", ""))
        if key in seen:
            duplicates.append(
                {
                    "key": key,
                    "link": toilet.get("link", ""),
                }
            )
        else:
            seen[key] = toilet.get("link", "")

    return {
        "total": len(toilets),
        "prefecture_counts": pref_counts,
        "missing_score": missing_score,
        "missing_prefecture": missing_pref,
        "missing_address": missing_addr,
        "duplicates": duplicates,
    }


def _rate(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return count / total


def evaluate_quality_gate(metrics: dict, expected_prefectures: Iterable[str]) -> tuple[list[str], list[str]]:
    """品質メトリクスからエラーと警告を返す。"""
    total = metrics.get("total", 0)
    errors = []
    warnings = []

    missing_score_rate = _rate(metrics.get("missing_score", 0), total)
    missing_pref_rate = _rate(metrics.get("missing_prefecture", 0), total)
    missing_addr_rate = _rate(metrics.get("missing_address", 0), total)
    duplicate_rate = _rate(len(metrics.get("duplicates", [])), total)

    if missing_score_rate > MAX_MISSING_SCORE_RATE:
        errors.append(f"Missing score rate too high: {missing_score_rate:.1%}")
    if missing_pref_rate > MAX_MISSING_PREFECTURE_RATE:
        errors.append(f"Missing prefecture rate too high: {missing_pref_rate:.1%}")
    if missing_addr_rate > MAX_MISSING_ADDRESS_RATE:
        errors.append(f"Missing address rate too high: {missing_addr_rate:.1%}")
    if duplicate_rate > MAX_DUPLICATE_RATE:
        errors.append(f"Duplicate rate too high: {duplicate_rate:.1%}")

    pref_counts = metrics.get("prefecture_counts", {})
    for pref in expected_prefectures:
        if pref_counts.get(pref, 0) == 0:
            warnings.append(f"No records found for {pref}")

    return errors, warnings


def main():
    print("=" * 60)
    print("  Data Verification - Kanto Phase 1")
    print("=" * 60)
    print()

    data = load_data()
    toilets = data["toilets"]
    meta = data.get("metadata", {})

    metrics = collect_quality_metrics(toilets)
    errors, warnings = evaluate_quality_gate(metrics, KANTO_PREFECTURES)

    # 基本統計
    print("[SUMMARY]")
    print(f"  Total toilets    : {metrics['total']}")
    print(f"  With reviews     : {meta.get('scored', 'N/A')}")
    print(f"  Public toilets   : {meta.get('public_toilets', 'N/A')}")
    print(f"  Last updated     : {meta.get('last_updated', 'N/A')}")
    print()

    # 都道府県別
    pref_counts = metrics["prefecture_counts"]
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
    print("[COMPLETENESS]")
    print(f"  Missing score     : {metrics['missing_score']}/{metrics['total']}")
    print(f"  Missing prefecture: {metrics['missing_prefecture']}/{metrics['total']}")
    print(f"  Missing address   : {metrics['missing_address']}/{metrics['total']}")
    print()

    # 重複チェック（同じ title+address）
    duplicates = metrics["duplicates"]
    if duplicates:
        print(f"[DUPLICATES] {len(duplicates)} duplicate records found:")
        for duplicate in duplicates[:5]:
            title, addr = duplicate["key"]
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
