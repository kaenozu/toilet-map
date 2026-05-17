"""
batch/ai_scoring.py
Gemini AI-powered review analysis for enhanced scoring.
Uses the google-genai SDK (Gemini Interactions API).

Related: batch/scoring.py, batch/process_data.py, ui/popups.py
"""
import json
import logging
import os

from google import genai

logger = logging.getLogger(__name__)

# Model configuration
_GEMINI_MODEL = os.environ.get("TOILET_MAP_GEMINI_MODEL", "gemini-2.0-flash")
_GEMINI_API_KEY = os.environ.get("TOILET_MAP_GEMINI_API_KEY", "")


def is_available() -> bool:
    """Check if Gemini API key is configured."""
    return bool(_GEMINI_API_KEY)


def _get_client() -> genai.Client | None:
    """Create a Gemini client if API key is available."""
    if not _GEMINI_API_KEY:
        return None
    return genai.Client(api_key=_GEMINI_API_KEY)


def analyze_reviews(reviews: list[dict], toilet_name: str) -> dict:
    """
    Analyze toilet reviews using Gemini and return enhanced scoring data.

    Returns:
        dict with keys: sentiment_score (0-100), cleanliness_summary (str),
                        keywords (list[str]), confidence (float 0-1)
    """
    client = _get_client()
    if not client:
        return {"sentiment_score": None, "cleanliness_summary": None, "keywords": [], "confidence": 0.0}

    if not reviews:
        return {"sentiment_score": None, "cleanliness_summary": "レビューがありません", "keywords": [], "confidence": 0.0}

    # Prepare review text for analysis
    review_texts = []
    for r in reviews[:10]:  # Use up to 10 reviews
        text = r.get("text", "")[:200]  # Truncate each to 200 chars
        if text.strip():
            rating = r.get("rating", "?")
            review_texts.append(f"[{rating}★] {text}")

    if not review_texts:
        return {"sentiment_score": None, "cleanliness_summary": None, "keywords": [], "confidence": 0.0}

    prompt = f"""You are a toilet cleanliness analyst. Analyze these Google Maps reviews for "{toilet_name}" and return JSON.

Reviews:
{chr(10).join(review_texts[:5])}

Return JSON with:
- sentiment_score: integer 0-100 (cleanliness-focused, not general sentiment)
- cleanliness_summary: one short sentence in Japanese describing cleanliness
- keywords: array of 3-5 Japanese keywords describing the toilet
- confidence: float 0.0-1.0 based on number and quality of reviews"""

    try:
        response = client.models.generate_content(
            model=_GEMINI_MODEL,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
            },
        )
        result = json.loads(response.text)
        return {
            "sentiment_score": result.get("sentiment_score"),
            "cleanliness_summary": result.get("cleanliness_summary"),
            "keywords": result.get("keywords", []),
            "confidence": result.get("confidence", 0.0),
        }
    except Exception as e:
        logger.warning("Gemini analysis failed for %s: %s", toilet_name, e)
        return {"sentiment_score": None, "cleanliness_summary": None, "keywords": [], "confidence": 0.0}
