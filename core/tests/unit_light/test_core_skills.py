"""Tests for core.skills.core_skills — skill name properties and (mocked) execution."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.skills import core_skills
from core.skills.base import BaseSkill
from core.skills.core_skills import (
    CodeGenerationSkill,
    ExperiencePersistenceSkill,
    ResearchSkill,
    StaticAnalysisSkill,
    SystemDesignSkill,
    ToolExecutionSkill,
    ToolSynthesisSkill,
)

SKILLS = [
    SystemDesignSkill,
    CodeGenerationSkill,
    StaticAnalysisSkill,
    ResearchSkill,
    ToolSynthesisSkill,
    ToolExecutionSkill,
]

EXPECTED_NAMES = {
    SystemDesignSkill: "SystemDesignSkill",
    CodeGenerationSkill: "CodeGenerationSkill",
    StaticAnalysisSkill: "StaticAnalysisSkill",
    ResearchSkill: "ResearchSkill",
    ToolSynthesisSkill: "ToolSynthesisSkill",
    ToolExecutionSkill: "ToolExecutionSkill",
    ExperiencePersistenceSkill: "ExperiencePersistenceSkill",
}


@pytest.mark.parametrize("skill_cls", SKILLS + [ExperiencePersistenceSkill])
def test_skill_name_property(skill_cls):
    assert skill_cls().name == EXPECTED_NAMES[skill_cls]


def _make_workspace():
    ws = MagicMock()
    ws.original_prompt = "build a thing"
    ws.log = MagicMock()
    return ws


@pytest.mark.asyncio
@pytest.mark.parametrize("skill_cls", SKILLS)
async def test_skill_execute_calls_gateway(skill_cls):
    fake_gateway = MagicMock()
    fake_gateway.acompletion = AsyncMock(
        return_value={"choices": [{"message": {"content": "RESULT"}}]}
    )
    ws = _make_workspace()
    with patch.object(core_skills, "llm_gateway", fake_gateway):
        result = await skill_cls().execute(ws, "user-1")
    assert result == "RESULT"
    fake_gateway.acompletion.assert_awaited_once()
    ws.log.assert_called()


@pytest.mark.asyncio
async def test_experience_persistence_skill_pure():
    ws = _make_workspace()
    result = await ExperiencePersistenceSkill().execute(ws, "user-1", summary="did a task")
    assert result == "Saved experience: did a task"


def test_base_skill_name_defaults_to_class_name():
    class MySkill(BaseSkill):
        pass

    assert MySkill().name == "MySkill"


def test_base_skill_run_not_implemented():
    class MySkill(BaseSkill):
        pass

    with pytest.raises(NotImplementedError):
        MySkill().run()
