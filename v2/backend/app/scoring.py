from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

SCORING_VERSION = "keyword-v2"
DIMENSION_SCORING_VERSION = "multidimensional-keyword-v1"
POSITIVE = ("きれい", "綺麗", "清潔", "清掃", "快適", "新しい", "clean", "spotless")
NEGATIVE = ("汚い", "臭い", "不潔", "故障", "詰ま", "虫", "dirty", "smell")


class ScoreDimension(StrEnum):
    CLEANLINESS = "cleanliness"
    ODOR = "odor"
    CONGESTION = "congestion"
    FRESHNESS = "freshness"
    EQUIPMENT = "equipment"
    ACCESSIBILITY = "accessibility"
    CHILD_FRIENDLINESS = "child_friendliness"


@dataclass(frozen=True)
class ScoreResult:
    score: float | None
    confidence: float | None
    matched_reviews: int
    explanation: dict[str, object]


@dataclass(frozen=True)
class DimensionScore:
    dimension: ScoreDimension
    score: float | None
    confidence: float
    evidence_count: int
    positive_matches: int
    negative_matches: int


DIMENSION_TERMS: dict[ScoreDimension, tuple[tuple[str, ...], tuple[str, ...]]] = {
    ScoreDimension.CLEANLINESS: (
        ("きれい", "綺麗", "清潔", "清掃", "clean", "spotless"),
        ("汚い", "不潔", "虫", "dirty"),
    ),
    ScoreDimension.ODOR: (
        ("無臭", "臭わない", "におわない", "odorless"),
        ("臭い", "悪臭", "におい", "smell", "odor"),
    ),
    ScoreDimension.CONGESTION: (
        ("空いて", "すぐ使え", "待たない"),
        ("混雑", "並ん", "待ち時間", "行列"),
    ),
    ScoreDimension.FRESHNESS: (
        ("新しい", "改装", "リニューアル"),
        ("古い", "老朽", "年季"),
    ),
    ScoreDimension.EQUIPMENT: (
        ("温水洗浄", "ウォシュレット", "荷物置き", "着替え台", "フィッティングボード"),
        ("故障", "壊れ", "使えない", "詰ま"),
    ),
    ScoreDimension.ACCESSIBILITY: (
        ("車椅子", "多目的", "バリアフリー", "オストメイト", "手すり"),
        ("段差", "狭い", "車椅子不可"),
    ),
    ScoreDimension.CHILD_FRIENDLINESS: (
        ("おむつ", "ベビー", "子供", "子ども", "キッズ", "ベビーチェア"),
        ("おむつ台なし", "子供不可", "子ども不可"),
    ),
}


def _count_terms(text: str, terms: tuple[str, ...]) -> int:
    normalized = text.casefold()
    return sum(1 for term in terms if term.casefold() in normalized)


def score_review_dimensions(reviews: Iterable[str]) -> dict[ScoreDimension, DimensionScore]:
    texts = [text.strip() for text in reviews if text and text.strip()]
    results: dict[ScoreDimension, DimensionScore] = {}
    for dimension, (positive_terms, negative_terms) in DIMENSION_TERMS.items():
        positive = 0
        negative = 0
        evidence_count = 0
        for text in texts:
            pos = _count_terms(text, positive_terms)
            neg = _count_terms(text, negative_terms)
            if pos or neg:
                evidence_count += 1
                positive += pos
                negative += neg
        score = None if evidence_count == 0 else max(0.0, min(100.0, 50.0 + (positive - negative) * 10.0))
        results[dimension] = DimensionScore(
            dimension=dimension,
            score=score,
            confidence=min(1.0, evidence_count / 5.0),
            evidence_count=evidence_count,
            positive_matches=positive,
            negative_matches=negative,
        )
    return results


def score_reviews(reviews: Iterable[str]) -> ScoreResult:
    texts = [text.strip() for text in reviews if text and text.strip()]
    if not texts:
        return ScoreResult(None, None, 0, {"version": SCORING_VERSION, "reason": "no_reviews"})

    positive = 0
    negative = 0
    matched = 0
    for text in texts:
        normalized = text.casefold()
        pos = sum(1 for word in POSITIVE if word.casefold() in normalized)
        neg = sum(1 for word in NEGATIVE if word.casefold() in normalized)
        if pos or neg:
            matched += 1
            positive += pos
            negative += neg

    if matched == 0:
        return ScoreResult(None, 0.0, 0, {"version": SCORING_VERSION, "reason": "no_toilet_signal"})

    raw = positive - negative
    score = max(0.0, min(100.0, 50.0 + raw * 10.0))
    confidence = min(1.0, matched / 5.0)
    return ScoreResult(
        score,
        confidence,
        matched,
        {
            "version": SCORING_VERSION,
            "positive_matches": positive,
            "negative_matches": negative,
            "review_count": len(texts),
        },
    )
