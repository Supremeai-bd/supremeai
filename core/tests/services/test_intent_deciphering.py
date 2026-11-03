# backend/tests/services/test_intent_deciphering.py
from unittest.mock import MagicMock

import pytest

from services.intent_deciphering import IntentDecipheringService


@pytest.fixture
def mock_memory_service():
    mock = MagicMock()
    mock.retrieve_memories.return_value = [
        {
            "session_id": "s1",
            "summary": "Fixed memory leak in background worker",
            "task_type": "bugfix",
        },
        {
            "session_id": "s2",
            "summary": "Optimized Redis cache TTL and latency",
            "task_type": "perf",
        },
        {
            "session_id": "s3",
            "summary": "Hardened JWT authentication middleware",
            "task_type": "security",
        },
    ]
    return mock


@pytest.mark.asyncio
async def test_empty_request_returns_noop_intent():
    service = IntentDecipheringService()
    intent = await service.decipher_intent("")
    assert intent.ultimate_goal == "No-op / Idle"
    assert "system_stability" in intent.invariants
    assert "zero_resource_consumption" in intent.latent_constraints
    assert intent.suggested_methodology == "noop"


@pytest.mark.asyncio
async def test_performance_intent_separation():
    service = IntentDecipheringService()
    intent = await service.decipher_intent(
        "The database queries are too slow, speed up API response time"
    )
    assert "Optimize system throughput" in intent.ultimate_goal
    assert "p99_latency_within_sla" in intent.invariants
    assert intent.suggested_methodology == "profile_bottlenecks_and_apply_caching"


@pytest.mark.asyncio
async def test_bugfix_intent_separation():
    service = IntentDecipheringService()
    intent = await service.decipher_intent("Fix the crash in billing webhook endpoint")
    assert "Identify root cause and eliminate defect" in intent.ultimate_goal
    assert "all_test_suites_must_pass" in intent.invariants
    assert intent.suggested_methodology == "reproduce_localize_ast_patch_and_verify"


@pytest.mark.asyncio
async def test_security_intent_separation():
    service = IntentDecipheringService()
    intent = await service.decipher_intent(
        "Add RBAC security guards to all unauthenticated admin endpoints"
    )
    assert "Harden endpoints with role-based access control" in intent.ultimate_goal
    assert "zero_unauthenticated_admin_access" in intent.invariants
    assert intent.suggested_methodology == "inject_explicit_rbac_guards"


@pytest.mark.asyncio
async def test_latent_constraints_extraction():
    service = IntentDecipheringService()
    intent = await service.decipher_intent(
        "Build a fast and safe cache layer with no downtime and clean code"
    )
    assert "zero_infrastructure_cost" in intent.latent_constraints
    assert "fail_closed_security" in intent.latent_constraints
    assert "low_latency_execution" in intent.latent_constraints
    assert "zero_downtime_execution" in intent.latent_constraints
    assert "minimal_code_footprint" in intent.latent_constraints


@pytest.mark.asyncio
async def test_bengali_intent_deciphering():
    service = IntentDecipheringService()
    intent = await service.decipher_intent("লগইন সিস্টেমে বড় একটা বাগ আছে, তাড়াতাড়ি সমাধান করো")
    assert "Identify root cause and eliminate defect" in intent.ultimate_goal
    assert "low_latency_execution" in intent.latent_constraints
    assert "all_test_suites_must_pass" in intent.invariants


@pytest.mark.asyncio
async def test_semantic_memory_recall(mock_memory_service):
    service = IntentDecipheringService(memory_service=mock_memory_service)
    intent = await service.decipher_intent("Optimize Redis latency and caching throughput")
    assert len(intent.relevant_past_memories) > 0
    assert any("latency" in (m.get("summary") or "").lower() for m in intent.relevant_past_memories)
    assert intent.confidence_score >= 0.9
