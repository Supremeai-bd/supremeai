from unittest.mock import AsyncMock, patch

import pytest

from core.orchestration.trio_pipeline import TrioPipeline


# A dummy class to represent the result object returned by agents
class DummyAgentResult:
    def __init__(self, output="", confidence=1.0, issues=None, metadata=None):
        self.output = output
        self.confidence = confidence
        self.issues = issues or []
        self.metadata = metadata or {}

    def to_dict(self):
        return {
            "output": self.output,
            "confidence": self.confidence,
            "issues": self.issues,
            "metadata": self.metadata,
        }


@pytest.fixture
def mock_pipeline_agents():
    """Mock the agents to isolate TrioPipeline's orchestration logic."""
    with patch("agents.ide.trio_adapters.GeminiWriter.run", new_callable=AsyncMock) as mock_writer:
        with patch(
            "agents.ide.trio_adapters.KiloReviewer.run", new_callable=AsyncMock
        ) as mock_reviewer:
            with patch(
                "agents.ide.trio_adapters.ClineChecker.run", new_callable=AsyncMock
            ) as mock_checker:
                yield {"writer": mock_writer, "reviewer": mock_reviewer, "checker": mock_checker}


@pytest.mark.asyncio
async def test_trio_pipeline_successful_flow(mock_pipeline_agents):
    """Test standard happy path: Writer succeeds, no review issues, Cline marks ready."""
    mock_pipeline_agents["writer"].return_value = DummyAgentResult(
        output="print('hello')", confidence=1.0
    )
    mock_pipeline_agents["reviewer"].return_value = DummyAgentResult(issues=[])
    mock_pipeline_agents["checker"].return_value = DummyAgentResult(
        issues=[], metadata={"ready_for_production": True}
    )

    pipeline = TrioPipeline()
    result = await pipeline.execute("Write a print script")

    assert result["status"] == "ready"
    assert result["ready_for_production"] is True
    assert result["generated_code"] == "print('hello')"

    # Verify all agents were called in order
    mock_pipeline_agents["writer"].assert_called_once()
    mock_pipeline_agents["reviewer"].assert_called_once()
    mock_pipeline_agents["checker"].assert_called_once()


@pytest.mark.asyncio
async def test_trio_pipeline_writer_failure(mock_pipeline_agents):
    """Test short-circuit behavior when the writer fails."""
    # Confidence 0.0 indicates a failure
    mock_pipeline_agents["writer"].return_value = DummyAgentResult(
        output="Error: could not generate", confidence=0.0, issues=["Compilation error"]
    )

    pipeline = TrioPipeline()
    result = await pipeline.execute("Write a failing script")

    assert result["status"] == "failed"
    assert result["generated_code"] == ""
    assert result["ready_for_production"] is False
    # FIX (final-test ci-fixes): production contract এখন stage-নাম সহ সৎ summary দেয়
    # ("Writer stage failed: <output>") — পুরনো "Stage 1 (Gemini) failed" ফরম্যাট আর নেই।
    assert "Writer stage failed" in result["summary"]

    # Ensure downstream agents are NOT called
    mock_pipeline_agents["reviewer"].assert_not_called()
    mock_pipeline_agents["checker"].assert_not_called()


@pytest.mark.asyncio
async def test_trio_pipeline_needs_review(mock_pipeline_agents):
    """Test status logic when the reviewer finds issues."""
    mock_pipeline_agents["writer"].return_value = DummyAgentResult(
        output="def foo(): pass", confidence=1.0
    )
    # Reviewer finds 2 issues
    mock_pipeline_agents["reviewer"].return_value = DummyAgentResult(
        issues=["Missing type hints", "No docstring"]
    )
    mock_pipeline_agents["checker"].return_value = DummyAgentResult(
        issues=[], metadata={"ready_for_production": False}
    )

    pipeline = TrioPipeline()
    result = await pipeline.execute("Write a python function")

    assert result["status"] == "needs_review"
    assert result["ready_for_production"] is False
    assert "2 issue(s) found" in result["summary"]
