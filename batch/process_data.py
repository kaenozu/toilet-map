# mypy: disable-error-code="no-redef"
"""Process Google Maps scraper JSONL output into the canonical JSON snapshot."""

from __future__ import annotations

import gzip
import json
import math
import sys
from datetime import datetime
from typing import cast

try:
    from .identity import build_fallback_source_id, build_source_id, normalize_identity_text
    from .scoring import (
        PlaceDict,
        ToiletResultDict,
        ToiletScoreInfo,
        _extract_coordinates,
        compute_toilet_score,
        is_toilet_place,
    )
    from .scoring_config import AREA_NAME_RE, DISPLAY_SCORE_MULTIPLIER, DISPLAY_SCORE_OFFSET
    from .utils import extract_prefecture, load_jsonl, logger, save_json
except ImportError:
    from identity import build_fallback_source_id, build_source_id, normalize_identity_text
    from scoring import (
        PlaceDict,
        ToiletResultDict,
        ToiletScoreInfo,
        _extract_coordinates,
        compute_toilet_score,
        is_toilet_place,
    )
    from scoring_config import AREA_NAME_RE, DISPLAY_SCORE_MULTIPLIER, DISPLAY_SCORE_OFFSET
    from utils import extract_prefecture, load_jsonl, logger, save_json

from app_config import POTENTIAL_CATEGORIES


def _coerce_float(value: object, default: float = 0.0) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _coerce_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return default


def _build_toilet_result(
    place: PlaceDict,
    info: ToiletScoreInfo,
    lat: float,
    lng: float,
) -> ToiletResultDict | None:
    is_public = is_toilet_place(place)
    if info["toilet_review_count"] == 0 and not is_public:
        category = str(place.get("category") or "").lower()
        title = str(place.get("title") or "").lower()
        if not any(candidate in category or candidate in title for candidate in POTENTIAL_CATEGORIES):
            return None

    display_score = (info["score"] + DISPLAY_SCORE_OFFSET) * DISPLAY_SCORE_MULTIPLIER
    if info["confidence"] <= 0:
        display_score = 50.0

    address = str(place.get("address") or "")
    return {
        "source_id": build_source_id(place, lat=lat, lng=lng),
        "title": str(place.get("title") or ""),
        "category": str(place.get("category") or ""),
        "address": address,
        "lat": lat,
        "lng": lng,
        "phone": str(place.get("phone") or ""),
        "rating": _coerce_float(place.get("review_rating"), 0.0),
        "review_count": _coerce_int(place.get("review_count"), 0),
        "link": str(place.get("link") or ""),
        "is_public_toilet": is_public,
        "toilet_score": round(display_score, 1),
        "confidence": info["confidence"],
        "toilet_review_count": info["toilet_review_count"],
        "top_keywords": info["top_keywords"],
        "sample_reviews": info["toilet_reviews"][:5],
        "prefecture": extract_prefecture(address),
    }


def process_place(place: PlaceDict) -> ToiletResultDict | None:
    lat, lng = _extract_coordinates(place)
    if lat is None or lng is None:
        return None
    if not str(place.get("title") or "").strip():
        return None
    return _build_toilet_result(place, compute_toilet_score(place), lat, lng)


def make_place_key(place: PlaceDict) -> str:
    lat, lng = _extract_coordinates(place)
    if place.get("source_id") or place.get("place_id") or place.get("data_id"):
        return build_source_id(place, lat=lat, lng=lng)

    title = normalize_identity_text(place.get("title"))
    address = normalize_identity_text(place.get("address"))
    if address:
        return f"title_address:{title}|{address}"
    if lat is not None and lng is not None:
        return f"coords:{float(lat):.6f},{float(lng):.6f}"
    return build_source_id(place, lat=lat, lng=lng)


def make_result_key(result: ToiletResultDict | dict) -> str:
    return build_source_id(result)


def load_existing(path: str) -> dict:
    candidates = [path]
    if not path.endswith(".gz"):
        candidates.append(f"{path}.gz")
    for candidate in candidates:
        try:
            if candidate.endswith(".gz"):
                with gzip.open(candidate, "rt", encoding="utf-8") as file:
                    return json.load(file)
            with open(candidate, encoding="utf-8") as file:
                return json.load(file)
        except FileNotFoundError:
            continue
        except json.JSONDecodeError as exc:
            logger.error(f"Failed to parse existing toilet data: {candidate} ({exc})")
            raise
    return {"metadata": None, "toilets": []}


