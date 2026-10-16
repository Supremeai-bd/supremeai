"""
Unit tests for Meta-Cognitive Intent Understanding, Capability Boundary & Delegation.
====================================================================================
Verifies:
1. Intent Parsing: Ambiguity detection & clarification question generation.
2. Capability Boundary: Local execution limits vs specialist needs.
3. Intelligent Delegation: Correct specialist routing (kaggle_gpu, reasoning_model, browser_subagent, human_admin, self).
4. MetaCognitionDatasetBuilder: Dataset compilation and JSONL export for Kaggle LoRA training.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock

import pytest

from backend.adaptive_engine.intent_parser import IntentParser
from backend.tools.learning.meta_cognition_dataset import MetaCognitionDatasetBuilder


@pytest.fixture
def mock_router():
    router = MagicMock()
    return router


def test_meta_cognition_destructive_gate_blocks_locally(mock_router):
    parser = IntentParser(model_router=mock_router)
    res = parser.parse_meta_cognition(
        "Drop database and delete production backups immediately"
    )

    assert res.can_solve_locally is False
    assert res.is_destructive_or_sensitive is True
    assert res.delegation_target == "human_admin"
    assert (
        "confirm" in (res.clarification_question or "").lower()
        or "authorize" in (res.clarification_question or "").lower()
    )
    # LLM should not even be called for hard destructive keywords
    mock_router.route_and_generate.assert_not_called()


def test_meta_cognition_heuristic_kaggle_delegation(mock_router):
    mock_router.route_and_generate.side_effect = RuntimeError("LLM offline")
    parser = IntentParser(model_router=mock_router)
    res = parser.parse_meta_cognition(
        "Fine-tune Llama 3 8B with LoRA on code refactoring dataset"
    )

    assert res.can_solve_locally is False
    assert res.delegation_target == "kaggle_gpu"
    assert "GPU" in res.why_delegated or "Kaggle" in res.why_delegated


def test_meta_cognition_heuristic_reasoning_delegation(mock_router):
    mock_router.route_and_generate.side_effect = RuntimeError("LLM offline")
    parser = IntentParser(model_router=mock_router)
    res = parser.parse_meta_cognition("Provide a mathematical proof of time complexity")

    assert res.can_solve_locally is False
    assert res.delegation_target == "reasoning_model"


def test_meta_cognition_heuristic_browser_delegation(mock_router):
    mock_router.route_and_generate.side_effect = RuntimeError("LLM offline")
    parser = IntentParser(model_router=mock_router)
    res = parser.parse_meta_cognition(
        "Open browser and click the login button to inspect console logs"
    )

    assert res.can_solve_locally is False
    assert res.delegation_target == "browser_subagent"


def test_meta_cognition_local_execution(mock_router):
    mock_router.route_and_generate.side_effect = RuntimeError("LLM offline")
    parser = IntentParser(model_router=mock_router)
    res = parser.parse_meta_cognition(
        "Add a type hint to parse_tokens function in parser.py"
    )

    assert res.can_solve_locally is True
    assert res.delegation_target == "self"
    assert res.is_ambiguous is False


def test_meta_cognition_llm_structured_parsing(mock_router):
    llm_payload = {
        "core_intent": "user_authentication",
        "underlying_goal": "Allow users to log in securely with JWT",
        "is_ambiguous": False,
        "clarification_question": None,
        "can_solve_locally": True,
        "confidence_score": 0.95,
        "boundary_limitations": [],
        "is_destructive_or_sensitive": False,
        "delegation_target": "self",
        "why_delegated": "Local FastAPI route implementation",
        "specialist_task_contract": {"endpoint": "/api/v1/login"},
        "synthesis_guidance": "Run test_auth.py to verify JWT generation",
    }
    mock_router.route_and_generate.return_value = {"text": json.dumps(llm_payload)}

    parser = IntentParser(model_router=mock_router)
    res = parser.parse_meta_cognition("Implement user login endpoint with JWT")

    assert res.core_intent == "user_authentication"
    assert res.can_solve_locally is True
    assert res.delegation_target == "self"
    assert res.confidence_score == 0.95


def test_dataset_builder_generation_and_export(tmp_path):
    builder = MetaCognitionDatasetBuilder(output_dir=str(tmp_path))
    jsonl_path = builder.generate_seed_dataset()

    assert os.path.exists(jsonl_path)
    with open(jsonl_path, encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]

    assert len(lines) >= 6
    # Check that instruction, input, and output exist in each training example
    for item in lines:
        assert "instruction" in item
        assert "input" in item
        assert "output" in item
        parsed_out = json.loads(item["output"])
        assert "core_intent" in parsed_out
        assert "can_solve_locally" in parsed_out
        assert "delegation_target" in parsed_out
