# backend/tests/learning/test_pattern_and_hypothesis.py
"""Tests for PatternDetector, EvidenceAnalyzer, and HypothesisEngine."""

from evolution.change_proposal import ChangeProposalManager, ChangeType, ProposalState
from learning.evidence_analyzer import EvidenceAnalyzer
from learning.experience import ExperienceRecord, ExperienceStore
from learning.hypothesis_engine import HypothesisEngine
from learning.pattern_detector import PatternDetector


def test_pattern_detector_identifies_syntax_and_timeout_failures():
    store = ExperienceStore()
    store.record(
        ExperienceRecord(
            task_id="t1",
            goal="write code",
            verified=False,
            failures=["AST Syntax Error at line 12"],
        )
    )
    store.record(
        ExperienceRecord(
            task_id="t2", goal="write code", verified=False, failures=["Invalid syntax token: EOF"]
        )
    )
    store.record(
        ExperienceRecord(
            task_id="to1",
            goal="scrape web",
            verified=False,
            failures=["Task execution timed out after 30s"],
        )
    )
    store.record(
        ExperienceRecord(
            task_id="to2",
            goal="scrape web",
            verified=False,
            failures=["Execution timeout: latency exceeded"],
        )
    )

    detector = PatternDetector(store=store)
    patterns = detector.analyze_patterns(min_support=2)

    pattern_types = [p.pattern_type for p in patterns]
    assert "SYNTAX" in pattern_types
    assert "TIMEOUT" in pattern_types


def test_evidence_analyzer_statistical_significance():
    analyzer = EvidenceAnalyzer()
    store = ExperienceStore()
    for i in range(10):
        store.record(
            ExperienceRecord(
                task_id=f"syn_{i}",
                goal="gen code",
                verified=False,
                failures=["Syntax Error: unexpected EOF"],
            )
        )

    detector = PatternDetector(store=store)
    patterns = detector.analyze_patterns(min_support=2)
    assert len(patterns) >= 1

    metrics = analyzer.analyze_pattern_evidence(patterns[0], baseline_rate=0.05)
    assert metrics.is_statistically_significant is True
    assert metrics.effect_size > 1.0


def test_hypothesis_engine_generates_and_converts_proposal():
    store = ExperienceStore()
    store.record(
        ExperienceRecord(
            task_id="b1",
            goal="multi-agent query",
            verified=False,
            failures=["BudgetExceededError: max token cost exceeded"],
        )
    )
    store.record(
        ExperienceRecord(
            task_id="b2",
            goal="multi-agent query",
            verified=False,
            failures=["Token budget exhausted"],
        )
    )

    detector = PatternDetector(store=store)
    analyzer = EvidenceAnalyzer()
    proposal_mgr = ChangeProposalManager()
    engine = HypothesisEngine(detector=detector, analyzer=analyzer, proposal_manager=proposal_mgr)

    hypotheses = engine.generate_hypotheses()
    assert len(hypotheses) == 1
    assert hypotheses[0].category == "PARAMETER_TUNING"
    assert hypotheses[0].expected_delta > 0
    assert "Multi-step reasoning" in hypotheses[0].root_cause

    proposal = engine.convert_hypothesis_to_proposal(hypotheses[0])
    assert proposal is not None
    assert proposal.change_type == ChangeType.PARAMETER_TUNING
    assert proposal.state == ProposalState.DRAFTED
    assert proposal.target_module == "adapters/budget_parameters.py"
