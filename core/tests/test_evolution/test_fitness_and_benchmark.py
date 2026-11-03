# backend/tests/evolution/test_fitness_and_benchmark.py
"""Tests for FitnessEvaluator, BenchmarkRunner, and ArtifactIntegrityGate."""

from evolution.artifact_integrity import ArtifactIntegrityGate
from evolution.benchmark_runner import get_benchmark_runner
from evolution.change_proposal import ChangeProposalManager, ChangeType, ProposalState
from evolution.fitness_evaluator import get_fitness_evaluator


def test_fitness_evaluator_multi_factor():
    evaluator = get_fitness_evaluator()
    breakdown = evaluator.evaluate_skill_execution(
        passed_tests=5,
        total_tests=5,
        ast_security_passed=True,
        latency_ms=250.0,
        cost_usd=0.002,
    )
    assert breakdown.correctness_score == 1.0
    assert breakdown.validation_score == 1.0
    assert breakdown.security_score == 1.0
    assert breakdown.composite_fitness >= 0.95


def test_benchmark_runner_promotes_superior_candidate():
    runner = get_benchmark_runner()
    proposal_mgr = ChangeProposalManager()
    proposal = proposal_mgr.create_proposal(
        title="Optimal JSON parser",
        description="Fast parser",
        change_type=ChangeType.CODE_REFACTOR,
        diff_content={"code": "def parse(): pass"},
        target_module="skills/parser.py",
        current_fitness=0.90,
    )

    evaluator = get_fitness_evaluator()
    candidate_eval = evaluator.evaluate_skill_execution(
        passed_tests=10,
        total_tests=10,
        ast_security_passed=True,
        latency_ms=100.0,
    )

    decision = runner.compare_and_decide(
        proposal=proposal,
        candidate_eval=candidate_eval,
        baseline_fitness=0.75,
    )

    assert decision.eligible is True
    assert decision.fitness_delta > 0
    assert decision.safety_status == "PASS"


def test_benchmark_runner_rejects_insecure_candidate():
    runner = get_benchmark_runner()
    proposal_mgr = ChangeProposalManager()
    proposal = proposal_mgr.create_proposal(
        title="Insecure eval injection",
        description="Dangerous code",
        change_type=ChangeType.CODE_REFACTOR,
        diff_content={"code": "eval('__import__')"},
        target_module="skills/eval.py",
        current_fitness=0.50,
    )

    evaluator = get_fitness_evaluator()
    candidate_eval = evaluator.evaluate_skill_execution(
        passed_tests=5,
        total_tests=5,
        ast_security_passed=False,  # Security violation
        latency_ms=100.0,
    )

    decision = runner.compare_and_decide(
        proposal=proposal,
        candidate_eval=candidate_eval,
        baseline_fitness=0.70,
    )

    assert decision.eligible is False
    assert decision.safety_status == "FAIL"


def test_artifact_integrity_gate():
    code = "def add(a, b): return a + b"
    schema = {"name": "add", "version": "1.0.0"}

    proposal_mgr = ChangeProposalManager()
    proposal = proposal_mgr.create_proposal(
        title="Add Skill",
        description="Math utility",
        change_type=ChangeType.NEW_SKILL,
        diff_content={"code": code, "schema": schema},
        target_module="skills/add",
        current_fitness=0.95,
    )

    # 1. Blocked when not promoted
    assert (
        ArtifactIntegrityGate.verify_and_authorize(
            proposal.proposal_id, code, schema, proposal_manager=proposal_mgr
        )
        is False
    )

    # 2. Advance to PROMOTED
    proposal.advance_state(ProposalState.VALIDATED)
    proposal.advance_state(ProposalState.SECURITY_CLEARED)
    proposal.advance_state(ProposalState.BENCHMARKED)
    proposal.advance_state(ProposalState.CANARY_ACTIVE)
    proposal.advance_state(ProposalState.PROMOTED)

    # 3. Authorized with exact match
    assert (
        ArtifactIntegrityGate.verify_and_authorize(
            proposal.proposal_id, code, schema, proposal_manager=proposal_mgr
        )
        is True
    )

    # 4. Tampered code blocked
    tampered_code = "def add(a, b): return a - b"
    assert (
        ArtifactIntegrityGate.verify_and_authorize(
            proposal.proposal_id, tampered_code, schema, proposal_manager=proposal_mgr
        )
        is False
    )
