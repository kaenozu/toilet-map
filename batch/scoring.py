# mypy: disable-error-code="no-redef"
"""Review scoring and confidence calculation."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import TypedDict

try:
    from .identity import normalize_identity_text
    from .scoring_config import (
        CONFIDENCE_MIN,
        CONFIDENCE_REVIEW_FACTOR,
        NEGATION_WINDOW,
        NEGATION_WORDS,
        NEGATIVE_BOOST_LOW,
        NEGATIVE_DAMPEN_HIGH,
        NEGATIVE_KEYWORDS,
        POSITIVE_BOOST_HIGH,
        POSITIVE_DAMPEN_LOW,
        POSITIVE_KEYWORDS,
        RATING_THRESHOLD_HIGH,
        RATING_THRESHOLD_LOW,
        SCORE_CLAMP_MAX,
        SCORE_CLAMP_MIN,
        SENTENCE_SPLIT_RE,
        TOILET_CATEGORIES,
        TOILET_MENTION_RE,
    )
except ImportError:
    from identity import normalize_identity_text
    from scoring_config import (
        CONFIDENCE_MIN,
        CONFIDENCE_REVIEW_FACTOR,
        NEGATION_WINDOW,
        NEGATION_WORDS,
        NEGATIVE_BOOST_LOW,
        NEGATIVE_DAMPEN_HIGH,
        NEGATIVE_KEYWORDS,
        POSITIVE_BOOST_HIGH,
        POSITIVE_DAMPEN_LOW,
        POSITIVE_KEYWORDS,
        RATING_THRESHOLD_HIGH,
        RATING_THRESHOLD_LOW,
        SCORE_CLAMP_MAX,
        SCORE_CLAMP_MIN,
        SENTENCE_SPLIT_RE,
        TOILET_CATEGORIES,
        TOILET_MENTION_RE,
    )


class PlaceDict(TypedDict, total=False):
    title: str
    category: str
    address: str
    latitude: float
    longitude: float
    longtitude: float
    place_id: str
    data_id: str
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
    source_id: str
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
CLAUSE_SPLIT_RE = re.compile(r"(?<=[。.!！?？])|(?:が|けれど|けど|しかし|ただし|but|however)[、,\s]+", re.IGNORECASE)

_POS_PATTERN = re.compile("|".join(re.escape(k) for k in sorted(POSITIVE_KEYWORDS, key=len, reverse=True)))
_NEG_PATTERN = re.compile("|".join(re.escape(k) for k in sorted(NEGATIVE_KEYWORDS, key=len, reverse=True)))
_NEGATION_PATTERN = re.compile("|".join(re.escape(w) for w in sorted(NEGATION_WORDS, key=len, reverse=True)))


def _normalize_identity_text(value: object) -> str:
    """Backward-compatible wrapper used by older tests and callers."""
    return normalize_identity_text(value)


def _coerce_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _toilet_clauses(text: str) -> list[str]:
    return [clause.strip() for clause in CLAUSE_SPLIT_RE.split(text) if clause.strip() and TOILET_MENTION_RE.search(clause)]


def mentions_toilet(text: str) -> bool:
    if not text or not TOILET_MENTION_RE.search(text):
        return False
    clauses = _toilet_clauses(text)
    return any(not TOILET_ABSENCE_RE.search(clause) for clause in clauses)


def _get_longitude(place: PlaceDict) -> float | None:
    raw = place.get("longitude")
    legacy_raw = place.get("longtitude")
    if raw is None or raw == "" or (raw == 0 and legacy_raw not in (None, "", 0)):
        raw = legacy_raw
    if raw is None or raw == "":
        return None
    value = _coerce_float(raw, default=float("nan"))
    return value if math.isfinite(value) else None


def _extract_coordinates(place: PlaceDict) -> tuple[float | None, float | None]:
    raw_lat = place.get("latitude")
    if raw_lat is None or raw_lat == "":
        return None, _get_longitude(place)
    lat: float | None = _coerce_float(raw_lat, default=float("nan"))
    lon = _get_longitude(place)
    if lat is not None and not math.isfinite(lat):
        lat = None
    if lat is not None and not -90 <= lat <= 90:
        lat = None
    if lon is not None and not -180 <= lon <= 180:
        lon = None
    return lat, lon


def extract_toilet_contexts(text: str) -> list[str]:
    sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]
    toilet_indices: set[int] = set()
    for i, sentence in enumerate(sentences):
        if mentions_toilet(sentence):
            toilet_indices.update(range(max(0, i - 1), min(len(sentences), i + 2)))
    contexts: list[str] = []
    for i in sorted(toilet_indices):
        sentence = sentences[i]
        if TOILET_MENTION_RE.search(sentence):
            valid_clauses = [clause for clause in _toilet_clauses(sentence) if not TOILET_ABSENCE_RE.search(clause)]
            if valid_clauses:
                contexts.extend(valid_clauses)
                continue
        contexts.append(sentence)
    return contexts


def _is_externally_negated(text: str, start: int, end: int) -> bool:
    """Detect a suffix negation without matching ``ない`` inside the phrase itself."""
    del start
    suffix = text[end : end + NEGATION_WINDOW]
    connector = r"^[\s、,はがをもにとでじゃ]*"
    return re.search(connector + _NEGATION_PATTERN.pattern, suffix) is not None


def _apply_scoring_and_negation(target_text: str) -> tuple[float, list[str]]:
    score = 0.0
    matched_tags: list[str] = []

    for match in _POS_PATTERN.finditer(target_text):
        keyword = match.group()
        if not _is_externally_negated(target_text, match.start(), match.end()):
            score += POSITIVE_KEYWORDS[keyword]
            matched_tags.append(f"+{keyword}")

    for match in _NEG_PATTERN.finditer(target_text):
        keyword = match.group()
        if _is_externally_negated(target_text, match.start(), match.end()):
            matched_tags.append(f"~{keyword}")
        else:
            score += NEGATIVE_KEYWORDS[keyword]
            matched_tags.append(f"-{keyword}")

    return score, matched_tags


def score_toilet_from_review(text: str) -> tuple[float, list[str]]:
    contexts = extract_toilet_contexts(text) or [text]
    score, matched = _apply_scoring_and_negation("。".join(contexts))
    return max(SCORE_CLAMP_MIN, min(SCORE_CLAMP_MAX, score)), matched


def _adjust_by_rating(score: float, matched: list[str], rating: float) -> tuple[float, list[str]]:
    if rating >= RATING_THRESHOLD_HIGH:
        if score < 0:
            score *= NEGATIVE_DAMPEN_HIGH
            matched = [m for m in matched if not m.startswith("-")] + [f"~{m[1:]}" for m in matched if m.startswith("-")]
        elif score > 0:
            score *= POSITIVE_BOOST_HIGH
    elif rating <= RATING_THRESHOLD_LOW:
        if score > 0:
            score *= POSITIVE_DAMPEN_LOW
            matched = [m for m in matched if not m.startswith("+")] + [f"~{m[1:]}" for m in matched if m.startswith("+")]
        elif score < 0:
            score *= NEGATIVE_BOOST_LOW
    return score, matched


def _collect_toilet_reviews(place: PlaceDict) -> tuple[list[ToiletReviewDict], list[str]]:
    reviews = (place.get("user_reviews") or []) + (place.get("user_reviews_extended") or [])
    toilet_reviews: list[ToiletReviewDict] = []
    all_highlights: list[str] = []
    seen_descriptions: set[str] = set()

    for review in reviews:
        description = str(review.get("Description") or "")
        if not description.strip() or not mentions_toilet(description):
            continue
        description_key = description.strip()
        if description_key in seen_descriptions:
            continue
        seen_descriptions.add(description_key)

        review_score, matched = score_toilet_from_review(description)
        rating = _coerce_float(review.get("Rating"), 0.0)
        review_score, matched = _adjust_by_rating(review_score, matched, rating)
        review_score = max(SCORE_CLAMP_MIN, min(SCORE_CLAMP_MAX, review_score))

        toilet_reviews.append({
            "text": description,
            "rating": review.get("Rating"),
            "when": review.get("When"),
            "name": review.get("Name"),
            "score": round(review_score, 2),
            "matched_keywords": matched,
            "toilet_context": "。".join(extract_toilet_contexts(description)),
        })
        all_highlights.extend(matched)

    return toilet_reviews, all_highlights


def _calculate_final_score(
    toilet_reviews: list[ToiletReviewDict],
    place_rating: float,
    total_score: float,
) -> tuple[float, float]:
    if toilet_reviews:
        average_score = total_score / len(toilet_reviews)
        final_score = average_score * 0.7 + (place_rating - 3.0) * 0.3
        confidence = min(1.0, len(toilet_reviews) / CONFIDENCE_REVIEW_FACTOR)
    elif place_rating > 0:
        final_score = (place_rating - 3.0) * 0.5
        confidence = CONFIDENCE_MIN
    else:
        final_score = 0.0
        confidence = 0.0
    return max(SCORE_CLAMP_MIN, min(SCORE_CLAMP_MAX, final_score)), confidence


def compute_toilet_score(place: PlaceDict) -> ToiletScoreInfo:
    toilet_reviews, highlights = _collect_toilet_reviews(place)
    total_score = sum(review["score"] for review in toilet_reviews)
    place_rating = _coerce_float(place.get("review_rating"), 0.0)
    final_score, confidence = _calculate_final_score(toilet_reviews, place_rating, total_score)
    return {
        "score": round(final_score, 2),
        "confidence": round(confidence, 2),
        "toilet_review_count": len(toilet_reviews),
        "toilet_reviews": toilet_reviews[:20],
        "top_keywords": Counter(highlights).most_common(5),
    }


def is_toilet_place(place: PlaceDict) -> bool:
    category = str(place.get("category") or "").lower()
    title = str(place.get("title") or "").lower()
    return any(keyword.lower() in category or keyword.lower() in title for keyword in TOILET_CATEGORIES)
