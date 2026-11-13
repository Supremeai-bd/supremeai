# backend/tests/services/test_living_engine.py
import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from core.services.living_engine import LivingEngineOrchestrator


@pytest.fixture(autouse=True)
def isolated_gateway_and_reflection(monkeypatch):
    gateway_module = importlib.import_module("core.llm.llm_gateway")

    async def complete(**kwargs):
        if kwargs.get("session_id", "").startswith("tool_forge_"):
            return {"text": "def run(): return {'status': 'completed', 'result': 10}"}
        return {"text": "Provider fixture result"}

    gateway = SimpleNamespace(acompletion=AsyncMock(side_effect=complete))
    monkeypatch.setattr(gateway_module, "get_llm_gateway", lambda: gateway)
    reflection_module = importlib.import_module("core.engine.self_reflection")

    async def reflect(**kwargs):
        return {
            "is_correct": kwargs["is_success"],
            "bottleneck_analysis": kwargs.get("error_details", ""),
            "future_prevention_strategy": "Fixture recommendation",
        }

    monkeypatch.setattr(
        reflection_module,
        "SelfReflectionLoop",
        lambda: SimpleNamespace(reflect=AsyncMock(side_effect=reflect)),
    )
    return gateway


@pytest.fixture
def isolated_tool_execution(monkeypatch):
    # Orchestration tests do not execute generated code. A separate test proves
    # the real executor's default-deny gate remains in force.
    from core.services import living_engine

    execute = MagicMock(return_value={"status": "completed", "result": 10})
    monkeypatch.setattr(living_engine.ToolForgeService, "execute_tool", execute)
    return execute


@pytest.fixture
def mock_memory():
    mock = MagicMock()
    mock.store_memory.return_value = None
    mock.search_memory.return_value = []
    mock.retrieve_recent.return_value = []
    return mock


@pytest.mark.asyncio
async def test_living_engine_solves_bengali_bugfix_demand(mock_memory, isolated_tool_execution):
    orchestrator = LivingEngineOrchestrator(memory_service=mock_memory)
    prompt = "ডাটাবেস কানেকশন ক্র্যাশ করছে, এটা ঠিক করো"

    solution = await orchestrator.solve_unpredictable_demand(prompt, session_id="test_sess_1")

    assert solution.success is True
    assert solution.domain in ["coder", "bengali"]
    assert len(solution.execution_order) >= 4
    assert solution.fitness_score > 0.5
    assert solution.error is None


@pytest.mark.asyncio
async def test_living_engine_solves_performance_optimization_demand(
    mock_memory, isolated_tool_execution
):
    orchestrator = LivingEngineOrchestrator(memory_service=mock_memory)
    prompt = "API response latency is slow, optimize query caching"

    solution = await orchestrator.solve_unpredictable_demand(prompt, session_id="test_sess_2")

    assert solution.success is True
    assert len(solution.execution_order) >= 4
    assert solution.fitness_score > 0.5


@pytest.mark.asyncio
async def test_living_engine_solves_rbac_security_demand(mock_memory, isolated_tool_execution):
    orchestrator = LivingEngineOrchestrator(memory_service=mock_memory)
    prompt = "Add RBAC role access guards to all unprotected routes"

    solution = await orchestrator.solve_unpredictable_demand(prompt, session_id="test_sess_3")

    assert solution.success is True
    assert len(solution.execution_order) >= 4


@pytest.mark.asyncio
async def test_living_engine_solves_dynamic_synthesis_demand(mock_memory, isolated_tool_execution):
    orchestrator = LivingEngineOrchestrator(memory_service=mock_memory)
    prompt = "Create a custom calculation for user discounts"

    solution = await orchestrator.solve_unpredictable_demand(prompt, session_id="test_sess_4")

    assert solution.success is True
    d = solution.to_dict()
    assert "execution_order" in d
    assert "fitness_score" in d
    assert "execution_time_ms" in d


# ═══════════════════════════════════════════════════════════════════════
# #2705 — SelfReflectionLoop production-hook পরীক্ষা।
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_solution_carries_self_critique_reflection(mock_memory, isolated_tool_execution):
    """সফল সমাধানের পরেও self-critique চলে এবং ফলাফল solution.reflection-এ বসে।"""
    orchestrator = LivingEngineOrchestrator(memory_service=mock_memory)
    solution = await orchestrator.solve_unpredictable_demand(
        "ডাটাবেস ইনডেক্স অপ্টিমাইজ করো", session_id="reflect_sess_1"
    )

    assert solution.success is True
    assert solution.reflection, "reflection খালি হতে পারবে না"
    assert solution.reflection.get("is_correct") is True
    assert "bottleneck_analysis" in solution.reflection
    assert "future_prevention_strategy" in solution.reflection
    # to_dict-ও reflection বহন করে
    assert "reflection" in solution.to_dict()


