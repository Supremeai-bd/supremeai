# backend/tests/services/test_phase3_evolution.py
"""Comprehensive Unit Tests for SupremeAI Phase 3 Self-Evolution Layer.

Tests:
1. PerformanceMonitor & AnomalyDetector (Z-score anomaly detection, metric recording)
2. MemoryConsolidator (4-tier storage, compression, promotion, allocation)
3. AutoTuner (Bayesian / simulated annealing tuning strategies)
4. StrategyOptimizer (UCB / Epsilon-greedy selection)
5. AdvancedEvolutionEngine (Fitness landscape navigation)
6. AutoEvolutionController (6-state evolution cycle, health evaluation, rollback guard)
"""

import pytest

from evolution.advanced_evolution_engine import AdvancedEvolutionEngine
from evolution.auto_evolution_controller import AutoEvolutionController, EvolutionState
from evolution.auto_tuner import AutoTuner
from evolution.memory_consolidator import MemoryConsolidator, MemoryTier
from evolution.performance_monitor import MetricPoint, MetricType, PerformanceMonitor
from evolution.strategy_optimizer import StrategyOptimizer

# ── 1. Performance Monitor & Anomaly Tests ────────────────────────────────────


@pytest.mark.asyncio
async def test_performance_monitor_recording_and_reports():
    monitor = PerformanceMonitor()
    await monitor.collect_all_metrics()
    metrics = monitor.get_current_metrics()
    assert "system.cpu.usage_percent" in metrics

    report = monitor.generate_report(period_minutes=15)
    assert report.report_id.startswith("report_")
    assert len(report.recommendations) > 0


def test_anomaly_detector_z_score():
    from evolution.performance_monitor import AnomalyDetector

    detector = AnomalyDetector(config={"std_dev_threshold": 2.0})

    # Feed normal distribution
    for i in range(15):
        detector.detect(
            MetricPoint(
                name="cpu",
                metric_type=MetricType.GAUGE,
                value=20.0 + (i % 3),
                timestamp=pytest.importorskip("datetime").datetime.now(),
            )
        )

    # Trigger spike
    anomaly = detector.detect(
        MetricPoint(
            name="cpu",
            metric_type=MetricType.GAUGE,
            value=99.0,
            timestamp=pytest.importorskip("datetime").datetime.now(),
        )
    )
    assert anomaly is not None
    assert anomaly["z_score"] > 2.0


# ── 2. Memory Consolidator Tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_memory_consolidator_tiered_lifecycle():
    consolidator = MemoryConsolidator(config={"hot_access_count": 2})

    # Allocate warm block
    block_id = consolidator.allocate(data={"test_key": "test_payload"}, tier=MemoryTier.WARM)
    assert block_id.startswith("blk_")

    # Access block to trigger promotion to HOT
    consolidator.access(block_id)
    consolidator.access(block_id)

    stats = consolidator.get_memory_stats()
    assert stats["total_blocks"] >= 1
    assert stats["blocks_promoted"] >= 1

    # Run consolidation
    res = await consolidator.consolidate()
    assert res.success is True


# ── 3. Auto-Tuner Tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_auto_tuner_performance_tuning():
    tuner = AutoTuner()
    res = await tuner.tune_performance()
    assert res["improvements"]["performance"] > 0
    assert len(res["results"]) > 0

    stats = tuner.get_optimizer_stats()
    assert stats["parameters_registered"] >= 4
    assert stats["total_tunings"] > 0


# ── 4. Strategy Optimizer Tests ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_strategy_optimizer_ucb_selection():
    optimizer = StrategyOptimizer(config={"exploration_rate": 0.0})  # Pure exploit
    strategy, reason = await optimizer.select_strategy({"task": "optimize_cache"})
    assert strategy is not None
    assert strategy.fitness_score >= 0.8
    assert "exploitation" in reason

    opt_res = await optimizer.optimize_strategy({})
    assert opt_res["improvements"]["strategy"] > 0


# ── 5. Advanced Evolution Engine Tests ────────────────────────────────────────


@pytest.mark.asyncio
async def test_advanced_evolution_engine():
    engine = AdvancedEvolutionEngine()
    improvements = {"performance": 0.08, "strategy": 0.06}
    res = await engine.evolve_based_on_improvements(improvements)
    assert res["evolutionary_gain"] > 0.1
    assert res["mode"] == "adaptive"


# ── 6. Auto-Evolution Controller End-to-End Tests ─────────────────────────────


@pytest.mark.asyncio
async def test_auto_evolution_controller_full_cycle():
    controller = AutoEvolutionController()

    # Initial health check
    health = await controller.check_system_health()
    assert health.overall_score >= 0.85
    assert len(health.component_scores) >= 3

    # Run full 6-phase evolution cycle
    cycle = await controller.run_evolution_cycle()
    assert cycle.state == EvolutionState.IDLE
    assert cycle.optimizations_applied >= 3
    assert cycle.duration_seconds >= 0.0
    assert len(cycle.improvements_measured) >= 3

    stats = controller.get_statistics()
    assert stats["total_cycles"] == 1
    assert stats["successful_optimizations"] >= 1


# ── 7. Safety & Rollback Manager Tests ────────────────────────────────────────


@pytest.mark.asyncio
async def test_safety_rollback_manager():
    from core.resilience.safety_rollback_manager import SafetyRollbackManager

    manager = SafetyRollbackManager()

    # Create backup
    backup_id = await manager.create_backup(reason="unit_test")
    assert backup_id.startswith("backup_")

    # List backups
    backups = manager.list_backups()
    assert len(backups) >= 1

    # Rollback to backup
    res = await manager.rollback_to_backup(backup_id)
    assert res.success is True
    assert res.verification_passed is True

    # Checkpoint test
    cp_id = await manager.create_checkpoint()
    assert cp_id.startswith("cp_")
    restored = await manager.restore_checkpoint(cp_id)
    assert restored is True


# ── 8. Distributed Scaling Manager Tests ──────────────────────────────────────


@pytest.mark.asyncio
async def test_distributed_scaling_manager():
    from scaling.distributed_manager import DistributedScalingManager, TaskPriority

    scaling_mgr = DistributedScalingManager()

    # Submit task
    task_id = await scaling_mgr.submit_task(
        task_type="code_synthesis",
        payload={"module": "living_engine"},
        priority=TaskPriority.HIGH,
    )
    assert task_id.startswith("task_")

    # Wait for execution
    task = await scaling_mgr.wait_for_task(task_id, timeout=2)
    assert task is not None
    assert task.assigned_node is not None

    status = scaling_mgr.get_cluster_status()
    assert status["total_nodes"] >= 1
