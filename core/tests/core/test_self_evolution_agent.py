import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.self_evolution.self_evolution_agent import SelfEvolutionAgent


@pytest.fixture
def mock_fitness_engine():
    engine = MagicMock()
    engine.metrics = {
        "Skill_A": {
            "success_count": 10,
            "failure_count": 5,
            "total_latency": 15.0,
            "token_cost": 0.0,
            "reuse_count": 15,
        }
    }
    engine.calculate_fitness.return_value = 0.25
    return engine


@pytest.fixture
def mock_auto_skill_creator():
    creator = MagicMock()
    creator.generate_and_deploy_skill = AsyncMock(
        return_value={"success": True, "skill_name": "Skill_A_v2"}
    )
    return creator


@pytest.fixture
def agent(mock_fitness_engine, mock_auto_skill_creator):
    return SelfEvolutionAgent(
        fitness_engine=mock_fitness_engine,
        auto_skill_creator=mock_auto_skill_creator,
        interval_seconds=60,
        min_runs_before_action=5,
        max_consecutive_penalties=3,
        refactor_penalty_threshold=0.3,
        fitness_threshold=0.5,
    )


@pytest.mark.anyio
async def test_evaluate_skill_prunes_below_threshold(agent, mock_fitness_engine):
    await agent._evaluate_skill("Skill_A")
    mock_fitness_engine.evaluate_and_prune.assert_called_once_with("Skill_A", 0.5, 5)


@pytest.mark.anyio
async def test_evaluate_skill_triggers_refactor_on_consecutive_penalties(
    agent, mock_fitness_engine, mock_auto_skill_creator
):
    agent._consecutive_penalties["Skill_A"] = 3
    await agent._evaluate_skill("Skill_A")
    mock_auto_skill_creator.generate_and_deploy_skill.assert_called_once()
    # Issue #1686 (CRITICAL infinite-loop fix): reset-to-0 was REMOVED on
    # purpose — post-refactor the counter now DECAYS by 1, never hard-resets.
    # Trace: 3 (pre-set) → +1 (score < refactor_penalty_threshold) → 4 ≥
    # max_consecutive_penalties → refactor triggered → decay → 3.
    # The real loop guard is the lineage refactor-budget freeze in
    # _maybe_trigger_refactor (max_refactors_per_skill → _frozen_skills).
    assert agent._consecutive_penalties["Skill_A"] == 3


@pytest.mark.anyio
async def test_evaluate_skill_skips_below_min_runs(agent, mock_fitness_engine):
    mock_fitness_engine.metrics = {
        "Skill_S": {
            "success_count": 2,
            "failure_count": 0,
            "total_latency": 2.0,
            "token_cost": 0.0,
            "reuse_count": 2,
        }
    }
    mock_fitness_engine.calculate_fitness.return_value = 0.3
    await agent._evaluate_skill("Skill_S")
    mock_fitness_engine.evaluate_and_prune.assert_not_called()


@pytest.mark.anyio
async def test_register_missing_path_triggers_generation(agent, mock_auto_skill_creator):
    agent._has_high_fitness_path = MagicMock(return_value=False)
    agent._register_missing_path("some demand", "NewSkill")
    await asyncio.sleep(0)
    await agent._process_demand({"task_demand": "some demand", "skill_name": "NewSkill"})
    mock_auto_skill_creator.generate_and_deploy_skill.assert_called_once_with(
        "some demand", "NewSkill"
    )


@pytest.mark.anyio
async def test_register_missing_path_skips_existing_skill(agent, mock_auto_skill_creator):
    agent._has_high_fitness_path = MagicMock(return_value=True)
    agent._register_missing_path("some demand", "NewSkill")
    await agent._process_demand({"task_demand": "some demand", "skill_name": "NewSkill"})
    mock_auto_skill_creator.generate_and_deploy_skill.assert_not_called()


@pytest.mark.anyio
async def test_start_stop_lifecycle(agent):
    await agent.start()
    assert agent._running is True
    assert agent._task is not None
    await agent.stop()
    assert agent._running is False
    assert agent._task is None


@pytest.mark.anyio
async def test_refactor_prompt_contains_source_code(agent, mock_auto_skill_creator, tmp_path):
    skill_dir = tmp_path / "skills" / "dynamic" / "Skill_A"
    skill_dir.mkdir(parents=True)
    (skill_dir / "main.py").write_text("class Skill_A:\n    pass\n")
    base = tmp_path
    with patch("core.self_evolution.self_evolution_agent.Path") as mock_path_cls:
        instance = MagicMock()
        instance.resolve.return_value = MagicMock()
        instance.resolve.return_value.parent.parent.parent = base
        mock_path_cls.return_value = instance
        result = agent._read_skill_code("Skill_A")
        assert "class Skill_A" in result


@pytest.mark.anyio
async def test_has_high_fitness_path_from_registry(agent, mock_fitness_engine):
    mock_fitness_engine.metrics = {}
    mock_fitness_engine.registry.get_skill.return_value = {"name": "Skill_B"}
    assert agent._has_high_fitness_path("Skill_B") is True
    mock_fitness_engine.registry.get_skill.assert_called_once_with("Skill_B")
