# backend/tests/orchestration/test_master_cognitive_orchestrator.py
"""Tests for SupremeAI Master Cognitive Orchestrator."""

import pytest

from core.orchestration.cognitive_pipeline_dispatcher import (
    CognitiveIntent,
    get_master_orchestrator,
)


@pytest.mark.asyncio
async def test_self_healing_pipeline_authorized():
    orchestrator = get_master_orchestrator()
    payload = {
        "error": "TimeoutError in step execution",
        "target_file": "adapters/task_executor.py",
        "discovery_query": "asyncio timeout resilience",
    }
    result = await orchestrator.dispatch(CognitiveIntent.REPAIR, payload)
    assert result.status == "SUCCESS"
    assert "01_diagnostic_incident_replay" in result.stages_completed
    assert "04_solution_synthesis_sandbox" in result.stages_completed
    assert "05_governance_policy_authorization" in result.stages_completed
    assert result.confidence >= 0.90


@pytest.mark.asyncio
async def test_self_healing_pipeline_governance_blocked():
    orchestrator = get_master_orchestrator()
    # Protected target: core/security
    payload = {
        "error": "Auth token bypass attempt",
        "target_file": "core/security/auth_guard.py",
    }
    result = await orchestrator.dispatch(CognitiveIntent.REPAIR, payload)
    assert result.status == "BLOCKED"
    assert "Governance policy blocked repair" in result.summary
    assert result.confidence == 0.0


@pytest.mark.asyncio
async def test_deep_synthesis_pipeline():
    orchestrator = get_master_orchestrator()
    payload = {
        "demand": "Design high-performance distributed token bucket rate limiter",
    }
    result = await orchestrator.dispatch(CognitiveIntent.FEATURE_SYNTHESIS, payload)
    assert result.status == "SUCCESS"
    assert "01_project_dna_fingerprint" in result.stages_completed
    assert "02_multi_model_knowledge_squeezer" in result.stages_completed
    assert "05_eternal_memory_ingestion" in result.stages_completed
    assert result.confidence >= 0.90


@pytest.mark.asyncio
async def test_autonomous_audit_pipeline():
    orchestrator = get_master_orchestrator()
    result = await orchestrator.dispatch(CognitiveIntent.AUDIT_RADAR, {})
    assert result.status == "SUCCESS"
    assert "01_universal_gap_finder_scan" in result.stages_completed
    assert "03_memory_revaluation" in result.stages_completed


@pytest.mark.asyncio
async def test_governed_evolution_pipeline_success_and_rejection():
    orchestrator = get_master_orchestrator()

    # Allowed target
    ok_res = await orchestrator.dispatch(
        CognitiveIntent.EVOLUTION,
        {"target_module": "skills/custom_math.py"},
    )
    assert ok_res.status == "SUCCESS"

    # Protected target
    blocked_res = await orchestrator.dispatch(
        CognitiveIntent.EVOLUTION,
        {"target_module": "billing/stripe_sync.py"},
    )
    assert blocked_res.status == "REJECTED"
    assert "blocked by governance policy" in blocked_res.summary


# ═══════════════════════════════════════════════════════════════════════
# #2705 — no-stub assertions: প্রতিটি artifact এখন সত্যিকারের উৎস থেকে।
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_self_healing_wires_real_decide_and_execute():
    """Discovery stage এখন আসল governed ReAct (decide_and_execute) ফল বহন করে।"""
    orchestrator = get_master_orchestrator()
    payload = {
        "error": "TimeoutError in step execution",
        "target_file": "adapters/task_executor.py",
    }
    result = await orchestrator.dispatch(CognitiveIntent.REPAIR, payload)

    assert result.status == "SUCCESS"
    # আসল decide_and_execute wire-এর প্রমাণ: decision + outcome artifact উভয়ই আছে
    assert "discovery_decision" in result.artifacts
    assert "discovery_outcome" in result.artifacts
    assert "source" in result.artifacts["discovery_decision"]
    assert "executed" in result.artifacts["discovery_outcome"]
    # পুরনো স্টাব ফিরে আসা নিষিদ্ধ
    assert "candidate_solutions" not in result.artifacts
    patch = result.artifacts["patch_candidate"]
    # #2707: verified_in_sandbox এখন প্রকৃত playground-স্যান্ডবক্স ফলাফল —
    # tool-gate executed থেকে স্বাধীন; sandbox না থাকলে সৎ False।
    assert "playground_verification" in result.artifacts
    pg = result.artifacts["playground_verification"]
    assert pg["verified"] == patch["verified_in_sandbox"]
    assert "diff" not in patch  # fake diff আর নেই


