# tests/test_agents_skill_librarian.py
"""Tests for SkillLibrarian - skill quarantine and approval management."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path


class TestSkillLibrarian:
    """Test SkillLibrarian approval and quarantine management."""

    @pytest.fixture
    def temp_skills_dir(self, tmp_path):
        """Create a temporary skills directory."""
        skills_dir = tmp_path / "skills" / "quarantine"
        skills_dir.mkdir(parents=True)
        return str(skills_dir)

    def test_librarian_initialization(self):
        """Test SkillLibrarian initializes correctly."""
        from backend.agents.skill_librarian import SkillLibrarian

        librarian = SkillLibrarian()
        assert librarian is not None

    def test_list_quarantine_queue(self):
        """Test listing quarantine queue."""
        from backend.agents.skill_librarian import SkillLibrarian

        librarian = SkillLibrarian()
        result = librarian.list_quarantine_queue()

        assert isinstance(result, list)

    def test_process_approval_approve(self):
        """Test processing approval action."""
        from backend.agents.skill_librarian import SkillLibrarian

        librarian = SkillLibrarian()

        # Mock the processing
        result = librarian.process_approval(
            skill_id="test-skill-123",
            action="approve",
            ai_patch_code=None
        )

        assert isinstance(result, dict)

    def test_process_approval_reject(self):
        """Test processing rejection action."""
        from backend.agents.skill_librarian import SkillLibrarian

        librarian = SkillLibrarian()

        result = librarian.process_approval(
            skill_id="test-skill-456",
            action="reject"
        )

        assert isinstance(result, dict)

    def test_process_approval_with_patch(self):
        """Test processing approval with AI patch."""
        from backend.agents.skill_librarian import SkillLibrarian

        librarian = SkillLibrarian()

        patch_code = """
# Fixed code
def secure_function():
    return "safe"
"""

        result = librarian.process_approval(
            skill_id="test-skill-789",
            action="approve_with_patch",
            ai_patch_code=patch_code
        )

        assert isinstance(result, dict)


class TestSkillGarbageCollector:
    """Test skill garbage collection and cleanup."""

    @pytest.fixture
    def temp_skills_dir(self, tmp_path):
        """Create a temporary skills directory."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        return str(skills_dir)

    def test_gc_initialization(self):
        """Test GC initializes correctly."""
        from backend.agents.skill_gc import SkillGarbageCollector

        gc = SkillGarbageCollector()
        assert gc is not None

    def test_run_daily_cleanup(self):
        """Test running daily cleanup."""
        from backend.agents.skill_gc import SkillGarbageCollector

        gc = SkillGarbageCollector()

        removed = gc.run_daily_cleanup(
            usage_threshold=5,
            days_threshold=30
        )

        assert isinstance(removed, list)


class TestMorphicAdapter:
    """Test MorphicAdapter for code contract adaptation."""

    def test_morphic_adapter_initialization(self):
        """Test MorphicAdapter initializes."""
        from backend.agents.morphic_adapter import MorphicAdapter

        adapter = MorphicAdapter()
        assert adapter is not None

    def test_get_system_prompt(self):
        """Test getting system prompt for morphic."""
        from backend.agents.morphic_adapter import MorphicAdapter

        adapter = MorphicAdapter()
        prompt = adapter._get_morphic_system_prompt()

        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_adapt_code_to_contract(self):
        """Test code adaptation to contract."""
        from backend.agents.morphic_adapter import MorphicAdapter

        adapter = MorphicAdapter()

        raw_code = "def my_func(x): return x * 2"

        result = adapter.adapt_code_to_contract(
            raw_code=raw_code,
            skill_description="A function that doubles input"
        )

        assert isinstance(result, dict)
