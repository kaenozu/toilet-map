"""
batch/process_data.py
Google Maps Scraper出力(JSONL)のデータ処理スクリプト

使い方: python process_data.py <input.json> <output.json>
"""
import json
import re
import sys
from collections import Counter
from datetime import datetime
from scoring_config import (
    SCORE_CLAMP_MIN,
    SCORE_CLAMP_MAX,
    DISPLAY_SCORE_OFFSET,
    DISPLAY_SCORE_MULTIPLIER,
    CONFIDENCE_MAX_REVIEWS,
    CONFIDENCE_LOW,
    RATING_THRESHOLD_HIGH,
    RATING_THRESHOLD_LOW,
    POSITIVE_BOOST_HIGH,
    NEGATIVE_DAMPEN_HIGH,
    POSITIVE_DAMPEN_LOW,
    NEGATIVE_BOOST_LOW,
    NEGATION_WINDOW,
    NEGATION_WORDS,
    POSITIVE_KEYWORDS,
    NEGATIVE_KEYWORDS,
    SENTENCE_SPLIT_RE,
    TOILET_MENTION_RE,
    AREA_NAME_RE,
    PREFECTURES,
    TOILET_CATEGORIES,
)


def mentions_toilet(text: str) -> bool:
    return bool(TOILET_MENTION_RE.search(text))


def extract_toilet_contexts(text: str) -> list[str]:
    sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]
    toilet_indices = set()
    for i, sent in enumerate(sentences):
        if mentions_toilet(sent):
            for j in range(max(0, i - 1), min(len(sentences), i + 2)):
                toilet_indices.add(j)
    return [sentences[i] for i in sorted(toilet_indices)] if toilet_indices else []


def _apply_keyword_scoring(target_text: str):
    score = 0.0
    matched = []
    for kw, val in POSITIVE_KEYWORDS.items():
        cnt = target_text.count(kw)
        if cnt > 0:
            score += val * cnt
            matched.append(f"+{kw}")
    for kw, val in NEGATIVE_KEYWORDS.items():
        cnt = target_text.count(kw)
        if cnt > 0:
            score += val * cnt
            matched.append(f"-{kw}")
    return score, matched


def _apply_negation_correction(target_text: str, score: float, matched: list[str]):
    for neg_word in NEGATION_WORDS:
        if neg_word not in target_text:
            continue
        neg_positions = [m.start() for m in re.finditer(re.escape(neg_word), target_text)]
        for kw, val in POSITIVE_KEYWORDS.items():
            if kw not in target_text:
                continue
            kw_positions = [m.start() for m in re.finditer(re.escape(kw), target_text)]
            cancelled = False
            for kp in kw_positions:
                for np in neg_positions:
                    if abs(kp - np) < NEGATION_WINDOW:
                        score -= val
                        tag = f"+{kw}"
                        if tag in matched:
                            matched.remove(tag)
                        cancelled = True
                        break
                if cancelled:
                    break
    return score, matched


def score_toilet_from_review(text: str):
    contexts = extract_toilet_contexts(text) or [text]
    target_text = "。".join(contexts)
    score, matched = _apply_keyword_scoring(target_text)
    score, matched = _apply_negation_correction(target_text, score, matched)
    return max(SCORE_CLAMP_MIN, min(SCORE_CLAMP_MAX, score)), matched


def extract_prefecture(address: str) -> str:
    if not address:
        return ""
    for pref in PREFECTURES:
        if pref in address:
            return pref
    return ""


def _adjust_by_rating(score: float, matched: list[str], rating: float):
    if rating >= RATING_THRESHOLD_HIGH:
        if score < 0:
            score *= NEGATIVE_DAMPEN_HIGH
            matched = [m for m in matched if not m.startswith("-")] + \
                       [f"~{m[1:]}" for m in matched if m.startswith("-")]
        elif score > 0:
            score *= POSITIVE_BOOST_HIGH
    elif rating <= RATING_THRESHOLD_LOW:
        if score > 0:
            score *= POSITIVE_DAMPEN_LOW
            matched = [m for m in matched if not m.startswith("+")] + \
                       [f"~{m[1:]}" for m in matched if m.startswith("+")]
        elif score < 0:
            score *= NEGATIVE_BOOST_LOW
    return score, matched


