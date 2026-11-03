# backend/tests/services/test_dynamic_planner.py
import pytest

from services.dynamic_planner import DynamicPlanningEngine, TaskDAG, TaskNode
from services.intent_deciphering import IntentAnalysis


def test_task_dag_topological_sort_valid_order():
    intent = IntentAnalysis(raw_request="test", ultimate_goal="test goal")
    dag = TaskDAG(dag_id="dag_1", intent=intent)

    n1 = TaskNode(id="n1", name="Step 1", capability="c1")
    n2 = TaskNode(id="n2", name="Step 2", capability="c2", dependencies=["n1"])
    n3 = TaskNode(id="n3", name="Step 3", capability="c3", dependencies=["n2"])

    dag.add_node(n1)
    dag.add_node(n2)
    dag.add_node(n3)

    order = dag.topological_sort()
    assert [n.id for n in order] == ["n1", "n2", "n3"]


def test_task_dag_cycle_detection_raises_error():
    intent = IntentAnalysis(raw_request="test", ultimate_goal="test goal")
    dag = TaskDAG(dag_id="dag_cycle", intent=intent)

    n1 = TaskNode(id="n1", name="Step 1", capability="c1", dependencies=["n3"])
    n2 = TaskNode(id="n2", name="Step 2", capability="c2", dependencies=["n1"])
    n3 = TaskNode(id="n3", name="Step 3", capability="c3", dependencies=["n2"])

    dag.add_node(n1)
    dag.add_node(n2)
    dag.add_node(n3)

    with pytest.raises(ValueError, match="Cyclic dependency detected"):
        dag.topological_sort()


@pytest.mark.asyncio
async def test_plan_task_bugfix_pipeline():
    planner = DynamicPlanningEngine()
    intent = IntentAnalysis(
        raw_request="Fix database crash",
        ultimate_goal="Identify root cause and eliminate defect",
        suggested_methodology="reproduce_localize_ast_patch_and_verify",
        invariants=["all_test_suites_must_pass"],
    )

    dag = await planner.plan_task(intent)
    nodes = dag.topological_sort()
    assert len(nodes) == 5  # Probe -> Localize -> Patch -> Verify -> Consolidate

    capabilities = [n.capability for n in nodes]
    assert capabilities == [
        "probe_system_state",
        "ast_localize_defect",
        "apply_safe_code_patch",
        "verify_invariants",
        "consolidate_ai_memory",
    ]


@pytest.mark.asyncio
async def test_plan_task_performance_pipeline():
    planner = DynamicPlanningEngine()
    intent = IntentAnalysis(
        raw_request="API is slow",
        ultimate_goal="Optimize system throughput",
        suggested_methodology="profile_bottlenecks_and_apply_caching",
    )

    dag = await planner.plan_task(intent)
    nodes = dag.topological_sort()
    assert len(nodes) == 5

    capabilities = [n.capability for n in nodes]
    assert capabilities == [
        "probe_system_state",
        "profile_latency_and_throughput",
        "optimize_cache_layers",
        "verify_invariants",
        "consolidate_ai_memory",
    ]


@pytest.mark.asyncio
async def test_plan_task_security_pipeline():
    planner = DynamicPlanningEngine()
    intent = IntentAnalysis(
        raw_request="Add RBAC guards",
        ultimate_goal="Harden endpoints with role-based access control",
        suggested_methodology="inject_explicit_rbac_guards",
    )

    dag = await planner.plan_task(intent)
    nodes = dag.topological_sort()
    assert len(nodes) == 5

    capabilities = [n.capability for n in nodes]
    assert capabilities == [
        "probe_system_state",
        "audit_route_dependencies",
        "inject_rbac_guards",
        "verify_invariants",
        "consolidate_ai_memory",
    ]


@pytest.mark.asyncio
async def test_dag_to_dict_serialization():
    planner = DynamicPlanningEngine()
    intent = IntentAnalysis(raw_request="do work", ultimate_goal="do work")
    dag = await planner.plan_task(intent)

    d = dag.to_dict()
    assert "dag_id" in d
    assert "execution_order" in d
    assert len(d["execution_order"]) == len(dag.nodes)
