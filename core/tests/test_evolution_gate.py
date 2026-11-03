import pytest

from backend.ecosystem.evolution_gate import (
    EvidenceReport,
    PromotionDecision,
    evaluate_promotion,
)


def test_failed_security_rejects_promotion():
    result = evaluate_promotion(EvidenceReport(True, False, True, True, True), impact_score=0.1)
    assert result.decision is PromotionDecision.REJECT
    assert "security_failed" in result.reasons


def test_high_impact_change_stages_until_canary():
    result = evaluate_promotion(EvidenceReport(True, True, True, True, False), impact_score=0.8)
    assert result.decision is PromotionDecision.STAGE
    assert "approval_or_canary_required" in result.reasons


def test_complete_evidence_promotes():
    result = evaluate_promotion(EvidenceReport(True, True, True, True, True), impact_score=0.2)
    assert result.decision is PromotionDecision.PROMOTE
    assert result.reasons == ()


def test_invalid_impact_is_rejected():
    result = evaluate_promotion(EvidenceReport(True, True, True, True, True), impact_score=2)
    assert result.decision is PromotionDecision.REJECT
    assert result.reasons == ("invalid_impact_score",)
