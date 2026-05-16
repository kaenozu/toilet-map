"""
batch/process_data.py
Google Maps Scraper出力(JSONL)のデータ処理スクリプト

使い方: python process_data.py <input.json> <output.json>
"""
import json
import gzip
import sys
from datetime import datetime
from typing import Optional

from scoring import (
    PlaceDict,
    ToiletScoreInfo,
    ToiletResultDict,
    _extract_coordinates,
    _normalize_identity_text,
    compute_toilet_score,
    is_toilet_place,
)
from scoring_config import AREA_NAME_RE, DISPLAY_SCORE_OFFSET, DISPLAY_SCORE_MULTIPLIER
from app_config import POTENTIAL_CATEGORIES
from utils import load_jsonl, save_json, logger, extract_prefecture


def _build_toilet_result(place: PlaceDict, info: ToiletScoreInfo, lat: float, lng: float) -> Optional[ToiletResultDict]:
    """スコア計算結果から表示用辞書を構築。救済対象外で情報もない場合は None を返す。"""
    is_public = is_toilet_place(place)

    # トイレ関連の口コミが0件で、かつカテゴリー的にもトイレ（または公共・コンビニ等）ではない場合は除外
    if info["toilet_review_count"] == 0 and not is_public:
        # カテゴリーがトイレスポット（公園、駅、コンビニ等）であれば救済
        cat = (place.get("category") or "").lower()
        title = (place.get("title") or "").lower()
        if not any(p in cat or p in title for p in POTENTIAL_CATEGORIES):
            return None

    display_score = (info["score"] + DISPLAY_SCORE_OFFSET) * DISPLAY_SCORE_MULTIPLIER

    # スコアがない地点（口コミなし救済地点）のデフォルト値を調整
    if info["confidence"] <= 0:
        display_score = 50.0  # デフォルト「普通」

    return {
        "title": place.get("title", ""),
        "category": place.get("category", ""),
        "address": place.get("address", ""),
        "lat": lat,
        "lng": lng,
        "phone": place.get("phone", ""),
        "rating": float(place.get("review_rating") or 0),
        "review_count": int(place.get("review_count") or 0),
        "link": place.get("link", ""),
        "is_public_toilet": is_public,
        "toilet_score": round(display_score, 1),
        "confidence": info["confidence"],
        "toilet_review_count": info["toilet_review_count"],
        "top_keywords": info["top_keywords"],
        "sample_reviews": info["toilet_reviews"][:5],
        "prefecture": extract_prefecture(place.get("address", "")),
    }


def process_place(place: PlaceDict) -> Optional[ToiletResultDict]:
    """
    スクレイプされた1地点を処理し、アプリ表示用形式に変換。

    初期チェック:
      - 緯度・経度の存在 → なければ None
      - タイトルの存在 → なければ None

    計算:
      - compute_toilet_score() でスコア・信頼度・キーワードを算出
      - display_score = (score + 5) × 10 で 0-100 スケールへ変換

    戻り値:
      ToiletResultDict 形式の辞書、または None
    """
    lat, lon = _extract_coordinates(place)
    if lat is None or lon is None:
        return None
    title = place.get("title", "")
    if not title:
        return None

    info = compute_toilet_score(place)
    return _build_toilet_result(place, info, lat, lon)


def make_place_key(place: PlaceDict) -> str:
    place_id = str(place.get("place_id") or "").strip()
    if place_id:
        return f"place_id:{place_id}"

    data_id = str(place.get("data_id") or "").strip()
    if data_id:
        return f"data_id:{data_id}"

    lat, lng = _extract_coordinates(place)
    if lat is not None and lng is not None:
        return f"coords:{lat:.6f},{lng:.6f}"

    title = _normalize_identity_text(place.get("title"))
    address = _normalize_identity_text(place.get("address"))
    return f"title_address:{title}|{address}"


def make_result_key(result: ToiletResultDict) -> str:
    return f"coords:{float(result['lat']):.6f},{float(result['lng']):.6f}"


