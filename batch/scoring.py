"""
batch/scoring.py
スコアリングロジック（process_data.py から抽出）
レビューからのトイレスコア計算・信頼度算出・キーワード抽出
"""
import os
import re
import sys
from collections import Counter
from typing import Optional, TypedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scoring_config import (
    SCORE_CLAMP_MIN,
    SCORE_CLAMP_MAX,
    CONFIDENCE_REVIEW_FACTOR,
    CONFIDENCE_MIN,
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
    TOILET_CATEGORIES,
)
from utils import logger as _unused_logger  # noqa: F401


class PlaceDict(TypedDict, total=False):
    title: str
    category: str
    address: str
    latitude: float
    longitude: float
    phone: str
    review_rating: float
    review_count: int
    link: str
    user_reviews: list[dict]
    user_reviews_extended: list[dict]


class ToiletReviewDict(TypedDict):
    text: str
    rating: float | str | None
    when: str | None
    name: str | None
    score: float
    matched_keywords: list[str]
    toilet_context: str


class ToiletScoreInfo(TypedDict):
    score: float
    confidence: float
    toilet_review_count: int
    toilet_reviews: list[ToiletReviewDict]
    top_keywords: list[tuple[str, int]]


class ToiletResultDict(TypedDict):
    title: str
    category: str
    address: str
    lat: float
    lng: float
    phone: str
    rating: float
    review_count: int
    link: str
    is_public_toilet: bool
    toilet_score: float
    confidence: float
    toilet_review_count: int
    top_keywords: list[tuple[str, int]]
    sample_reviews: list[ToiletReviewDict]
    prefecture: str


TOILET_ABSENCE_PATTERNS = [
    r"(?:トイレ|お手洗い|化粧室|洗面所|bathroom|restroom|washroom)\s*(?:が|は|も|を)?\s*(?:ない|なし|ありません|無い|無し|未設置)(?:\s|$|[。、!！?？])",
    r"(?:no|not)\s+(?:toilet|restroom|washroom|bathroom)s?(?:\s|$|[.!?])",
    r"toilet\s+(?:not\s+available|unavailable|missing)",
    r"トイレ\s*(?:なし|無い|ない|未設置)(?:\s|$|[。、])",
]
TOILET_ABSENCE_RE = re.compile("|".join(TOILET_ABSENCE_PATTERNS), re.IGNORECASE)

_POS_SORTED = sorted(POSITIVE_KEYWORDS.keys(), key=len, reverse=True)
_NEG_SORTED = sorted(NEGATIVE_KEYWORDS.keys(), key=len, reverse=True)
_POS_PATTERN = re.compile('|'.join(re.escape(k) for k in _POS_SORTED))
_NEG_PATTERN = re.compile('|'.join(re.escape(k) for k in _NEG_SORTED))
_NEGATION_PATTERN = re.compile('|'.join(re.escape(w) for w in NEGATION_WORDS))


def _normalize_identity_text(value: object) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def mentions_toilet(text: str) -> bool:
    if not text or not TOILET_MENTION_RE.search(text):
        return False
    if TOILET_ABSENCE_RE.search(text):
        return False
    return True


def _get_longitude(place: PlaceDict) -> float:
    lon = place.get("longitude")
    if lon is None:
        lon = place.get("longtitude")
    return float(lon or 0)


def extract_toilet_contexts(text: str) -> list[str]:
    sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]
    toilet_indices = set()
    for i, sent in enumerate(sentences):
        if mentions_toilet(sent):
            for j in range(max(0, i - 1), min(len(sentences), i + 2)):
                toilet_indices.add(j)
    return [sentences[i] for i in sorted(toilet_indices)] if toilet_indices else []


