from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

SCORING_VERSION = "keyword-v2"
POSITIVE = ("きれい", "綺麗", "清潔", "清掃", "快適", "新しい", "clean", "spotless")
NEGATIVE = ("汚い", "臭い", "不潔", "故障", "詰ま", "虫", "dirty", "smell")


@dataclass(frozen=True)
class ScoreResult:
    score: float | None
    confidence: float | None
    matched_reviews: int
    explanation: dict[str, object]


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
