"""
batch/quality_metrics.py
トイレデータ品質メトリクス収集・検証
verify_data.py から分離
"""

import logging
import os
import sqlite3
from collections import Counter
from collections.abc import Iterable

from batch.quality_metrics_dto import (
    ComparisonResult,
    QualityGateResult,
    QualityMetrics,
    SQLiteMetrics,
)

logger = logging.getLogger(__name__)

# 品質ゲートの閾値
MAX_MISSING_SCORE_RATE = 0.2
MAX_MISSING_PREFECTURE_RATE = 0.1
MAX_MISSING_ADDRESS_RATE = 0.1
MAX_DUPLICATE_RATE = 0.02


def _coerce_int(value: object) -> int | None:
    """値を整数に変換、失敗した場合はNoneを返す"""
    try:
        return int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return None


def _coerce_float(value: object) -> float | None:
    """値を浮動小数点数に変換、失敗した場合はNoneを返す"""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _rate(count: int, total: int) -> float:
    """レートを計算、ゼロ除算を避ける"""
    if total <= 0:
        return 0.0
    return count / total


def _collect_basic_counts(toilets: list[dict]) -> tuple[int, int, int, int]:
    """基本的なカウントを収集"""
    missing_score = sum(1 for t in toilets if t.get("toilet_score") is None)
    missing_pref = sum(1 for t in toilets if not t.get("prefecture"))
    missing_addr = sum(1 for t in toilets if not t.get("address"))
    total = len(toilets)
    return total, missing_score, missing_pref, missing_addr


def _collect_prefecture_counts(toilets: list[dict]) -> Counter:
    """都道府県別のカウントを収集"""
    return Counter(t.get("prefecture", "不明") for t in toilets)


def _find_duplicates(toilets: list[dict]) -> list[dict]:
    """重複データを検出"""
    seen = {}
    duplicates = []

    for toilet in toilets:
        key = _generate_duplicate_key(toilet)
        if key in seen:
            duplicates.append(
                {
                    "key": key,
                    "link": toilet.get("link", ""),
                }
            )
        else:
            seen[key] = toilet.get("link", "")

    return duplicates


def _generate_duplicate_key(toilet: dict) -> tuple[str, ...]:
    """重複判定用のキーを生成"""
    place_id = toilet.get("place_id", "")
    data_id = toilet.get("data_id", "")
    lat = _coerce_float(toilet.get("lat"))
    lng = _coerce_float(toilet.get("lng"))

    if place_id:
        return ("place_id", str(place_id))
    elif data_id:
        return ("data_id", str(data_id))
    elif lat is not None and lng is not None:
        return ("coordinates", f"{lat:.6f}", f"{lng:.6f}")
    else:
        return (
            "title_address",
            toilet.get("title", ""),
            toilet.get("address", ""),
        )


def collect_quality_metrics(toilets: list[dict]) -> QualityMetrics:
    """トイレデータの品質メトリクスを収集"""
    total, missing_score, missing_pref, missing_addr = _collect_basic_counts(toilets)
    prefecture_counts = _collect_prefecture_counts(toilets)
    duplicates = _find_duplicates(toilets)

    return QualityMetrics(
        total=total,
        prefecture_counts=dict(prefecture_counts),
        missing_score=missing_score,
        missing_prefecture=missing_pref,
        missing_address=missing_addr,
        duplicates=duplicates,
    )


def collect_sqlite_metrics(db_path: str) -> SQLiteMetrics | None:
    """SQLiteデータベースからメトリクスを収集"""
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

        return SQLiteMetrics(
            total=total,
            scored=scored,
            public_toilets=public_toilets,
            prefecture_counts={str(prefecture or ""): int(count) for prefecture, count in prefecture_rows},
            metadata=dict(metadata_rows),
        )
    except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
        logger.error(f"Failed to collect SQLite metrics from {db_path}: {exc}")
        return None
    finally:
        conn.close()


def _normalize_count_map(values: dict | Counter) -> dict[str, int]:
    """カウントマップを正規化（None値を除外し、キーを文字列に変換）"""
    normalized: dict[str, int] = {}
    for key, value in values.items():
        count = _coerce_int(value)
        if count is None:
            continue
        normalized[str(key or "")] = count
    return normalized