def _apply_scoring_and_negation(target_text: str) -> tuple[float, list[str]]:
    score = 0.0
    matched_tags = []

    neg_word_positions = [m.start() for m in _NEGATION_PATTERN.finditer(target_text)]

    def is_negated(pos: int) -> bool:
        for np in neg_word_positions:
            if abs(pos - np) < NEGATION_WINDOW:
                return True
        return False

    for m in _POS_PATTERN.finditer(target_text):
        kw = m.group()
        val = POSITIVE_KEYWORDS[kw]
        if not is_negated(m.start()):
            score += val
            matched_tags.append(f"+{kw}")

    for m in _NEG_PATTERN.finditer(target_text):
        kw = m.group()
        val = NEGATIVE_KEYWORDS[kw]
        if is_negated(m.start()):
            matched_tags.append(f"~{kw}")
        else:
            score += val
            matched_tags.append(f"-{kw}")

    return score, matched_tags


def score_toilet_from_review(text: str) -> tuple[float, list[str]]:
    contexts = extract_toilet_contexts(text) or [text]
    target_text = "。".join(contexts)
    score, matched = _apply_scoring_and_negation(target_text)
    return max(SCORE_CLAMP_MIN, min(SCORE_CLAMP_MAX, score)), matched


def _adjust_by_rating(score: float, matched: list[str], rating: float) -> tuple[float, list[str]]:
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


def _collect_toilet_reviews(
    place: PlaceDict,
) -> tuple[list[dict], list[str]]:
    reviews = (place.get("user_reviews") or []) + (place.get("user_reviews_extended") or [])
    toilet_reviews = []
    all_highlights = []
    seen_descs: set[int] = set()

    for r in reviews:
        desc = r.get("Description", "")
        if not desc or not desc.strip() or not mentions_toilet(desc):
            continue
        desc_hash = hash(desc.strip())
        if desc_hash in seen_descs:
            continue
        seen_descs.add(desc_hash)

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
        all_highlights.extend(matched)

    return toilet_reviews, all_highlights


def _calculate_final_score(
    toilet_reviews: list[dict],
    place_rating: float,
    total_score: float,
) -> tuple[float, float]:
    if toilet_reviews:
        avg_score = total_score / len(toilet_reviews)
        final_score = avg_score * 0.7 + (place_rating - 3.0) * 0.3
        confidence = min(1.0, len(toilet_reviews) / CONFIDENCE_REVIEW_FACTOR)
    else:
        if place_rating > 0:
            final_score = (place_rating - 3.0) * 0.5
            confidence = CONFIDENCE_MIN
        else:
            final_score = 0.0
            confidence = 0.0
    final_score = max(SCORE_CLAMP_MIN, min(SCORE_CLAMP_MAX, final_score))
    return final_score, confidence


def compute_toilet_score(place: PlaceDict) -> ToiletScoreInfo:
    toilet_reviews, all_highlights = _collect_toilet_reviews(place)
    total_score = sum(r["score"] for r in toilet_reviews)
    place_rating = float(place.get("review_rating") or 0)
    final_score, confidence = _calculate_final_score(
        toilet_reviews, place_rating, total_score,
    )

    highlight_counts = Counter(all_highlights)
    return {
        "score": round(final_score, 2),
        "confidence": round(confidence, 2),
        "toilet_review_count": len(toilet_reviews),
        "toilet_reviews": toilet_reviews[:20],
        "top_keywords": highlight_counts.most_common(5),
    }


def is_toilet_place(place: PlaceDict) -> bool:
    cat = (place.get("category") or "").lower()
    title = (place.get("title") or "").lower()
    return any(tc.lower() in cat or tc.lower() in title for tc in TOILET_CATEGORIES)


def _extract_coordinates(place: PlaceDict) -> tuple[Optional[float], Optional[float]]:
    lat = place.get("latitude")
    lon = place.get("longitude")
    if lon is None:
        lon = place.get("longtitude")
    if lat is not None and lon == 0:
        alt_lon = place.get("longtitude")
        if alt_lon is not None:
            lon = alt_lon
    return lat, lon
