"""
batch/models.py
Pydantic models for toilet record validation and data integrity.
Related: batch/process_data.py, batch/verify_data.py, batch/to_sqlite.py
"""
from pydantic import BaseModel


class ToiletRecord(BaseModel):
    place_id: str
    title: str | None = None
    lat: float | None = None
    lng: float | None = None
    score: float | None = None
    review_count: int = 0
    rating: float | None = None
    address: str | None = None
    prefecture: str | None = None
    link: str | None = None
    sample_reviews_json: str = ""
    top_keywords: str = ""
    updated_at: str | None = None

    @classmethod
    def validate_record(cls, data: dict) -> "ToiletRecord":
        cleaned = {k: v for k, v in data.items() if k in cls.model_fields}
        return cls(**cleaned)


class Metadata(BaseModel):
    key: str
    value: str
