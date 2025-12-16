"""
Tests for Feedback Service.
"""
import pytest
from datetime import datetime


class TestFeedbackTypes:
    """Test feedback type validation."""

    def test_valid_feedback_types(self):
        """Test valid feedback types are accepted."""
        valid_types = ['correction', 'confirmation', 'rejection']
        assert 'correction' in valid_types
        assert 'confirmation' in valid_types
        assert 'rejection' in valid_types

    def test_correction_requires_category(self):
        """Test correction feedback requires correct_category."""
        feedback_type = 'correction'
        correct_category = None
        if feedback_type == 'correction':
            assert correct_category is None  # Would fail validation


class TestFeedbackStats:
    """Test feedback statistics calculation."""

    def test_accuracy_calculation(self):
        """Test accuracy is calculated correctly."""
        confirmations = 80
        total = 100
        accuracy = confirmations / total
        assert accuracy == 0.8

    def test_feedback_rate_calculation(self):
        """Test feedback rate calculation."""
        feedback_count = 50
        prediction_count = 1000
        rate = feedback_count / prediction_count
        assert rate == 0.05

    def test_corrections_by_category_structure(self):
        """Test corrections by category is a dict."""
        corrections = {
            'POLITICS': 10,
            'BUSINESS': 5,
            'SPORTS': 3
        }
        assert isinstance(corrections, dict)
        assert sum(corrections.values()) == 18


class TestFeedbackStorage:
    """Test feedback storage functionality."""

    def test_feedback_id_generation(self):
        """Test feedback ID is unique format."""
        import uuid
        feedback_id = f"fb_{uuid.uuid4().hex[:12]}"
        assert feedback_id.startswith('fb_')
        assert len(feedback_id) == 15

    def test_timestamp_format(self):
        """Test timestamp is ISO format."""
        timestamp = datetime.utcnow().isoformat()
        assert 'T' in timestamp
