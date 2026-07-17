from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ScoreStatus(StrEnum):
    RATED = "rated"
    PROVISIONAL = "provisional"
    UNRATED = "unrated"
    INSUFFICIENT_DATA = "insufficient_data"
    EXCLUDED = "excluded"


@dataclass(frozen=True, slots=True)
class ToiletRecord:
    id: str
    place_id: str
    title: str
    category: str | None
    address: str | None
    latitude: float
    longitude: float
    score: float | None
    confidence: float
    review_count: int
    score_status: ScoreStatus
    scoring_version: str

    def __post_init__(self) -> None:
        if not -90 <= self.latitude <= 90:
            raise ValueError("latitude must be between -90 and 90")
        if not -180 <= self.longitude <= 180:
            raise ValueError("longitude must be between -180 and 180")
        if self.score is not None and not 0 <= self.score <= 100:
            raise ValueError("score must be between 0 and 100")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if self.review_count < 0:
            raise ValueError("review_count must be non-negative")
        if self.score_status is ScoreStatus.UNRATED and self.score is not None:
            raise ValueError("unrated records cannot have a score")
