# backend/tests/services/test_self_correction.py
from unittest.mock import MagicMock

import pytest

from services.dynamic_planner import TaskDAG, TaskNode
from services.intent_deciphering import IntentAnalysis
from services.self_correction import SelfCorrectionService


@pytest.fixture
def mock_memory_service():
    mock = MagicMock()
    mock.store_memory.return_value = None
    return mock


@pytest.mark.asyncio
async def test_simulate_pre_execution_valid_dag():
    service = SelfCorrectionService()
    intent = IntentAnalysis(raw_request="test", ultimate_goal="test goal")
    dag = TaskDAG(dag_id="dag_valid", intent=intent)
    dag.add_node(TaskNode(id="n1", name="Step 1", capability="probe"))
    dag.add_node(TaskNode(id="n2", name="Step 2", capability="patch", dependencies=["n1"]))

    result = await service.simulate_pre_execution(dag)
    assert result.is_valid is True
    assert result.stage == "pre_flight"
    assert len(result.violations) == 0


@pytest.mark.asyncio
async def test_simulate_pre_execution_catches_empty_capability():
    service = SelfCorrectionService()
    intent = IntentAnalysis(raw_request="test", ultimate_goal="test goal")
    dag = TaskDAG(dag_id="dag_invalid", intent=intent)
    dag.add_node(TaskNode(id="n1", name="Step 1", capability=""))

    result = await service.simulate_pre_execution(dag)
    assert result.is_valid is False
    assert any("missing required capability" in v for v in result.violations)


@pytest.mark.asyncio
async def test_audit_post_execution_asserts_test_invariants():
    service = SelfCorrectionService()
    intent = IntentAnalysis(
        raw_request="test",
        ultimate_goal="test",
        invariants=["all_test_suites_must_pass"],
    )
    dag = TaskDAG(dag_id="dag_post", intent=intent)
    node = TaskNode(id="n1", name="Step 1", capability="execute")
    dag.add_node(node)

    # 1. Success case
    res_ok = await service.audit_post_execution(dag, {"test_status": "passed"}, duration_ms=100.0)
    assert res_ok.is_valid is True
    assert res_ok.fitness_score > 0.8

    # 2. Violation case
    res_fail = await service.audit_post_execution(dag, {"test_status": "failed"}, duration_ms=100.0)
    assert res_fail.is_valid is False
    assert any("test suite failed" in v for v in res_fail.violations)


@pytest.mark.asyncio
async def test_execute_with_self_healing_success(mock_memory_service):
    service = SelfCorrectionService(memory_service=mock_memory_service)
    intent = IntentAnalysis(raw_request="run", ultimate_goal="run task")
    dag = TaskDAG(dag_id="dag_heal", intent=intent)
    dag.add_node(TaskNode(id="n1", name="Step 1", capability="do_action"))

    attempt_count = 0

    async def faulty_executor(node, context):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 2:
            raise ValueError("Transient glitch")
        return {"output": "recovered"}

    output = await service.execute_with_self_healing(dag, faulty_executor)
    assert output["status"] == "success"
    assert output["results"]["n1"] == {"output": "recovered"}
    assert attempt_count == 2
    assert mock_memory_service.store_memory.called
