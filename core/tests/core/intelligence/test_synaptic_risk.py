from datetime import UTC, datetime, timedelta

from core.intelligence.precognitive_risk import PrecognitiveRiskScorer
from core.intelligence.synaptic_memory import SynapticMemory


def test_consolidation_archives_before_removing_memory():
    memory = SynapticMemory(retention_days=1)
    memory.remember("old", {"value": 1}, importance=0.0)
    memory._memories["old"]["updated_at"] = datetime.now(UTC) - timedelta(days=2)
    report = memory.consolidate()
    assert report.archived == 1
    assert report.deleted == 1
    assert memory.restore(report.archive_ids[0])
    assert memory.insights()["active_memories"] == 1


def test_risk_is_deterministic_and_proposal_only():
    scorer = PrecognitiveRiskScorer(noise_budget=0.0)
    first = scorer.propose("delete production data", irreversible=True)
    second = scorer.propose("delete production data", irreversible=True)
    assert first.to_dict() == second.to_dict()
    assert first.requires_approval
    assert first.severity == "high"
