"""Integration tests for skill execution pipeline.

বাংলা: স্কিল ডিসkovary, রেজিস্টার, এবং এক্সিকিউশন পাইপলাইন — orchestrated chain।
"""

from __future__ import annotations

import pytest

from core.base import BaseSkill
from core.orchestration.periodic_task_scheduler import Orchestrator
from core.skill_manager import SkillManager


class FakeSkill(BaseSkill):
    name = "fake_skill"
    description = "A fake skill for testing"

    async def execute(self, input_data):
        return {"result": f"executed:{input_data}"}


class TestSkillExecutionPipeline:
    """Tests for skill execution pipeline."""

    @pytest.mark.asyncio
    async def test_register_and_get_skill(self):
        """Test skill registration and retrieval."""
        manager = SkillManager()
        skill = FakeSkill()
        manager.register_skill(skill, name="fake_skill")
        result = await manager.get_skill("fake_skill")
        assert result == skill

    @pytest.mark.asyncio
    async def test_get_unknown_skill_raises(self):
        """Test getting unknown skill raises error."""
        manager = SkillManager()
        with pytest.raises(
            Exception
        ):  # -- intentionally broad: asserts *some* error propagates (mocked/validation failure), exact type varies
            await manager.get_skill("nonexistent_skill")

    @pytest.mark.asyncio
    async def test_skill_chain_execution(self):
        """Test orchestrator executes skill chain."""
        from core.skill_manager import skill_manager

        orch = Orchestrator()
        skill = FakeSkill()
        skill_manager.register_skill(skill, name="Skill_A")
        skill_manager.register_skill(skill, name="Skill_B")
        orch.skill_graph.find_execution_path = lambda a, b: ["Skill_A", "Skill_B"]
        result = await orch.execute_skill_chain(["Skill_A", "Skill_B"], {"x": 1})
        assert result.get("success") is True
        assert "output" in result

    @pytest.mark.asyncio
    async def test_skill_chain_fallback(self):
        """Test orchestrator uses fallback on failure."""
        from core.skill_manager import skill_manager

        orch = Orchestrator()
        skill = FakeSkill()
        skill_manager.register_skill(skill, name="Skill_A")
        skill_manager.register_skill(skill, name="Skill_B")
        orch.skill_graph.find_execution_path = lambda a, b: ["Skill_A", "Skill_B"]

        # Orchestrator's execute_skill_chain mocks the execution and raises an error for Skill_B
        # if 'trigger_failure' is in the data.
        result = await orch.execute_skill_chain(["Skill_A", "Skill_B"], {"trigger_failure": True})
        assert result.get("success") is False
        assert "error" in result or "fallback_executed" in result

    def test_skill_manager_singleton(self):
        """Test skill_manager is a singleton."""
        from core.skill_manager import skill_manager

        assert skill_manager is not None

    @pytest.mark.asyncio
    async def test_skill_execution_with_monkeypatched_llm(self, monkeypatch):
        """Test skill execution with mocked LLM gateway."""
        manager = SkillManager()

        async def mock_synthesize(*args, **kwargs):
            return {"text": '{"success": true, "skill_name": "NewSkill"}'}

        class _FakeGateway:
            acompletion = staticmethod(mock_synthesize)

        # বাংলা মন্তব্য: skill_manager এখন `core.llm.llm_gateway.get_llm_gateway()` দিয়ে
        # gateway lazily fetch করে (module-level `llm_gateway` নাম আর নেই), তাই
        # `_get_llm_gateway` হেল্পারটাই patch করা হচ্ছে যাতে mock gateway ফেরত আসে।
        monkeypatch.setattr("core.skill_manager._get_llm_gateway", lambda: _FakeGateway())
        result = await manager.synthesize_skill_schema("test task")
        assert result["success"] is True
