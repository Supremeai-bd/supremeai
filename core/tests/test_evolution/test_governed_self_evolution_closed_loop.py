# backend/tests/evolution/test_governed_self_evolution_closed_loop.py
"""Comprehensive 21-State Transition Contract & Negative Security Governance Test."""

from core.security.governance_policy import get_governance_policy
from evolution.artifact_integrity import ArtifactIntegrityGate, canonical_artifact_hash
from evolution.benchmark_runner import BenchmarkRunner
from evolution.canary_manager import CanaryRolloutController
from evolution.change_proposal import ChangeProposalManager, ChangeType, ProposalState
from evolution.fitness_evaluator import FitnessEvaluator
from learning.evidence_analyzer import EvidenceAnalyzer
from learning.experience import ExperienceRecord, ExperienceStore
from learning.hypothesis_engine import HypothesisEngine
from learning.pattern_detector import PatternDetector


def test_21_state_governed_self_evolution_closed_loop():
    """Validates the complete 21-state contract from task failure to promoted capability."""
    # 01. Experience capture
    store = ExperienceStore()
    store.record(
        ExperienceRecord(
            task_id="t_ast_01",
            goal="generate math skill",
            verified=False,
            failures=["AST Syntax Error: invalid token at line 4"],
        )
    )
    store.record(
        ExperienceRecord(
            task_id="t_ast_02",
            goal="generate math skill",
            verified=False,
            failures=["AST Syntax Error: unclosed parenthesis"],
        )
    )

    # 02. Failure normalization
    records = store.get_recent(limit=10)
    assert len(records) == 2

    # 03. Pattern detection & 04. Pattern clustering
    detector = PatternDetector(store=store)
    patterns = detector.analyze_patterns(min_support=2)
    assert len(patterns) >= 1
    syntax_pattern = next(p for p in patterns if p.pattern_type == "SYNTAX")

    # 05. Evidence collection
    assert len(syntax_pattern.evidence) == 2
    assert "t_ast_01" in syntax_pattern.evidence_task_ids

    # 06. Statistical validation
    analyzer = EvidenceAnalyzer()
    metrics = analyzer.analyze_pattern_evidence(syntax_pattern, baseline_rate=0.05)
    assert metrics.is_statistically_significant is True
    assert metrics.effect_size > 1.0

    # 07. Hypothesis creation
    proposal_mgr = ChangeProposalManager()
    engine = HypothesisEngine(detector=detector, analyzer=analyzer, proposal_manager=proposal_mgr)
    hypotheses = engine.generate_hypotheses()
    assert len(hypotheses) >= 1
    hyp = hypotheses[0]
    assert hyp.category == "PROMPT_OPTIMIZATION"
    assert "Markdown" in hyp.root_cause

    # 08. Proposal generation & 09. Governance pre-check
    proposal = engine.convert_hypothesis_to_proposal(hyp)
    assert proposal is not None

    # 10. Proposal DRAFTED
    assert proposal.state == ProposalState.DRAFTED

    # 11. Candidate artifact creation & 12. Static/AST security gate
    candidate_code = "def math_add(a: int, b: int) -> int:\n    return a + b\n"
    candidate_schema = {"name": "math_add", "description": "Add two integers"}

    # 13. Artifact integrity hash
    computed_hash = canonical_artifact_hash(candidate_code, candidate_schema)
    assert len(computed_hash) == 64

    proposal.diff_content = {
        "code": candidate_code,
        "schema": candidate_schema,
        "artifact_hash": computed_hash,
    }

    # 14. Sandbox validation & 15. Baseline benchmark vs 16. Candidate benchmark
    evaluator = FitnessEvaluator()
    candidate_eval = evaluator.evaluate_skill_execution(
        passed_tests=5,
        total_tests=5,
        ast_security_passed=True,
        latency_ms=45.0,
    )
    assert candidate_eval.composite_fitness > 0.85

    # 17. Fitness comparison
    benchmarker = BenchmarkRunner()
    decision = benchmarker.compare_and_decide(
        proposal=proposal,
        candidate_eval=candidate_eval,
        baseline_fitness=0.75,
    )
    assert decision.eligible is True
    assert decision.fitness_delta > 0.10
    proposal.advance_state(ProposalState.BENCHMARKED)

    # 18. Canary simulation
    canary = CanaryRolloutController(proposal_manager=proposal_mgr)
    canary_deployed = canary.deploy_canary(proposal.proposal_id, sample_ratio=0.10)
    assert canary_deployed is True
    for _ in range(20):
        canary.record_observation(proposal.proposal_id, success=True, latency_ms=42.0)

    stats = canary.get_canary_stats(proposal.proposal_id)
    assert stats["success_rate"] == 1.0

    # 19. Canary promotion & 20. PROMOTED transition
    promoted = canary.evaluate_and_promote(proposal.proposal_id)
    assert promoted is True
    assert proposal.state == ProposalState.PROMOTED

    # 21. Cryptographic Artifact Integrity Verification at Installer Boundary
    is_authorized = ArtifactIntegrityGate.verify_and_authorize(
        proposal.proposal_id, candidate_code, candidate_schema, proposal_manager=proposal_mgr
    )
    assert is_authorized is True

    # 22. Audit event + persistence verification
    persisted = proposal_mgr.proposals.get(proposal.proposal_id)
    assert persisted is not None
    assert persisted.state == ProposalState.PROMOTED


def test_governance_policy_negative_security_rejections():
    """Verifies that malicious or illegal self-modifications are strictly rejected fail-closed."""
    get_governance_policy()
    proposal_mgr = ChangeProposalManager()

    # 1. Attempt to modify Auth Guards
    auth_proposal = proposal_mgr.create_proposal(
        title="Bypass Auth",
        description="Tamper with authentication tokens",
        change_type=ChangeType.CODE_REFACTOR,
        diff_content={"bypass": True},
        target_module="backend/api/dependencies.py",
    )
    assert auth_proposal.state == ProposalState.REJECTED
    assert "Governance policy violation" in auth_proposal.rejection_reason

    # 2. Attempt Path Traversal into Security Vault
    traversal_proposal = proposal_mgr.create_proposal(
        title="Path Traversal",
        description="Escape to security vault",
        change_type=ChangeType.CODE_REFACTOR,
        diff_content={"exploit": True},
        target_module="../core/security/secret_vault.py",
    )
    assert traversal_proposal.state == ProposalState.REJECTED

    # 3. Attempt to modify Billing Subsystem
    billing_proposal = proposal_mgr.create_proposal(
        title="Modify Quotas",
        description="Free credits hack",
        change_type=ChangeType.PARAMETER_TUNING,
        diff_content={"free_credits": 99999},
        target_module="billing/stripe_handler.py",
    )
    assert billing_proposal.state == ProposalState.REJECTED

    # 4. Attempt to modify Runtime Budget Guard
    budget_proposal = proposal_mgr.create_proposal(
        title="Disable Budget Guard",
        description="Unlimited execution time",
        change_type=ChangeType.PARAMETER_TUNING,
        diff_content={"disable_guard": True},
        target_module="runtime/budget_guard.py",
    )
    assert budget_proposal.state == ProposalState.REJECTED
