"""
Unit tests for SupremeAI Micro StateGraph Engine
"""

import pytest

from runs.stategraph import (
    END,
    CompiledGraph,
    RecursionLimitExceeded,
    StateGraph,
    StateGraphError,
)


class MockCheckpointer:
    def __init__(self):
        self.storage = {}

    def save_graph_state(self, run_id: str, node: str, state: dict, step_index: int = 0):
        self.storage[run_id] = {
            "node": node,
            "state": dict(state),
            "step_index": step_index,
        }

    def load_graph_state(self, run_id: str):
        record = self.storage.get(run_id)
        if record:
            return record["state"]
        return None


@pytest.mark.asyncio
async def test_linear_graph_execution():
    graph = StateGraph()

    async def step_one(state: dict):
        return {"step1": "completed", "value": state.get("value", 0) + 1}

    def step_two(state: dict):
        return {"step2": "completed", "value": state["value"] * 2}

    graph.add_node("step_one", step_one)
    graph.add_node("step_two", step_two)
    graph.set_entry_point("step_one")
    graph.add_edge("step_one", "step_two")
    graph.add_edge("step_two", END)

    compiled = graph.compile()
    assert isinstance(compiled, CompiledGraph)

    result = await compiled.invoke({"value": 5})

    assert result["step1"] == "completed"
    assert result["step2"] == "completed"
    assert result["value"] == 12  # (5 + 1) * 2
    assert result["__completed__"] is True
    assert result["__interrupted__"] is False
    assert len(result["__execution_trace__"]) == 2


@pytest.mark.asyncio
async def test_cyclic_graph_with_conditional_edge():
    graph = StateGraph()

    def generate_node(state: dict):
        attempts = state.get("attempts", 0) + 1
        return {"attempts": attempts}

    def evaluate_node(state: dict):
        passed = state["attempts"] >= 3
        return {"passed": passed}

    def route_evaluation(state: dict) -> str:
        return "continue" if state.get("passed") else "retry"

    graph.add_node("generate", generate_node)
    graph.add_node("evaluate", evaluate_node)
    graph.set_entry_point("generate")
    graph.add_edge("generate", "evaluate")
    graph.add_conditional_edges(
        "evaluate",
        route_evaluation,
        {
            "retry": "generate",
            "continue": END,
        },
    )

    compiled = graph.compile()
    result = await compiled.invoke({})

    assert result["attempts"] == 3
    assert result["passed"] is True
    assert result["__completed__"] is True
    # Trace should show 3 cycles of generate + evaluate = 6 steps
    assert len(result["__execution_trace__"]) == 6


@pytest.mark.asyncio
async def test_recursion_limit_guard():
    graph = StateGraph()

    def infinite_loop(state: dict):
        return {"count": state.get("count", 0) + 1}

    graph.add_node("infinite", infinite_loop)
    graph.set_entry_point("infinite")
    graph.add_edge("infinite", "infinite")

    compiled = graph.compile()

    with pytest.raises(RecursionLimitExceeded):
        await compiled.invoke({}, config={"max_iterations": 10})


@pytest.mark.asyncio
async def test_state_reducer_list_append():
    graph = StateGraph()

    def node_a(state: dict):
        return {"messages": ["Message from A"]}

    def node_b(state: dict):
        return {"messages": ["Message from B"]}

    graph.add_node("node_a", node_a)
    graph.add_node("node_b", node_b)
    graph.set_entry_point("node_a")
    graph.add_edge("node_a", "node_b")
    graph.add_edge("node_b", END)

    compiled = graph.compile()
    result = await compiled.invoke({"messages": ["Initial message"]})

    assert result["messages"] == [
        "Initial message",
        "Message from A",
        "Message from B",
    ]


@pytest.mark.asyncio
async def test_interrupt_before_and_resume():
    checkpointer = MockCheckpointer()
    graph = StateGraph()

    def node_one(state: dict):
        return {"node_one": "done"}

    def sensitive_node(state: dict):
        return {"sensitive_action": "executed", "confirmed_by": state.get("approved_by")}

    graph.add_node("node_one", node_one)
    graph.add_node("sensitive_node", sensitive_node)
    graph.set_entry_point("node_one")
    graph.add_edge("node_one", "sensitive_node")
    graph.add_edge("sensitive_node", END)

    # Interrupt before sensitive_node requires HITL approval
    compiled = graph.compile(checkpointer=checkpointer, interrupt_before=["sensitive_node"])

    run_id = "test-run-123"
    result = await compiled.invoke({"user": "admin"}, config={"run_id": run_id})

    # Assert graph paused before sensitive_node
    assert result.get("__interrupted__") is True
    assert result.get("__interrupted_at__") == "sensitive_node"
    assert "sensitive_action" not in result

    # Checkpoint should have been saved
    assert run_id in checkpointer.storage
    saved_state = checkpointer.storage[run_id]["state"]
    assert saved_state["node_one"] == "done"

    # Now simulate approval and resume
    resumed_result = await compiled.resume(
        run_id=run_id,
        resume_state={"approved_by": "Saiful"},
    )

    assert resumed_result.get("__completed__") is True
    assert resumed_result.get("__interrupted__") is False
    assert resumed_result["sensitive_action"] == "executed"
    assert resumed_result["confirmed_by"] == "Saiful"


def test_mermaid_export():
    graph = StateGraph()
    graph.add_node("step1", lambda s: s)
    graph.add_node("step2", lambda s: s)
    graph.set_entry_point("step1")
    graph.add_edge("step1", "step2")
    graph.add_edge("step2", END)

    mermaid = graph.to_mermaid()
    assert "graph TD" in mermaid
    assert "START([Start]) --> step1" in mermaid
    assert "step1 --> step2" in mermaid
    assert "step2 --> END([End])" in mermaid
