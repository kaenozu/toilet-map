"""
ui/types.py
Shared TypedDict definitions for UI components
"""
from typing import TypedDict


class ToiletDict(TypedDict, total=False):
    """トイレデータの型定義"""
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
    place_id: str
    data_id: str
    toilet_score: float
    confidence: float
    toilet_review_count: int
    top_keywords: list[tuple[str, int]]
    sample_reviews: list[dict[str, object]]
    prefecture: str
    distance: float | None
    ai_sentiment_score: float | None
    ai_cleanliness_summary: str | None
    ai_keywords: list[str]
    ai_confidence: float

