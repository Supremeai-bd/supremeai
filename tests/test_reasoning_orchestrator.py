import pytest
from unittest.mock import patch, MagicMock
from brain.reasoning_orchestrator import ReasoningOrchestrator

def test_reasoning_orchestrator_plan():
    orchestrator = ReasoningOrchestrator(
        long_term_memory=MagicMock(),
        cot_reasoner=MagicMock(),
        episodic_memory=MagicMock()
    )
    
    # Simple check
    res_simple = orchestrator.plan("Hi there")
    assert res_simple["mode"] == "direct"
    
    # CoT check
    res_cot = orchestrator.plan("prove that X is correct")
    assert res_cot["mode"] == "cot"
    
    # Advanced reasoning check
    res_adv = orchestrator.plan("solve using monte carlo tree search")
    assert res_adv["mode"] == "tot_mcts"
    
    # Default check
    res_def = orchestrator.plan("generate a report on sales")
    assert res_def["mode"] == "standard"

def test_reasoning_orchestrator_route():
    mock_ltm = MagicMock()
    mock_ltm.build_context.return_value = "ltm context"
    
    mock_episodic = MagicMock()
    mock_episodic.summarize_recent.return_value = "recent context"
    
    mock_cot = MagicMock()
    mock_cot.tree_search.return_value = {"trace": "cot trace"}
    mock_cot.monte_carlo_search.return_value = {"trace": "mcts trace"}
    mock_cot.build_prompt.return_value = "enriched prompt with cot"
    
    orchestrator = ReasoningOrchestrator(
        long_term_memory=mock_ltm,
        cot_reasoner=mock_cot,
        episodic_memory=mock_episodic
    )
    
    res = orchestrator.route("solve math problem using monte carlo")
    assert res["use_cot"] is True
    assert "cot trace" in res["reasoning_trace"]["trace"]
    assert "mcts trace" in res["reasoning_trace"]["mcts"]["trace"]
    assert res["prompt"] == "enriched prompt with cot"
