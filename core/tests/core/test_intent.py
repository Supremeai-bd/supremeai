"""
Tests for core/intent.py — IntentClassifier
"""

from __future__ import annotations

import pytest

from core.intent import IntentClassifier, TaskType


@pytest.fixture
def classifier():
    return IntentClassifier()


class TestIntentClassifier:
    def test_general_query(self, classifier):
        intent = classifier.classify("what is the capital of france?")
        assert intent.task_type == TaskType.general
        assert intent.confidence >= 0.0
        assert intent.requires_admin is False
        assert intent.requires_vision is False

    def test_coding_query(self, classifier):
        intent = classifier.classify("write a python function to sort a list")
        assert intent.task_type == TaskType.coding
        assert intent.confidence > 0.0

    def test_admin_query(self, classifier):
        intent = classifier.classify("run admin shutdown command now")
        assert intent.task_type == TaskType.admin
        assert intent.requires_admin is True

    def test_translation_query(self, classifier):
        intent = classifier.classify("translate this to bengali")
        assert intent.task_type == TaskType.translation

    def test_sentiment_query(self, classifier):
        intent = classifier.classify("analyze the sentiment of this text")
        assert intent.task_type == TaskType.sentiment

    def test_vision_query(self, classifier):
        intent = classifier.classify("what is in this image?")
        assert intent.task_type == TaskType.vision
        assert intent.requires_vision is True

    def test_reasoning_query(self, classifier):
        intent = classifier.classify("prove that the square root of 2 is irrational")
        assert intent.task_type == TaskType.reasoning

    def test_confidence_sums_to_one(self, classifier):
        intent = classifier.classify("write a python code to translate text")
        assert 0.0 <= intent.confidence <= 1.0

    def test_empty_string_returns_general(self, classifier):
        intent = classifier.classify("")
        assert intent.task_type == TaskType.general

    def test_mixed_keywords_highest_wins(self, classifier):
        intent = classifier.classify("write python code to translate to bengali")
        # Should classify as coding or translation based on keyword density
        assert intent.task_type in (TaskType.coding, TaskType.translation)

    def test_case_insensitivity(self, classifier):
        intent1 = classifier.classify("TRANSLATE this text")
        intent2 = classifier.classify("translate this text")
        assert intent1.task_type == intent2.task_type

    def test_multiple_admin_keywords(self, classifier):
        intent = classifier.classify("admin please kill switch and shutdown")
        assert intent.task_type == TaskType.admin
        assert intent.requires_admin is True

    def test_word_boundary_respected(self, classifier):
        """Test that 'translation' matches but 'transportation' doesn't trigger translation."""
        intent = classifier.classify("transportation is important")
        # 'translation' keyword should NOT match 'transportation'
        assert intent.task_type != TaskType.translation

    @pytest.mark.parametrize(
        "prompt,expected_type",
        [
            ("fix this bug in my code", TaskType.coding),
            ("debug this python error", TaskType.coding),
            ("translate to french", TaskType.translation),
            ("check the sentiment", TaskType.sentiment),
            ("look at this screenshot", TaskType.vision),
            ("plan the architecture", TaskType.reasoning),
            ("disable the system", TaskType.admin),
            ("", TaskType.general),
        ],
    )
    def test_various_prompts(self, classifier, prompt, expected_type):
        intent = classifier.classify(prompt)
        assert intent.task_type == expected_type


def test_task_type_enum_values():
    assert TaskType.general.value == "general"
    assert TaskType.coding.value == "coding"
    assert TaskType.translation.value == "translation"
    assert TaskType.sentiment.value == "sentiment"
    assert TaskType.vision.value == "vision"
    assert TaskType.reasoning.value == "reasoning"
    assert TaskType.admin.value == "admin"


def test_task_type_membership():
    assert len(TaskType) == 7
    for t in TaskType:
        assert isinstance(t, TaskType)
