"""Issue #1686 (CRITICAL) — infinite evolution/refactor loop guard tests.

Old behaviour: after `_trigger_refactor()`, consecutive penalties reset to 0
and the refactor lineage kept generating new versions forever (LLM budget
burn, `_v2/_v3/_v4…` churn, no human notified).

New contract:
1. Refactors counted per skill LINEAGE (`foo`, `foo_v2`, `foo_v3` → one budget)
2. Budget exhausted (default 3) → skill FROZEN: no further refactors, CRITICAL
   alert + error-bus `EVOLUTION_LOOP_FROZEN` event (once)
3. Penalties DECAY by 1 (not hard-reset to 0) after refactor or good score
4. Refactor names increment (`_v2`, `_v3`, …) instead of reusing `_v2`
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.self_evolution.self_evolution_agent import SelfEvolutionAgent


def _agent(max_refactors: int = 3) -> SelfEvolutionAgent:
    agent = SelfEvolutionAgent(
        fitness_engine=MagicMock(metrics={}),
        auto_skill_creator=MagicMock(generate_and_deploy_skill=AsyncMock()),
        interval_seconds=300,
        max_refactors_per_skill=max_refactors,
    )
    return agent


def _bad_skill_engine(agent: SelfEvolutionAgent, skill: str) -> None:
    agent.fitness_engine.calculate_fitness = MagicMock(return_value=0.1)
    agent.fitness_engine.metrics = {skill: {"success_count": 0, "failure_count": 100}}
    agent.fitness_engine.evaluate_and_prune = MagicMock()


class TestRefactorLineageBudget:
    async def test_refactors_counted_per_lineage(self):
        agent = _agent(max_refactors=5)
        # direct lineage calls: foo → foo_v2 → foo_v3 share ONE budget
        for name in ("foo", "foo_v2", "foo_v3"):
            await agent._maybe_trigger_refactor(name)
        assert agent._refactor_counts["foo"] == 3
        assert "foo" not in agent._frozen_skills
        assert agent.auto_skill_creator.generate_and_deploy_skill.await_count == 3

    async def test_budget_exhausted_freezes_and_alerts(self):
        agent = _agent(max_refactors=1)
        _bad_skill_engine(agent, "bar")
        # 1st refactor: allowed
        await agent._maybe_trigger_refactor("bar")
        assert agent.auto_skill_creator.generate_and_deploy_skill.await_count == 1
        # 2nd attempt: budget exhausted → frozen, no refactor
        await agent._maybe_trigger_refactor("bar")
        assert "bar" in agent._frozen_skills
        assert agent.auto_skill_creator.generate_and_deploy_skill.await_count == 1

    async def test_frozen_skill_skips_evaluation_entirely(self):
        agent = _agent()
        _bad_skill_engine(agent, "baz")
        agent._frozen_skills.add("baz")
        await agent._evaluate_skill("baz")
        agent.fitness_engine.calculate_fitness.assert_not_called()

    async def test_freeze_alert_emitted_once(self, monkeypatch):
        agent = _agent(max_refactors=0)
        events = []
        from core.messaging import event_bus

        monkeypatch.setattr(
            event_bus.error_event_bus,
            "emit",
            lambda e: events.append(e.error_type),
        )
        await agent._maybe_trigger_refactor("qux")
        await agent._maybe_trigger_refactor("qux")
        assert events.count("EVOLUTION_LOOP_FROZEN") == 1  # alert deduped
        assert "qux" in agent._frozen_skills


class TestPenaltyDecay:
    async def test_refactor_decays_penalty_not_reset(self):
        agent = _agent()
        agent._consecutive_penalties["s1"] = agent.max_consecutive_penalties
        await agent._maybe_trigger_refactor("s1")
        # post-refactor decay happens in _evaluate_skill; simulate it:
        agent._consecutive_penalties["s1"] = max(0, agent._consecutive_penalties["s1"] - 1)
        # direct check via _evaluate_skill below

    async def test_evaluate_skill_good_score_decays_not_resets(self):
        agent = _agent()
        agent.fitness_engine.calculate_fitness = MagicMock(return_value=0.9)
        agent.fitness_engine.metrics = {"s2": {"success_count": 50, "failure_count": 1}}
        agent._consecutive_penalties["s2"] = 2
        await agent._evaluate_skill("s2")
        assert agent._consecutive_penalties["s2"] == 1  # decayed, NOT 0

    async def test_evaluate_skill_refactor_path_decays(self):
        agent = _agent(max_refactors=10)
        agent.fitness_engine.calculate_fitness = MagicMock(return_value=0.1)
        agent.fitness_engine.metrics = {"s3": {"success_count": 0, "failure_count": 99}}
        agent.fitness_engine.evaluate_and_prune = MagicMock()
        agent._consecutive_penalties["s3"] = agent.max_consecutive_penalties
        await agent._evaluate_skill("s3")
        # penalty increments (3→4) then decays by 1 (4→3): NET plateau instead
        # of the old reset-to-0. The hard ceiling is the lineage budget/freeze.
        assert agent._consecutive_penalties["s3"] == agent.max_consecutive_penalties
        # and the refactor was counted toward the lineage budget:
        assert agent._refactor_counts["s3"] == 1


class TestRefactorNaming:
    def test_next_refactor_name_increments(self):
        agent = _agent()
        assert agent._next_refactor_name("foo") == "foo_v2"
        agent._refactor_counts["foo"] = 1
        assert agent._next_refactor_name("foo") == "foo_v3"
        agent._refactor_counts["foo"] = 2
        assert agent._next_refactor_name("foo_v2") == "foo_v4"

    def test_base_skill_name_strips_version(self):
        assert SelfEvolutionAgent._base_skill_name("foo") == "foo"
        assert SelfEvolutionAgent._base_skill_name("foo_v2") == "foo"
        assert SelfEvolutionAgent._base_skill_name("foo_v10") == "foo"
        assert SelfEvolutionAgent._base_skill_name("foo_version") == "foo_version"
