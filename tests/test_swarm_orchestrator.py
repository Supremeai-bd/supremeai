import os

os.environ.setdefault("OPENROUTER_API_KEY", "")
os.environ.setdefault("HF_API_KEY", "")
os.environ.setdefault("OLLAMA_URL", "http://localhost:11434")

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def orchestrator():
    from brain.crewai_agents import CrewAgent, CrewTask
    from brain.swarm_orchestrator import SwarmOrchestrator

    agent1 = MagicMock(spec=CrewAgent)
    agent1.role = "planner"
    agent2 = MagicMock(spec=CrewAgent)
    agent2.role = "executor"
    orch = SwarmOrchestrator(agents=[agent1, agent2], max_workers=2)
    return orch, agent1, agent2


class TestSwarmOrchestrator:
    def test_execute_swarm_returns_all_results(self, orchestrator):
        orch, agent1, agent2 = orchestrator
        agent1.execute.return_value = "result-a"
        agent2.execute.return_value = "result-b"

        task_a = MagicMock()
        task_a.description = "task alpha"
        task_b = MagicMock()
        task_b.description = "task beta"
        results = orch.execute_swarm([task_a, task_b])

        assert "task alpha" in results
        assert "task beta" in results

    def test_execute_swarm_assigns_round_robin(self, orchestrator):
        orch, agent1, agent2 = orchestrator
        agent1.execute.return_value = "ok"
        agent2.execute.return_value = "ok"

        tasks = [MagicMock(description=f"t{i}") for i in range(4)]
        results = orch.execute_swarm(tasks)

        assert agent1.execute.call_count == 2
        assert agent2.execute.call_count == 2

    def test_execute_swarm_task_output_set(self, orchestrator):
        orch, agent1, _ = orchestrator
        agent1.execute.return_value = "output-1"
        task = MagicMock()
        task.description = "my task"
        orch.execute_swarm([task])
        assert task.output == "output-1"

    def test_execute_swarm_handles_failure(self, orchestrator):
        orch, agent1, _ = orchestrator
        agent1.execute.side_effect = RuntimeError("agent crashed")
        task = MagicMock()
        task.description = "failing task"
        results = orch.execute_swarm([task])
        assert "Error:" in results["failing task"]
