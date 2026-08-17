# tests/test_core_feedback.py
"""Tests for feedback loop and learning system."""

import pytest
from unittest.mock import MagicMock, patch


class TestFeedbackLoop:
    """Test feedback loop functionality."""

    def test_feedback_loop_initialization(self):
        """Test that FeedbackLoop initializes correctly."""
        from backend.core.feedback_loop import FeedbackLoop

        loop = FeedbackLoop()
        assert loop is not None

    def test_record_edit(self):
        """Test recording user edits."""
        from backend.core.feedback_loop import FeedbackLoop

        loop = FeedbackLoop()
        result = loop.record_edit(
            file_path="test.py",
            diff_summary="Changed function signature"
        )

        assert isinstance(result, dict)

    def test_record_suggestion_feedback_accepted(self):
        """Test recording accepted suggestion feedback."""
        from backend.core.feedback_loop import FeedbackLoop

        loop = FeedbackLoop()
        result = loop.record_suggestion_feedback(
            accepted=True,
            context={"task": "code_generation"}
        )

        assert isinstance(result, dict)

    def test_record_suggestion_feedback_rejected(self):
        """Test recording rejected suggestion feedback."""
        from backend.core.feedback_loop import FeedbackLoop

        loop = FeedbackLoop()
        result = loop.record_suggestion_feedback(
            accepted=False,
            context={"task": "code_generation"}
        )

        assert isinstance(result, dict)

    def test_record_error_report(self):
        """Test recording error reports."""
        from backend.core.feedback_loop import FeedbackLoop

        loop = FeedbackLoop()
        result = loop.record_error_report(
            error=Exception("Test error"),
            context={"operation": "test"}
        )

        assert isinstance(result, dict)

    def test_get_metrics(self):
        """Test getting feedback metrics."""
        from backend.core.feedback_loop import FeedbackLoop

        loop = FeedbackLoop()
        metrics = loop.metrics()

        assert isinstance(metrics, dict)

    def test_events_filtering(self):
        """Test getting filtered events."""
        from backend.core.feedback_loop import FeedbackLoop

        loop = FeedbackLoop()

        # Get all events
        all_events = loop.events()
        assert isinstance(all_events, list)

        # Get filtered events
        edit_events = loop.events(event_type="edit")
        assert isinstance(edit_events, list)


class TestCallbackQueryHandler:
    """Test callback query handling."""

    @pytest.mark.asyncio
    async def test_handle_feedback(self):
        """Test feedback handling endpoint."""
        from backend.core.feedback_loop import FeedbackLoop

        loop = FeedbackLoop()
        result = loop.handle_feedback({
            "type": "rating",
            "value": 5,
            "comment": "Great work!"
        })

        assert isinstance(result, dict)
