"""External Agents control plane (issue #1572 Part 3)."""

from external_agents.control.job_api import AgentJob, ExternalAgentJobAPI
from external_agents.control.state_manager import (
    AgentStateManager,
    InvalidTransitionError,
    TaskRecord,
)

__all__ = [
    "AgentJob",
    "AgentStateManager",
    "ExternalAgentJobAPI",
    "InvalidTransitionError",
    "TaskRecord",
]