def load_existing(path: str) -> dict:
    candidates = [path]
    if not path.endswith(".gz"):
        candidates.append(f"{path}.gz")
    for candidate in candidates:
        try:
            if candidate.endswith(".gz"):
                with gzip.open(candidate, "rt", encoding="utf-8") as f:
                    return json.load(f)
            with open(candidate, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            continue
        except json.JSONDecodeError as exc:
            logger.error(f"Failed to parse existing toilet data: {candidate} ({exc})")
            raise
    return {"metadata": None, "toilets": []}


def deduplicate(places: list[PlaceDict]) -> list[PlaceDict]:
    seen = set()
    unique = []
    for p in places:
        key = make_place_key(p)
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def calc_dynamic_zoom(results: list[ToiletResultDict]) -> int:
    if len(results) < 2:
        return 13
    lats = [r["lat"] for r in results]
    lngs = [r["lng"] for r in results]
    max_range = max(max(lats) - min(lats), max(lngs) - min(lngs))
    thresholds = [(10, 5), (5, 7), (2, 9), (1, 10), (0.5, 11), (0.2, 12), (0.1, 13), (0.05, 14)]
    for threshold, zoom in thresholds:
        if max_range > threshold:
            return zoom
    return 15


def build_metadata(results: list[ToiletResultDict]) -> dict:
    if results:
        center_lat = sum(r["lat"] for r in results) / len(results)
        center_lng = sum(r["lng"] for r in results) / len(results)
    else:
        center_lat, center_lng = 36.2231, 139.3772

    area_name = "検索エリア"
    if results:
        addrs = [r.get("address", "") for r in results if r.get("address")]
        if addrs:
            m = AREA_NAME_RE.search(addrs[0])
            if m:
                area_name = m.group(1)

    zoom = calc_dynamic_zoom(results)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return {
        "total": len(results),
        "scored": sum(1 for r in results if r["confidence"] > 0),
        "public_toilets": sum(1 for r in results if r["is_public_toilet"]),
        "center_lat": round(center_lat, 4),
        "center_lng": round(center_lng, 4),
        "zoom": zoom,
        "area_name": area_name,
        "last_updated": now,
    }


def process_file(input_path: str, output_path: str, mode: str = "--full"):
    places = load_jsonl(input_path)
    logger.info(f"スクレイプデータ: {len(places)}件")

    unique_places = deduplicate(places)
    logger.info(f"重複除去後: {len(unique_places)}件")

    new_results = {}
    for place in unique_places:
        processed = process_place(place)
        if processed:
            new_results[make_result_key(processed)] = processed
    logger.info(f"新規処理済み: {len(new_results)}件")

    if mode == "--incremental":
        existing = load_existing(output_path)
        merged = {make_result_key(t): t for t in existing.get("toilets", [])}
        new_count = sum(1 for k in new_results if k not in merged)
        updated_count = sum(1 for k in new_results if k in merged)
        merged.update(new_results)
        results = list(merged.values())
        logger.info(f"差分マージ: 新規追加 {new_count}件 / 更新 {updated_count}件 / 既存維持 {len(merged) - new_count - updated_count}件")
        metadata = build_metadata(results)
    else:
        results = list(new_results.values())
        metadata = build_metadata(results)
        logger.info(f"フル再生成: {len(results)}件")

    results.sort(key=lambda x: x["toilet_score"], reverse=True)
    metadata["total"] = len(results)
    metadata["scored"] = sum(1 for r in results if r["confidence"] > 0)
    metadata["public_toilets"] = sum(1 for r in results if r["is_public_toilet"])

    logger.info(f"出力: {len(results)}件 (スコアあり {metadata['scored']}件 / 公共トイレ {metadata['public_toilets']}件)")

    save_json(output_path, {"metadata": metadata, "toilets": results}, compress=True)


def main():
    if len(sys.argv) < 3:
        logger.error("Usage: python process_data.py <input.json> <output.json>")
        print("  --full        既存データを無視して全件再生成（デフォルト）")
        print("  --incremental 既存データに差分マージ")
        sys.exit(1)
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) > 3 else "--full"
    process_file(input_path, output_path, mode)


if __name__ == "__main__":
    main()
