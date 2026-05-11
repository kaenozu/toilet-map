"""
verify_data.py
Phase 1 スクレイピング後のデータ品質を検証
実行: python verify_data.py
関連: data/toilets.json.gz, batch/queries.d/
"""
import json
import os
import sqlite3
import gzip
from collections import Counter
from typing import Iterable

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data")
DATA_PATHS = [
    os.path.join(DATA_DIR, "toilets.json.gz"),
    os.path.join(DATA_DIR, "toilets.json"),
]
DB_PATH = os.path.join(DATA_DIR, "toilets.db")
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


def get_expected_prefectures() -> list[str]:
    """queries.d に存在する都道府県一覧を返す。未検出時のみ Kanto を使う。"""
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
    """queries.d/<pref>/batch_*.txt のクエリ数を合算する。"""
    pref_dir = os.path.join(QUERIES_D, pref)
    if not os.path.isdir(pref_dir):
        return 0

    total = 0
    for name in sorted(os.listdir(pref_dir)):
        if not (name.startswith("batch_") and name.endswith(".txt")):
            continue
        path = os.path.join(pref_dir, name)
        with open(path, "r", encoding="utf-8") as f:
            total += sum(1 for line in f if (stripped := line.strip()) and not stripped.startswith("#"))
    return total


def collect_quality_metrics(toilets: list[dict]) -> dict:
    """検証で使う集計値を一か所にまとめる。"""
    pref_counts = Counter(t.get("prefecture", "不明") for t in toilets)
    missing_score = sum(1 for t in toilets if t.get("toilet_score") is None)
    missing_pref = sum(1 for t in toilets if not t.get("prefecture"))
    missing_addr = sum(1 for t in toilets if not t.get("address"))

    seen = {}
    duplicates = []
    for toilet in toilets:
        place_id = toilet.get("place_id", "")
        data_id = toilet.get("data_id", "")
        if place_id:
            key = ("place_id", str(place_id))
        elif data_id:
            key = ("data_id", str(data_id))
        else:
            key = ("title_address", toilet.get("title", ""), toilet.get("address", ""))
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


