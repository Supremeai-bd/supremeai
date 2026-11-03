import pytest

from workers.precognitive_watcher import PrecognitiveWatcher
from workers.synaptic_dream import SynapticDreamWorker


@pytest.mark.asyncio
async def test_synaptic_dream_worker_cycle():
    worker = SynapticDreamWorker()
    report = await worker.execute_dream_cycle(tenant_id="test_tenant", retention_days=14)
    # Issue #440 honest contract: the cycle either really pruned ("completed")
    # or honestly reports the store unavailable ("degraded_no_store"). It never
    # returns fabricated counts (the old code hardcoded pruned=5, consolidated=2).
    assert report.status in ("completed", "degraded_no_store")
    assert report.duration_ms >= 0.0
    assert isinstance(report.pruned_count, int)
    assert isinstance(report.consolidated_count, int)
    assert report.consolidated_count == 0  # consolidation honestly not implemented yet


@pytest.mark.asyncio
async def test_precognitive_watcher_scan():
    watcher = PrecognitiveWatcher()
    alerts = await watcher.scan_system_health()
    assert isinstance(alerts, list)
    active_alerts = watcher.get_active_alerts()
    assert isinstance(active_alerts, list)