def deduplicate(places: list[PlaceDict]) -> list[PlaceDict]:
    seen: set[str] = set()
    unique: list[PlaceDict] = []
    for place in places:
        key = make_place_key(place)
        if key not in seen:
            seen.add(key)
            unique.append(place)
    return unique


def calc_dynamic_zoom(results: list[ToiletResultDict]) -> int:
    if len(results) < 2:
        return 13
    lats = [result["lat"] for result in results]
    lngs = [result["lng"] for result in results]
    max_range = max(max(lats) - min(lats), max(lngs) - min(lngs))
    thresholds = [(10, 5), (5, 7), (2, 9), (1, 10), (0.5, 11), (0.2, 12), (0.1, 13), (0.05, 14)]
    for threshold, zoom in thresholds:
        if max_range > threshold:
            return zoom
    return 15


def build_metadata(results: list[ToiletResultDict]) -> dict:
    if results:
        center_lat = sum(result["lat"] for result in results) / len(results)
        center_lng = sum(result["lng"] for result in results) / len(results)
    else:
        center_lat, center_lng = 36.2231, 139.3772

    area_name = "検索エリア"
    addresses = [result.get("address", "") for result in results if result.get("address")]
    if addresses and (match := AREA_NAME_RE.search(addresses[0])):
        area_name = match.group(1)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "total": len(results),
        "scored": sum(1 for result in results if result["confidence"] > 0),
        "public_toilets": sum(1 for result in results if result["is_public_toilet"]),
        "center_lat": round(center_lat, 4),
        "center_lng": round(center_lng, 4),
        "zoom": calc_dynamic_zoom(results),
        "area_name": area_name,
        "last_updated": now,
    }


def _normalize_existing_results(existing: dict) -> dict[str, ToiletResultDict]:
    normalized: dict[str, ToiletResultDict] = {}
    for toilet in existing.get("toilets", []):
        item = cast(ToiletResultDict, dict(toilet))
        item["source_id"] = build_source_id(item)
        normalized[item["source_id"]] = item
    return normalized


def process_file(input_path: str, output_path: str, mode: str = "--full") -> None:
    places = cast(list[PlaceDict], load_jsonl(input_path))
    logger.info(f"スクレイプデータ: {len(places)}件")

    unique_places = deduplicate(places)
    logger.info(f"重複除去後: {len(unique_places)}件")

    new_results: dict[str, ToiletResultDict] = {}
    invalid_count = 0
    for index, place in enumerate(unique_places):
        try:
            processed = process_place(place)
        except (TypeError, ValueError, OverflowError) as exc:
            invalid_count += 1
            logger.warning(f"Skipping invalid record #{index}: {exc}")
            continue
        if processed:
            new_results[make_result_key(processed)] = processed
    logger.info(f"新規処理済み: {len(new_results)}件 / 不正データ除外: {invalid_count}件")

    if mode == "--incremental":
        merged = _normalize_existing_results(load_existing(output_path))
        new_count = 0
        updated_count = 0
        for key, result in new_results.items():
            fallback_key = build_fallback_source_id(result)
            if key in merged:
                updated_count += 1
            elif fallback_key in merged:
                merged.pop(fallback_key)
                updated_count += 1
            else:
                new_count += 1
            merged[key] = result
        results = list(merged.values())
        logger.info(
            f"差分マージ: 新規追加 {new_count}件 / 更新 {updated_count}件 / "
            f"既存維持 {len(merged) - new_count - updated_count}件"
        )
    else:
        results = list(new_results.values())
        logger.info(f"フル再生成: {len(results)}件")

    results.sort(key=lambda result: result["toilet_score"], reverse=True)
    metadata = build_metadata(results)
    logger.info(
        f"出力: {len(results)}件 (スコアあり {metadata['scored']}件 / "
        f"公共トイレ {metadata['public_toilets']}件)"
    )
    save_json(output_path, {"metadata": metadata, "toilets": results}, compress=True)


def main() -> None:
    if len(sys.argv) < 3:
        logger.error("Usage: python process_data.py <input.json> <output.json>")
        print("  --full        既存データを無視して全件再生成（デフォルト）")
        print("  --incremental 既存データに差分マージ")
        raise SystemExit(1)
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) > 3 else "--full"
    process_file(input_path, output_path, mode)


if __name__ == "__main__":
    main()
