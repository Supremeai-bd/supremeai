from unittest.mock import MagicMock, patch
from brain.reasoning_orchestrator import ReasoningOrchestrator


def _make_orchestrator():
    orchestrator = ReasoningOrchestrator.__new__(ReasoningOrchestrator)
    orchestrator.long_term_memory = MagicMock()
    orchestrator.cot_reasoner = MagicMock()
    orchestrator.episodic_memory = MagicMock()
    return orchestrator


def test_plan_simple_task():
    o = _make_orchestrator()
    plan = o.plan('hello there')
    assert plan['mode'] == 'direct'
    assert plan['complexity'] == 'simple'


def test_plan_advanced_reasoning():
    o = _make_orchestrator()
    plan = o.plan('optimize multi-step strategy with tradeoffs')
    assert plan['mode'] == 'tot_mcts'


def test_plan_reasoning():
    o = _make_orchestrator()
    plan = o.plan('prove this math logic')
    assert plan['mode'] == 'cot'


def test_build_enriched_prompt_calls_cot():
    o = _make_orchestrator()
    o.cot_reasoner.build_prompt.return_value = 'COT: hello'
    prompt = o.build_enriched_prompt('solve this')
    assert prompt == 'COT: hello'


def test_route_returns_prompt_and_trace():
    o = _make_orchestrator()
    o.cot_reasoner.tree_search.return_value = {'path': 'x'}
    result = o.route('complex planning task')
    assert 'prompt' in result
    assert result['use_cot'] is True
    assert 'reasoning_trace' in result
