# SupremeAI 2.0 — Unified Evolution Core Regression Suite
# বাংলা মন্তব্য: কনসোলিডেটেড backend/core/evolution/ প্যাকেজের জন্য রিগ্রেশন টেস্ট।
# এজেন্ট ব্রিডিং, ফিটনেস স্কোরিং, স্কিল গ্রাফ ফলব্যাক, রিঅ্যাক্ট স্কিল
# জেনারেশন এবং ডেইলি লার্নার ডিসকভারি-স্কোরিং কভার করে।

import sys
from unittest.mock import MagicMock

# Import guard: evolution modules may transitively import optional google.genai.
sys.modules.setdefault("google", MagicMock())
sys.modules.setdefault("google.genai", MagicMock())

from core.self_evolution.agent_breeder import AgentBreeder  # noqa: E402
from core.self_evolution.daily_learner import DailyLearner, PriorityScorer  # noqa: E402
from core.self_evolution.evolution_react_agent import EvolutionReActAgent  # noqa: E402
from core.self_evolution.fitness_engine import AutomatedFitnessEngine, FitnessEngine  # noqa: E402
from core.self_evolution.skill_graph import EvolutionSkillGraph  # noqa: E402


def test_evolution_core_modules_importable():
    """Consolidation integrity: every unified evolution module must import cleanly."""
    assert DailyLearner is not None
    assert FitnessEngine is not None
    assert EvolutionReActAgent is not None
    assert EvolutionSkillGraph is not None
    assert AgentBreeder is not None
    assert PriorityScorer is not None
    assert AutomatedFitnessEngine is not None


def test_evolution_classes_construct_with_safe_defaults():
    """Unified evolution classes must construct without mandatory external deps."""
    assert isinstance(DailyLearner(), DailyLearner)
    assert isinstance(FitnessEngine(), FitnessEngine)
    assert isinstance(EvolutionReActAgent(), EvolutionReActAgent)


def test_self_evolution_agent_constructs():
    from core.self_evolution.self_evolution_agent import SelfEvolutionAgent

    agent = SelfEvolutionAgent()
    assert hasattr(agent, "fitness_threshold")


def test_priority_scorer_score_discovery_deterministic():
    score = PriorityScorer.score_discovery({"novelty": 0.5, "impact": 0.5})
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0
    # Same input => same score (deterministic)
    assert PriorityScorer.score_discovery({"novelty": 0.5, "impact": 0.5}) == score


def test_priority_scorer_score_discovery_scales_with_signals():
    low = PriorityScorer.score_discovery({"type": "library"})
    high = PriorityScorer.score_discovery({"type": "protocol", "source": "arxiv"})
    assert high > low


def test_automated_fitness_engine_score():
    score = AutomatedFitnessEngine().calculate_fitness_score(10, 0, 100.0)
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0
    # All-success should outscore all-failure (same latency)
    success = AutomatedFitnessEngine().calculate_fitness_score(10, 0, 100.0)
    failure = AutomatedFitnessEngine().calculate_fitness_score(0, 10, 100.0)
    assert success > failure


def test_evolution_skill_graph_fallback_unknown():
    graph = EvolutionSkillGraph()
    assert graph.get_fallback("does_not_exist") is None


def test_evolution_react_agent_generate_skill_shape():
    agent = EvolutionReActAgent()
    result = agent.generate_skill("test_skill", "perform a safe operation")
    assert isinstance(result, dict)
    assert "skill_name" in result or "name" in result or "code" in result


def test_agent_breeder_constructs_with_mock_session():
    breeder = AgentBreeder(db_session=MagicMock())
    assert isinstance(breeder, AgentBreeder)
    assert breeder._db is not None


def test_self_evolution_agent_thresholds_configurable():
    from core.self_evolution.self_evolution_agent import SelfEvolutionAgent

    agent = SelfEvolutionAgent(fitness_threshold=0.7, max_consecutive_penalties=2)
    assert agent.fitness_threshold == 0.7
    assert agent.max_consecutive_penalties == 2