def compare_sqlite_metrics(meta: dict, sqlite_metrics: SQLiteMetrics) -> ComparisonResult:
    """JSONメタデータとSQLiteメトリクスを比較"""
    errors = []
    warnings = []

    # 基本カウントの比較
    json_total = _coerce_int(meta.get("total"))
    json_scored = _coerce_int(meta.get("scored"))
    json_public = _coerce_int(meta.get("public_toilets"))

    if json_total is not None and json_total != sqlite_metrics.total:
        errors.append(f"SQLite total mismatch: json={json_total}, db={sqlite_metrics.total}")
    if json_scored is not None and json_scored != sqlite_metrics.scored:
        errors.append(f"SQLite scored mismatch: json={json_scored}, db={sqlite_metrics.scored}")
    if json_public is not None and json_public != sqlite_metrics.public_toilets:
        errors.append(f"SQLite public_toilets mismatch: json={json_public}, db={sqlite_metrics.public_toilets}")

    # タイムスタンプの比較
    json_last_updated = str(meta.get("last_updated") or "").strip()
    sqlite_last_updated = str(sqlite_metrics.metadata.get("last_updated", "")).strip()
    sqlite_synced_at = str(sqlite_metrics.metadata.get("db_synced_at", "")).strip()

    if json_last_updated and sqlite_last_updated and json_last_updated != sqlite_last_updated:
        warnings.append(f"SQLite last_updated mismatch: json={json_last_updated}, db={sqlite_last_updated}")
    if json_last_updated and not sqlite_last_updated:
        warnings.append("SQLite last_updated missing")
    if not sqlite_synced_at:
        warnings.append("SQLite db_synced_at missing")

    # 都道府県別カウントの比較
    json_prefecture_counts = _normalize_count_map(meta.get("prefecture_counts", {}))
    sqlite_prefecture_counts = _normalize_count_map(sqlite_metrics.prefecture_counts)

    all_prefectures = set(json_prefecture_counts) | set(sqlite_prefecture_counts)
    for prefecture in sorted(all_prefectures):
        json_count = json_prefecture_counts.get(prefecture)
        sqlite_count = sqlite_prefecture_counts.get(prefecture)

        if json_count is None:
            errors.append(f"SQLite has unexpected prefecture: {prefecture}={sqlite_count}")
        elif sqlite_count is None:
            errors.append(f"SQLite missing prefecture: {prefecture} (json={json_count})")
        elif json_count != sqlite_count:
            errors.append(f"SQLite prefecture count mismatch: {prefecture}: json={json_count}, db={sqlite_count}")

    return ComparisonResult(errors=errors, warnings=warnings)


def evaluate_quality_gate(metrics: QualityMetrics, expected_prefectures: Iterable[str]) -> QualityGateResult:
    """品質ゲートを評価"""
    errors = []
    warnings = []
    total = metrics.total

    # 欠損率のチェック
    missing_score_rate = _rate(metrics.missing_score, total)
    missing_pref_rate = _rate(metrics.missing_prefecture, total)
    missing_addr_rate = _rate(metrics.missing_address, total)
    duplicate_rate = _rate(len(metrics.duplicates), total)

    if missing_score_rate > MAX_MISSING_SCORE_RATE:
        errors.append(f"Missing score rate too high: {missing_score_rate:.1%}")
    if missing_pref_rate > MAX_MISSING_PREFECTURE_RATE:
        errors.append(f"Missing prefecture rate too high: {missing_pref_rate:.1%}")
    if missing_addr_rate > MAX_MISSING_ADDRESS_RATE:
        errors.append(f"Missing address rate too high: {missing_addr_rate:.1%}")
    if duplicate_rate > MAX_DUPLICATE_RATE:
        errors.append(f"Duplicate rate too high: {duplicate_rate:.1%}")

    # 期待される都道府県の存在チェック
    pref_counts = metrics.prefecture_counts
    warnings.extend(f"No records found for {pref}" for pref in expected_prefectures if pref_counts.get(pref, 0) == 0)

    return QualityGateResult(errors=errors, warnings=warnings)


def _format_duplicate_key(key: tuple[str, ...]) -> str:
    if not key:
        return ""
    kind = key[0]
    if kind == "place_id" and len(key) > 1:
        return f"place_id={key[1]}"
    if kind == "data_id" and len(key) > 1:
        return f"data_id={key[1]}"
    if kind == "coordinates" and len(key) > 2:
        return f"coordinates={key[1]},{key[2]}"
    if kind == "title_address" and len(key) > 2:
        title = key[1]
        address = key[2]
        return f"{title} / {address[:30]}..."
    return " / ".join(str(part) for part in key)
