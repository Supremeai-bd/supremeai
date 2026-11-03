# backend/tests/services/test_integration_layer.py
"""Comprehensive Unit Tests for SupremeAI Unified Integration Layer.

Tests:
1. SupremeAIIntegrator initialization and health validation
2. Process pipeline across multiple problem domains (Dev, Business, UX, Reasoning)
3. Background processes (Auto-Evolution, Memory Consolidation) start & graceful shutdown
4. System status dashboard and session telemetry
"""

import pytest

from core.integration_layer import SupremeAIIntegrator, get_integrator


@pytest.mark.asyncio
async def test_supremeai_integrator_initialization():
    integrator = SupremeAIIntegrator()
    initialized = await integrator.initialize()
    assert initialized is True
    assert integrator.initialized is True

    status = integrator.get_system_status()
    assert status["initialized"] is True
    assert "auto_evolution" in status
    assert "performance_metrics" in status


@pytest.mark.asyncio
async def test_supremeai_integrator_process_development():
    integrator = await get_integrator()
    result = await integrator.process("Debug this Python function: def divide(a, b): return a/b")
    assert result.success is True
    assert result.confidence > 0.5
    assert result.processing_time_ms > 0
    assert "reasoning_engine" in result.components_used


@pytest.mark.asyncio
async def test_supremeai_integrator_process_business():
    integrator = await get_integrator()
    result = await integrator.process(
        "Calculate ROI and forecasted growth for investing in AI infrastructure"
    )
    assert result.success is True
    assert result.confidence > 0.5


@pytest.mark.asyncio
async def test_supremeai_integrator_process_ux():
    integrator = await get_integrator()
    result = await integrator.process(
        "Create accessible modern high-converting checkout user flow with WCAG compliance"
    )
    assert result.success is True
    assert result.confidence > 0.5


@pytest.mark.asyncio
async def test_supremeai_integrator_background_and_shutdown():
    integrator = SupremeAIIntegrator()
    await integrator.initialize()
    await integrator.start_background_processes()
    assert integrator._background_running is True

    await integrator.shutdown()
    assert integrator._background_running is False
