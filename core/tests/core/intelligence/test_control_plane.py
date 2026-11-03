from core.intelligence.manual_tasks import ManualTaskRegistry
from core.intelligence.models import IntelligenceTier, TaskClassification
from core.intelligence.router import IntelligenceRouter
from core.intelligence.verification import VerificationEngine


def test_router_defaults_to_fast_for_general_tasks():
    decision = IntelligenceRouter().route("say hello")
    assert decision.tier == IntelligenceTier.FAST
    assert decision.classification == TaskClassification.GENERAL
    assert decision.budget.max_agents == 1


def test_router_blocks_irreversible_override():
    decision = IntelligenceRouter().route("deploy this migration", requested_tier="lab")
    assert decision.classification == TaskClassification.IRREVERSIBLE
    assert decision.tier == IntelligenceTier.VERIFIED
    assert decision.budget.requires_approval
    assert not decision.override_applied


def test_router_applies_safe_override_and_budget():
    decision = IntelligenceRouter().route("research this topic", requested_tier="swarm")
    assert decision.tier == IntelligenceTier.SWARM
    assert decision.override_applied
    assert decision.budget.max_agents == 6


def test_verifier_reports_contradictions():
    result = VerificationEngine().verify_text("answer", claims=["missing"])
    assert result.status == "contradicted"
    assert result.contradictions


def test_manual_registry_is_secret_free():
    registry = ManualTaskRegistry()
    task = registry.create(
        "deployment", "Review staging deployment", ["Inspect CI", "Approve canary"], ["CI run URL"]
    )
    assert task.secret_free
    assert registry.report()[0]["title"] == task.title