@pytest.mark.asyncio
async def test_deep_synthesis_no_stub_memory_or_dna():
    """memory_id এখন আসল EpisodicMemory episode-id; project_dna আসল স্ক্যান-ফল।"""
    orchestrator = get_master_orchestrator()
    result = await orchestrator.dispatch(
        CognitiveIntent.FEATURE_SYNTHESIS,
        {"demand": "Design a token bucket rate limiter"},
    )

    assert result.status == "SUCCESS"
    assert result.confidence >= 0.90

    memory_id = result.artifacts["memory_id"]
    assert memory_id != "mem_vector_9f83a"  # পুরনো hardcoded স্টাব
    assert memory_id.startswith("ep_")  # আসল episode id চুক্তি

    dna = result.artifacts["project_dna"]
    assert "scan_status" in dna  # আসল স্ক্যান ক্ষেত্র, hardcoded 48 নয়
    assert "services_count" not in dna

    consensus = result.artifacts["multi_model_consensus"]
    assert consensus["source"] in ("llm_consensus", "deterministic_summary")
    assert "distilled_principles" not in consensus  # fake principles সরানো

    truth = result.artifacts["truth_validation"]
    assert "basis" in truth  # সত্যতার ভিত্তি লিপিবদ্ধ
    skill = result.artifacts["generated_skill"]
    assert skill["name"].startswith("capability_")
    assert skill["derived_from_demand"] is True


@pytest.mark.asyncio
async def test_autonomous_audit_real_bus_and_drift_metrics():
    """gap_metrics এখন error_event_bus.stats() থেকে; drift-এ আসল গণনা।"""
    orchestrator = get_master_orchestrator()
    result = await orchestrator.dispatch(CognitiveIntent.AUDIT_RADAR, {})

    assert result.status == "SUCCESS"
    metrics = result.artifacts["gap_metrics"]
    assert metrics["source"] == "error_event_bus.stats()"
    assert set(metrics.keys()) >= {"critical", "total_emitted", "registered_listeners", "status"}
    assert metrics["status"] in ("HEALTHY", "DEGRADED")
    # ডামি হার্ডকোডেড ১২-এর বদলে আসল episode-গণনা
    assert isinstance(result.artifacts["memory_revalued_count"], int)
    drift = result.artifacts["documentation_drift"]
    assert drift["sync_status"] in ("ALIGNED", "DRIFTED", "UNAVAILABLE")
    if drift["sync_status"] != "UNAVAILABLE":
        assert "listed_scripts" in drift and "actual_scripts" in drift


@pytest.mark.asyncio
async def test_governed_evolution_honest_stage_names():
    """প্রতারণামূলক stage-নাম নয় — টুল-গেট বন্ধ থাকলে pending-অবস্থা সৎভাবে লেখা।"""
    orchestrator = get_master_orchestrator()
    result = await orchestrator.dispatch(
        CognitiveIntent.EVOLUTION,
        {"target_module": "skills/custom_math.py"},
    )
    assert result.status == "SUCCESS"
    bench = result.artifacts["sandbox_benchmark"]
    assert bench in ("executed", "pending_tool_gate")
    # stage-নাম artifact-অবস্থার সাথে সংগতিপূর্ণ
    if bench == "pending_tool_gate":
        assert "03_sandbox_benchmark_pending" in result.stages_completed
        assert "04_canary_promotion_pending" in result.stages_completed
    else:
        assert "03_sandbox_benchmarked" in result.stages_completed