def compute_toilet_score(place: dict) -> dict:
    reviews = (place.get("user_reviews") or []) + (place.get("user_reviews_extended") or [])
    toilet_reviews = []
    total_score = 0.0
    all_highlights = []
    seen_descs = set()

    for r in reviews:
        desc = r.get("Description", "")
        if not desc or not desc.strip() or not mentions_toilet(desc):
            continue
        desc_key = desc.strip()[:100]
        if desc_key in seen_descs:
            continue
        seen_descs.add(desc_key)

        s, matched = score_toilet_from_review(desc)
        rating = float(r.get("Rating") or 0)
        s, matched = _adjust_by_rating(s, matched, rating)
        s = max(SCORE_CLAMP_MIN, min(SCORE_CLAMP_MAX, s))

        toilet_reviews.append({
            "text": desc,
            "rating": r.get("Rating"),
            "when": r.get("When"),
            "name": r.get("Name"),
            "score": round(s, 2),
            "matched_keywords": matched,
            "toilet_context": "。".join(extract_toilet_contexts(desc)),
        })
        total_score += s
        all_highlights.extend(matched)

    if toilet_reviews:
        avg_score = total_score / len(toilet_reviews)
        place_rating = float(place.get("review_rating") or 0)
        final_score = avg_score * 0.7 + (place_rating - 3.0) * 0.3
        confidence = min(1.0, len(toilet_reviews) / CONFIDENCE_MAX_REVIEWS)
    else:
        place_rating = float(place.get("review_rating") or 0)
        if place_rating > 0:
            final_score = (place_rating - 3.0) * 0.5
            confidence = CONFIDENCE_LOW
        else:
            final_score = 0.0
            confidence = 0.0

    final_score = max(SCORE_CLAMP_MIN, min(SCORE_CLAMP_MAX, final_score))
    highlight_counts = Counter(all_highlights)

    return {
        "score": round(final_score, 2),
        "confidence": round(confidence, 2),
        "toilet_review_count": len(toilet_reviews),
        "toilet_reviews": toilet_reviews[:20],
        "top_keywords": highlight_counts.most_common(5),
    }


def is_toilet_place(place: dict) -> bool:
    cat = (place.get("category") or "").lower()
    title = (place.get("title") or "").lower()
    return any(tc.lower() in cat or tc.lower() in title for tc in TOILET_CATEGORIES)


def process_place(place: dict) -> dict | None:
    lat = place.get("latitude")
    lon = place.get("longitude") or place.get("longtitude")
    if not lat or not lon:
        return None
    title = place.get("title", "")
    if not title:
        return None

    info = compute_toilet_score(place)
    display_score = (info["score"] + DISPLAY_SCORE_OFFSET) * DISPLAY_SCORE_MULTIPLIER

    return {
        "title": title,
        "category": place.get("category", ""),
        "address": place.get("address", ""),
        "lat": float(lat),
        "lng": float(lon),
        "phone": place.get("phone", ""),
        "rating": float(place.get("review_rating") or 0),
        "review_count": int(place.get("review_count") or 0),
        "link": place.get("link", ""),
        "is_public_toilet": is_toilet_place(place),
        "toilet_score": round(display_score, 1),
        "confidence": info["confidence"],
        "toilet_review_count": info["toilet_review_count"],
        "top_keywords": info["top_keywords"],
        "sample_reviews": info["toilet_reviews"][:5],
        "prefecture": extract_prefecture(place.get("address", "")),
    }


def make_place_key(place: dict) -> str:
    lat = float(place.get("latitude") or 0)
    lng = float(place.get("longitude") or place.get("longtitude") or 0)
    return f"{place.get('title', '')}@{lat:.4f},{lng:.4f}"


def make_result_key(result: dict) -> str:
    return f"{result['title']}@{result['lat']:.4f},{result['lng']:.4f}"


def load_jsonl(path: str) -> list[dict]:
    places = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                places.append(json.loads(line))
    return places


def load_existing(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"metadata": None, "toilets": []}


def deduplicate(places: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for p in places:
        key = make_place_key(p)
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def calc_dynamic_zoom(results: list[dict]) -> int:
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


def build_metadata(results: list[dict]) -> dict:
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
    now = datetime.now().strftime("%Y-%m-%d")

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
    print(f"スクレイプデータ: {len(places)}件")

    unique_places = deduplicate(places)
    print(f"重複除去後: {len(unique_places)}件")

    new_results = {}
    for place in unique_places:
        processed = process_place(place)
        if processed:
            new_results[make_result_key(processed)] = processed
    print(f"新規処理済み: {len(new_results)}件")

    if mode == "--incremental":
        existing = load_existing(output_path)
        merged = {make_result_key(t): t for t in existing.get("toilets", [])}
        new_count = sum(1 for k in new_results if k not in merged)
        updated_count = sum(1 for k in new_results if k in merged)
        merged.update(new_results)
        results = list(merged.values())
        print(f"差分マージ: 新規追加 {new_count}件 / 更新 {updated_count}件 / 既存維持 {len(merged) - new_count - updated_count}件")
        metadata = existing.get("metadata") or build_metadata(results)
    else:
        results = list(new_results.values())
        metadata = build_metadata(results)
        print(f"フル再生成: {len(results)}件")

    results.sort(key=lambda x: x["toilet_score"], reverse=True)
    metadata["total"] = len(results)
    metadata["scored"] = sum(1 for r in results if r["confidence"] > 0)
    metadata["public_toilets"] = sum(1 for r in results if r["is_public_toilet"])

    print(f"出力: {len(results)}件 (スコアあり {metadata['scored']}件 / 公共トイレ {metadata['public_toilets']}件)")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"metadata": metadata, "toilets": results}, f, ensure_ascii=False, indent=2)
    print(f"出力完了: {output_path}")


def main():
    if len(sys.argv) < 3:
        print("Usage: python process_data.py <input.json> <output.json>")
        print("  --full        既存データを無視して全件再生成（デフォルト）")
        print("  --incremental 既存データに差分マージ")
        sys.exit(1)
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) > 3 else "--full"
    process_file(input_path, output_path, mode)


if __name__ == "__main__":
    main()