@pytest.mark.asyncio
async def test_self_reflection_loop_invoked_on_demand(mock_memory, isolated_tool_execution):
    """SelfReflectionLoop.reflect() আসলেই production path থেকে invoke হয় (spy)।"""
    from unittest.mock import AsyncMock

    from core.engine.self_reflection import SelfReflectionLoop

    spy_loop = SelfReflectionLoop()
    spy_loop.reflect = AsyncMock(
        return_value={
            "is_correct": True,
            "success_factor": "Validated execution.",
            "bottleneck_analysis": "None",
            "future_prevention_strategy": "Maintain optimal pattern.",
        }
    )
    orchestrator = LivingEngineOrchestrator(memory_service=mock_memory, self_reflection=spy_loop)
    await orchestrator.solve_unpredictable_demand(
        "API রেট লিমিট ঠিক করো", session_id="reflect_sess_2"
    )

    spy_loop.reflect.assert_awaited_once()
    call_kwargs = spy_loop.reflect.await_args.kwargs
    assert call_kwargs.get("is_success") is True


@pytest.mark.asyncio
async def test_failure_path_still_reflects(mock_memory):
    """ব্যর্থতার ক্ষেত্রেও reflection চলে — bottleneck-learning সংরক্ষিত হয়।"""

    class ExplodingPlanner:
        async def plan_task(self, intent):
            raise RuntimeError("planner exploded")

    orchestrator = LivingEngineOrchestrator(
        memory_service=mock_memory,
        planning_engine=ExplodingPlanner(),  # type: ignore[arg-type]
    )
    solution = await orchestrator.solve_unpredictable_demand(
        "impossible demand", session_id="reflect_sess_3"
    )

    assert solution.success is False
    assert solution.reflection, "ব্যর্থতাতেও reflection থাকতে হবে"
    assert solution.reflection.get("is_correct") is False


@pytest.mark.asyncio
async def test_dynamic_synthesis_respects_default_deny_gate(mock_memory, monkeypatch):
    monkeypatch.delenv("SUPREMEAI_ALLOW_INPROCESS_CODEGEN", raising=False)
    orchestrator = LivingEngineOrchestrator(memory_service=mock_memory)
    solution = await orchestrator.solve_unpredictable_demand("Create a user discount calculator")
    assert solution.success is False
    assert solution.error
    assert "SUPREMEAI_ALLOW_INPROCESS_CODEGEN" in solution.error


@pytest.mark.asyncio
async def test_provider_failure_never_becomes_pipeline_success(
    mock_memory, isolated_gateway_and_reflection, isolated_tool_execution
):
    isolated_gateway_and_reflection.acompletion.side_effect = RuntimeError("Provider unavailable")
    orchestrator = LivingEngineOrchestrator(memory_service=mock_memory)
    solution = await orchestrator.solve_unpredictable_demand("Fix a database connection bug")
    assert solution.success is False
    assert "Provider unavailable" in solution.error
    isolated_tool_execution.assert_not_called()
    assert solution.reflection["is_correct"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("pipeline_fails", [False, True])
async def test_unavailable_reflection_preserves_execution_outcome(
    mock_memory, isolated_tool_execution, pipeline_fails
):
    reflection = SimpleNamespace(reflect=AsyncMock(side_effect=RuntimeError("Private detail")))
    planner = None
    if pipeline_fails:
        planner = SimpleNamespace(plan_task=AsyncMock(side_effect=RuntimeError("planner failed")))
    orchestrator = LivingEngineOrchestrator(
        memory_service=mock_memory, planning_engine=planner, self_reflection=reflection
    )
    solution = await orchestrator.solve_unpredictable_demand("Create a discount calculator")
    assert solution.success is not pipeline_fails
    assert solution.reflection == {"status": "unavailable", "error_type": "RuntimeError"}
    assert "Private detail" not in str(solution.to_dict())
    reflection.reflect.assert_awaited_once()
    assert reflection.reflect.await_args.kwargs["is_success"] is solution.success
