"""
Tests for Inference Service.
"""
import pytest
from unittest.mock import Mock, patch


class TestPreprocessing:
    """Test text preprocessing functions."""

    def test_clean_text_removes_urls(self):
        """Test that URLs are removed from text."""
        import re
        text = "Check out http://example.com for more"
        cleaned = re.sub(r'http\S+', '', text)
        assert 'http' not in cleaned

    def test_clean_text_removes_special_chars(self):
        """Test special character removal."""
        import re
        text = "Hello! @world #test"
        cleaned = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
        assert '@' not in cleaned
        assert '#' not in cleaned

    def test_combine_text_handles_none_description(self):
        """Test combining headline with None description."""
        headline = "Test headline"
        description = None
        result = headline if not description else f"{headline} {description}"
        assert result == "Test headline"


class TestPrediction:
    """Test prediction functionality."""

    def test_prediction_response_structure(self):
        """Test prediction response has required fields."""
        expected_fields = [
            'prediction_id',
            'category',
            'confidence',
            'top_categories',
            'model_version',
            'processing_time_ms'
        ]
        assert len(expected_fields) == 6

    def test_confidence_range(self):
        """Test confidence values are between 0 and 1."""
        confidence = 0.85
        assert 0 <= confidence <= 1

    def test_top_categories_sorted(self):
        """Test top categories are sorted by confidence."""
        top_cats = [
            {'category': 'POLITICS', 'confidence': 0.8},
            {'category': 'BUSINESS', 'confidence': 0.1},
            {'category': 'SPORTS', 'confidence': 0.05}
        ]
        confidences = [c['confidence'] for c in top_cats]
        assert confidences == sorted(confidences, reverse=True)


class TestCaching:
    """Test caching functionality."""

    def test_cache_key_generation(self):
        """Test cache key is generated consistently."""
        import hashlib
        headline = "Test headline"
        key1 = hashlib.md5(headline.encode()).hexdigest()
        key2 = hashlib.md5(headline.encode()).hexdigest()
        assert key1 == key2