def _coerce_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def collect_sqlite_metrics(db_path: str = DB_PATH) -> dict | None:
    """SQLite の件数と metadata を読み込む。DB がなければ None を返す。"""
    if not os.path.exists(db_path):
        return None

    conn = sqlite3.connect(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM toilets").fetchone()[0]
        scored = conn.execute("SELECT COUNT(*) FROM toilets WHERE confidence > 0").fetchone()[0]
        public_toilets = conn.execute("SELECT COUNT(*) FROM toilets WHERE is_public_toilet = 1").fetchone()[0]
        prefecture_rows = conn.execute(
            """
            SELECT COALESCE(NULLIF(TRIM(prefecture), ''), '') AS prefecture, COUNT(*)
            FROM toilets
            GROUP BY COALESCE(NULLIF(TRIM(prefecture), ''), '')
            """
        ).fetchall()
        metadata_rows = conn.execute("SELECT key, value FROM metadata").fetchall()
        return {
            "total": total,
            "scored": scored,
            "public_toilets": public_toilets,
            "prefecture_counts": {str(prefecture or ""): int(count) for prefecture, count in prefecture_rows},
            "metadata": dict(metadata_rows),
        }
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def _normalize_count_map(values: dict | Counter) -> dict[str, int]:
    normalized: dict[str, int] = {}
    for key, value in values.items():
        count = _coerce_int(value)
        if count is None:
            continue
        normalized[str(key or "")] = count
    return normalized


def compare_sqlite_metrics(meta: dict, sqlite_metrics: dict) -> tuple[list[str], list[str]]:
    """JSON と SQLite の集計値を比較し、エラーと警告を返す。"""
    errors = []
    warnings = []

    json_total = _coerce_int(meta.get("total"))
    json_scored = _coerce_int(meta.get("scored"))
    json_public = _coerce_int(meta.get("public_toilets"))

    if json_total is not None and json_total != sqlite_metrics["total"]:
        errors.append(f"SQLite total mismatch: json={json_total}, db={sqlite_metrics['total']}")
    if json_scored is not None and json_scored != sqlite_metrics["scored"]:
        errors.append(f"SQLite scored mismatch: json={json_scored}, db={sqlite_metrics['scored']}")
    if json_public is not None and json_public != sqlite_metrics["public_toilets"]:
        errors.append(f"SQLite public_toilets mismatch: json={json_public}, db={sqlite_metrics['public_toilets']}")

    json_last_updated = str(meta.get("last_updated") or "").strip()
    sqlite_last_updated = str(sqlite_metrics.get("metadata", {}).get("last_updated") or "").strip()
    sqlite_synced_at = str(sqlite_metrics.get("metadata", {}).get("db_synced_at") or "").strip()

    if json_last_updated and sqlite_last_updated and json_last_updated != sqlite_last_updated:
        warnings.append(f"SQLite last_updated mismatch: json={json_last_updated}, db={sqlite_last_updated}")
    if json_last_updated and not sqlite_last_updated:
        warnings.append("SQLite last_updated missing")
    if not sqlite_synced_at:
        warnings.append("SQLite db_synced_at missing")

    json_prefecture_counts = _normalize_count_map(meta.get("prefecture_counts", {}))
    sqlite_prefecture_counts = _normalize_count_map(sqlite_metrics.get("prefecture_counts", {}))
    for prefecture in sorted(set(json_prefecture_counts) | set(sqlite_prefecture_counts)):
        json_count = json_prefecture_counts.get(prefecture)
        sqlite_count = sqlite_prefecture_counts.get(prefecture)
        if json_count is None:
            errors.append(f"SQLite has unexpected prefecture: {prefecture}={sqlite_count}")
        elif sqlite_count is None:
            errors.append(f"SQLite missing prefecture: {prefecture} (json={json_count})")
        elif json_count != sqlite_count:
            errors.append(
                f"SQLite prefecture count mismatch: {prefecture}: json={json_count}, db={sqlite_count}"
            )

    return errors, warnings


def _format_duplicate_key(key: tuple[str, ...]) -> str:
    if not key:
        return ""
    kind = key[0]
    if kind == "place_id" and len(key) > 1:
        return f"place_id={key[1]}"
    if kind == "data_id" and len(key) > 1:
        return f"data_id={key[1]}"
    if kind == "title_address" and len(key) > 2:
        title = key[1]
        address = key[2]
        return f"{title} / {address[:30]}..."
    return " / ".join(str(part) for part in key)


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
    sqlite_metrics = collect_sqlite_metrics()
    errors, warnings = evaluate_quality_gate(metrics, expected_prefectures)

    if sqlite_metrics:
        sqlite_errors, sqlite_warnings = compare_sqlite_metrics(meta, sqlite_metrics)
        errors.extend(sqlite_errors)
        warnings.extend(sqlite_warnings)

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
    for pref in expected_prefectures:
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

    if sqlite_metrics:
        print("[SQLITE]")
        print(f"  Total toilets    : {sqlite_metrics['total']}")
        print(f"  With reviews     : {sqlite_metrics['scored']}")
        print(f"  Public toilets   : {sqlite_metrics['public_toilets']}")
        print(f"  Last updated     : {sqlite_metrics['metadata'].get('last_updated', 'N/A')}")
        print(f"  DB synced at     : {sqlite_metrics['metadata'].get('db_synced_at', 'N/A')}")
        print()

    # 重複チェック（place_id / data_id を優先、なければ title+address）
    duplicates = metrics["duplicates"]
    if duplicates:
        print(f"[DUPLICATES] {len(duplicates)} duplicate records found:")
        for duplicate in duplicates[:5]:
            print(f"  - {_format_duplicate_key(duplicate['key'])}")
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
