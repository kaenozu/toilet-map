"""Deterministic aggregate and dimensional keyword scoring."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

SCORING_VERSION = "keyword-v3"
DIMENSION_SCORING_VERSION = "multidimensional-keyword-v2"
POSITIVE = (
    "きれい", "綺麗", "清潔", "清掃", "快適", "新しい",
    "clean", "spotless",
    "衛生的", "ピカピカ", "掃除", "磨か",
    "気持ちいい", "香り", "アロマ",
    "除菌", "消毒", "清潔感",
    "広い", "明るい", "暖房", "使いやすい",
    "洋式", "最新", "自動洗浄", "ウォシュレット",
    "個室", "音楽",
)
NEGATIVE = (
    "汚い", "臭い", "不潔", "故障", "詰ま", "虫",
    "dirty", "smell",
    "汚れ", "カビ", "錆", "水漏れ", "水浸し",
    "紙切れ", "流れない", "水圧",
    "暗い", "怖い", "危ない", "廃墟", "ぼろ",
    "閉鎖", "工事中", "有料",
    "入りづらい", "立ち入り禁止",
)


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
    confidence: float
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
        ("きれい", "綺麗", "清潔", "清掃", "clean", "spotless",
         "ピカピカ", "掃除", "磨か", "除菌", "消毒"),
        ("汚い", "不潔", "虫", "dirty", "汚れ", "カビ", "ぼろ"),
    ),
    ScoreDimension.ODOR: (
        ("無臭", "臭わない", "におわない", "odorless",
         "香り", "アロマ"),
        ("臭い", "悪臭", "におい", "smell", "odor", "臭"),
    ),
    ScoreDimension.CONGESTION: (
        ("空いて", "すぐ使え", "待たない"),
        ("混雑", "並ん", "待ち時間", "行列", "人が多い", "長蛇"),
    ),
    ScoreDimension.FRESHNESS: (
        ("新しい", "改装", "リニューアル", "最新"),
        ("古い", "老朽", "年季", "廃墟"),
    ),
    ScoreDimension.EQUIPMENT: (
        ("温水洗浄", "ウォシュレット", "荷物置き", "着替え台", "フィッティングボード",
         "自動洗浄", "暖房", "音楽", "洋式"),
        ("故障", "壊れ", "使えない", "詰ま", "流れない",
         "水漏れ", "水浸し", "紙切れ", "閉鎖", "工事中"),
    ),
    ScoreDimension.ACCESSIBILITY: (
        ("車椅子", "多目的", "バリアフリー", "オストメイト", "手すり",
         "スロープ", "エレベーター"),
        ("段差", "狭い", "車椅子不可", "階段", "入りづらい"),
    ),
    ScoreDimension.CHILD_FRIENDLINESS: (
        ("おむつ", "ベビー", "子供", "子ども", "キッズ", "ベビーチェア",
         "おむつ台", "授乳"),
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
        score = None if evidence_count == 0 else max(0.0, min(100.0, 50.0 + (positive - negative) * 7.0))
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
        return ScoreResult(None, 0.0, 0, {"version": SCORING_VERSION, "reason": "no_reviews"})

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
    score = max(0.0, min(100.0, 50.0 + raw * 7.0))
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
