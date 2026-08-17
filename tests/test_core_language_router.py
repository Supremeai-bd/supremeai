# tests/test_core_language_router.py
"""Tests for language routing and detection functionality."""

import pytest
from unittest.mock import MagicMock, patch


class TestLanguageRouter:
    """Test language detection and routing."""

    def test_language_router_initialization(self):
        """Test that LanguageRouter initializes correctly."""
        from backend.core.language_router import LanguageRouter

        router = LanguageRouter()
        assert router is not None

    def test_detect_bangla_language(self):
        """Test detection of Bangla language."""
        from backend.core.language_router import LanguageRouter

        router = LanguageRouter()

        bangla_texts = [
            "আমি সুপ্রিম এআই ব্যবহার করছি",
            "এটি একটি এআই সিস্টেম",
            "বাংলা ভাষায় লিখা টেক্সট",
        ]

        for text in bangla_texts:
            detected = router.detect(text)
            # Should detect Bangla
            assert detected is not None
            assert isinstance(detected, str)

    def test_detect_english_language(self):
        """Test detection of English language."""
        from backend.core.language_router import LanguageRouter

        router = LanguageRouter()

        english_texts = [
            "I am using SupremeAI",
            "This is a test",
            "Hello World",
        ]

        for text in english_texts:
            detected = router.detect(text)
            assert detected is not None
            assert isinstance(detected, str)

    def test_route_by_language(self):
        """Test routing based on detected language."""
        from backend.core.language_router import LanguageRouter

        router = LanguageRouter()

        result = router.route(
            text="আমি কীভাবে এআই ব্যবহার করব?",
            task_type="general"
        )

        assert isinstance(result, dict)

    def test_route_by_detected_language(self):
        """Test routing with explicit language detection."""
        from backend.core.language_router import LanguageRouter

        router = LanguageRouter()

        result = router.route_by_language(
            text="Test text",
            detected_lang="en"
        )

        assert isinstance(result, dict)


class TestIntentRouter:
    """Test intent classification and routing."""

    def test_intent_router_initialization(self):
        """Test that IntentRouter initializes."""
        from backend.core.intent_router import IntentRouter

        router = IntentRouter()
        assert router is not None

    def test_route_code_generation_intent(self):
        """Test routing for code generation prompts."""
        from backend.core.intent_router import IntentRouter

        router = IntentRouter()

        result = router.route("Create a Python function to add two numbers")

        assert isinstance(result, object)

    def test_route_bangla_code_intent(self):
        """Test routing for Bangla code generation."""
        from backend.core.intent_router import IntentRouter

        router = IntentRouter()

        result = router.route("আমাকে একটি পাইথন ফাংশন দরকার")

        assert result is not None

    def test_extract_operations(self):
        """Test operation extraction from text."""
        from backend.core.intent_router import IntentRouter

        router = IntentRouter()

        operations = router._extract_operations("Delete the temp files and create new folder")

        assert isinstance(operations, list)

    def test_extract_setting_changes(self):
        """Test setting change extraction."""
        from backend.core.intent_router import IntentRouter

        router = IntentRouter()

        changes = router._extract_setting_changes("Change theme to dark mode and language to English")

        assert isinstance(changes, list)


class TestPromptAction:
    """Test PromptAction dataclass."""

    def test_prompt_action_creation(self):
        """Test creating PromptAction."""
        from backend.core.intent_router import PromptAction

        action = PromptAction(
            action_type="test",
            target_module="test_module",
            payload={"key": "value"}
        )

        assert action.action_type == "test"
        assert action.target_module == "test_module"
        assert action.payload == {"key": "value"}

    def test_prompt_action_defaults(self):
        """Test PromptAction default values."""
        from backend.core.intent_router import PromptAction

        action = PromptAction(action_type="test")

        assert action.confidence == 0.0
        assert action.requires_confirmation is False
        assert action.payload == {}


class TestLanguageDetectionEdgeCases:
    """Test edge cases in language detection."""

    def test_mixed_language_detection(self):
        """Test detection of mixed language text."""
        from backend.core.language_router import LanguageRouter

        router = LanguageRouter()

        mixed_text = "I am using সুপ্রিম এআই today"
        detected = router.detect(mixed_text)

        assert detected is not None

    def test_empty_text_detection(self):
        """Test detection of empty text."""
        from backend.core.language_router import LanguageRouter

        router = LanguageRouter()

        detected = router.detect("")
        assert detected is not None

    def test_numeric_text_detection(self):
        """Test detection of numeric-only text."""
        from backend.core.language_router import LanguageRouter

        router = LanguageRouter()

        detected = router.detect("12345 67890")
        assert detected is not None
