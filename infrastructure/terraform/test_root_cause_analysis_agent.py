# backend/tests/analysis/test_root_cause_analysis_agent.py

import pytest
from unittest.mock import AsyncMock, MagicMock

# The path assumes the tests are run from the root of the 'backend' directory
# or the path is correctly configured.
from analysis.root_cause_analysis_agent import RootCauseAnalysisAgent


@pytest.fixture
def mock_clients():
    """Provides mock clients for the agent."""
    return {
        "llm_client": MagicMock(),
        "db_pool": AsyncMock(),
        "git_client": MagicMock(),
    }


@pytest.mark.asyncio
async def test_analyze_pipeline(mocker, mock_clients):
    """
    Unit test for the analyze method of RootCauseAnalysisAgent.

    This test verifies that the `analyze` method correctly orchestrates its
    internal methods (_parse_logs, _parse_traces, _get_context_from_git)
    and returns the expected analysis result.
    """
    # --- 1. Setup Mocks ---

    # Mock the internal async methods of the agent
    mock_parsed_logs = [{"file": "service.log", "error_type": "NullPointerException"}]
    mocker.patch.object(
        RootCauseAnalysisAgent,
        "_parse_logs",
        new_callable=AsyncMock,
        return_value=mock_parsed_logs,
    )

    mock_parsed_traces = [{"service": "payment_processor", "duration_ms": 1500}]
    mocker.patch.object(
        RootCauseAnalysisAgent,
        "_parse_traces",
        new_callable=AsyncMock,
        return_value=mock_parsed_traces,
    )

    mock_git_context = {"commit": "a1b2c3d4", "author": "dev@supreme.ai"}
    mocker.patch.object(
        RootCauseAnalysisAgent,
        "_get_context_from_git",
        new_callable=AsyncMock,
        return_value=mock_git_context,
    )

    # --- 2. Initialize Agent and Run Analysis ---

    agent = RootCauseAnalysisAgent(**mock_clients)

    incident_id = "INC-TEST-001"
    log_files = ["/path/to/service.log"]
    trace_files = ["/path/to/trace.json"]

    result = await agent.analyze(
        incident_id=incident_id, log_files=log_files, trace_files=trace_files
    )

    # --- 3. Assertions ---

    # Verify that internal methods were called correctly
    RootCauseAnalysisAgent._parse_logs.assert_awaited_once_with(log_files)
    RootCauseAnalysisAgent._parse_traces.assert_awaited_once_with(trace_files)
    # The arguments for git context are hardcoded in the example, so we match them.
    RootCauseAnalysisAgent._get_context_from_git.assert_awaited_once_with(
        "src/payment_processor.py", 42
    )

    # Verify the final result (currently hardcoded in the agent)
    expected_root_cause = "The 'payment_processor' service is failing due to a NullPointerException when handling a specific payment type, likely introduced in commit a1b2c3d4."
    assert result is not None
    assert "root_cause" in result
    assert result["root_cause"] == expected_root_cause
    assert "code_patch_suggestion" in result

    # Optional: Verify the prompt sent to the LLM (if the LLM client were called)
    # In the current implementation, the LLM call is commented out,
    # so we can't test it directly without modification.
    # If it were active, the test would look like this:
    # mock_clients["llm_client"].generate.assert_called_once()
    # call_args = mock_clients["llm_client"].generate.call_args[0][0]
    # assert incident_id in call_args
    # assert json.dumps(mock_parsed_logs, indent=2) in call_args

    print("\n✅ Unit test for RootCauseAnalysisAgent.analyze passed successfully!")
