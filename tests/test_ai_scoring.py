"""
tests/test_ai_scoring.py
Tests for Gemini AI scoring module.
Related: batch/ai_scoring.py
"""
from batch.ai_scoring import analyze_reviews, is_available


class TestAiScoring:
    def test_is_available_returns_false_without_key(self, monkeypatch):
        monkeypatch.setattr("batch.ai_scoring._GEMINI_API_KEY", "")
        assert is_available() is False

    def test_analyze_reviews_returns_fallback_without_key(self, monkeypatch):
        monkeypatch.setattr("batch.ai_scoring._GEMINI_API_KEY", "")
        result = analyze_reviews([{"text": "clean", "rating": 5}], "Test Toilet")
        assert result["sentiment_score"] is None
        assert result["confidence"] == 0.0

    def test_analyze_reviews_returns_fallback_with_empty_list(self, monkeypatch):
        monkeypatch.setattr("batch.ai_scoring._GEMINI_API_KEY", "test-key")
        result = analyze_reviews([], "Test Toilet")
        assert result["sentiment_score"] is None
        assert result["cleanliness_summary"] == "レビューがありません"

    def test_analyze_reviews_handles_no_text_reviews(self, monkeypatch):
        monkeypatch.setattr("batch.ai_scoring._GEMINI_API_KEY", "test-key")
        result = analyze_reviews([{"text": "", "rating": 5}], "Test Toilet")
        assert result["sentiment_score"] is None
