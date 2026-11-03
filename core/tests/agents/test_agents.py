"""
Agent Management Test Suite
============================

Tests for AI Agent CRUD operations, configuration management,
and lifecycle handling.

Test Coverage:
- Agent creation and validation
- Agent retrieval and listing
- Agent updates and configuration changes
- Agent status management (active/paused/archived)
- Agent ownership and access control
- API key generation and validation
- Tool configuration

Run with: pytest tests/test_agents.py -v --cov=agents
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.tests.conftest import (
    CustomAssertions,
    sample_admin_data,
    sample_agent_create_request,
    sample_agent_data,
    sample_user_data,
)

# ============================================================================
# MOCK AGENT SERVICE IMPLEMENTATION (for testing)
# ============================================================================


class MockAgentService:
    """
    Mock implementation of Agent Service for testing.

    In production, this would be app/services/agent.py
    This mock simulates all agent behaviors for isolated unit testing.
    """

    # Valid statuses
    VALID_STATUSES = {"active", "paused", "archived", "error"}

    # Valid models
    VALID_MODELS = {
        "gpt-4-turbo",
        "gpt-4o",
        "gpt-4o-mini",
        "claude-3-opus",
        "claude-3-sonnet",
        "claude-3-haiku",
        "gemini-pro",
        "gemini-ultra",
    }

    # Available tools
    AVAILABLE_TOOLS = {
        "web_search",
        "calculator",
        "code_interpreter",
        "file_manager",
        "sql_query",
        "api_client",
    }

    # Default configuration
    DEFAULT_CONFIG = {
        "temperature": 0.7,
        "max_tokens": 2048,
        "top_p": 0.9,
        "frequency_penalty": 0.5,
        "presence_penalty": 0.3,
    }

    def __init__(self):
        self.agents: dict[str, dict[str, Any]] = {}
        self._agent_counter = 0

    async def create_agent(
        self,
        name: str,
        owner_id: str,
        system_prompt: str,
        model: str = "gpt-4-turbo",
        description: str | None = None,
        configuration: dict[str, Any] | None = None,
        hitl_config: dict[str, Any] | None = None,
        tools: list[str] | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        """Create a new AI agent."""

        # Validate required fields
        if not name or not name.strip():
            raise ValueError("name is required")

        if not owner_id:
            raise ValueError("owner_id is required")

        if not system_prompt or not system_prompt.strip():
            raise ValueError("system_prompt is required")

        # Validate model
        if model not in self.VALID_MODELS:
            raise ValueError(f"Invalid model: {model}. Must be one of {self.VALID_MODELS}")

        # Validate status
        if status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}")

        # Validate tools
        if tools:
            for tool in tools:
                if tool not in self.AVAILABLE_TOOLS:
                    raise ValueError(f"Invalid tool: {tool}")

        # Merge with defaults
        final_config = {**self.DEFAULT_CONFIG, **(configuration or {})}

        # Generate API key hash (mock)
        api_key_hash = f"key-hash-{self._agent_counter}"

        # Create agent
        self._agent_counter += 1
        now = datetime.now(UTC)

        agent = {
            "id": str(uuid.uuid4()),
            "name": name.strip(),
            "description": description or "",
            "owner_id": owner_id,
            "system_prompt": system_prompt,
            "model": model,
            "configuration": final_config,
            "hitl_config": hitl_config or {},
            "tools": tools or [],
            "status": status,
            "api_key_hash": api_key_hash,
            "created_at": now,
            "updated_at": now,
            "statistics": {
                "total_conversations": 0,
                "total_messages": 0,
                "total_tokens": 0,
                "avg_response_time_ms": 0,
                "success_rate": 100.0,
            },
        }

        self.agents[agent["id"]] = agent

        return self._sanitize_agent(agent)

    async def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        """Get agent by ID."""
        agent = self.agents.get(agent_id)
        if agent:
            return self._sanitize_agent(agent)
        return None

    async def get_agents_by_owner(
        self, owner_id: str, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Get all agents owned by a user."""
        agents = [a for a in self.agents.values() if a["owner_id"] == owner_id]

        if status:
            agents = [a for a in agents if a["status"] == status]

        # Sort by created_at descending
        agents.sort(key=lambda x: x["created_at"], reverse=True)

        # Paginate
        paginated = agents[offset : offset + limit]

        return [self._sanitize_agent(a) for a in paginated]

    async def list_agents(
        self, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        """list all agents with pagination."""
        agents = list(self.agents.values())

        if status:
            agents = [a for a in agents if a["status"] == status]

        total = len(agents)

        # Sort by created_at descending
        agents.sort(key=lambda x: x["created_at"], reverse=True)

        # Paginate
        paginated = agents[offset : offset + limit]

        return {
            "data": [self._sanitize_agent(a) for a in paginated],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def update_agent(self, agent_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Update an existing agent."""

        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")

        agent = self.agents[agent_id]

        updatable_fields = {
            "name",
            "description",
            "system_prompt",
            "model",
            "configuration",
            "hitl_config",
            "tools",
            "status",
        }

        for field, value in updates.items():
            if field not in updatable_fields:
                raise ValueError(f"Cannot update field: {field}")

            # Validate specific fields
            if field == "model" and value not in self.VALID_MODELS:
                raise ValueError(f"Invalid model: {value}")

            if field == "status" and value not in self.VALID_STATUSES:
                raise ValueError(f"Invalid status: {value}")

            if field == "tools":
                for tool in value:
                    if tool not in self.AVAILABLE_TOOLS:
                        raise ValueError(f"Invalid tool: {tool}")

            if field == "configuration":
                # Merge with defaults
                value = {**self.DEFAULT_CONFIG, **value}

            agent[field] = value

        agent["updated_at"] = datetime.now(UTC)

        return self._sanitize_agent(agent)

    async def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent."""
        if agent_id not in self.agents:
            return False

        del self.agents[agent_id]
        return True

    async def change_status(self, agent_id: str, new_status: str) -> dict[str, Any]:
        """Change agent status."""
        if new_status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status: {new_status}")

        return await self.update_agent(agent_id, {"status": new_status})

    async def regenerate_api_key(self, agent_id: str) -> str:
        """Regenerate agent's API key."""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")

        import secrets

        new_key = f"sk-agent-{secrets.token_urlsafe(32)}"
        self.agents[agent_id]["api_key_hash"] = f"hash-{new_key}"

        return new_key

    async def validate_api_key(self, agent_id: str, api_key: str) -> bool:
        """Validate API key for agent."""
        if agent_id not in self.agents:
            return False

        # In production, would verify against hashed key
        return api_key.startswith("sk-agent-") if api_key else False

    async def update_statistics(self, agent_id: str, stats_update: dict[str, Any]) -> None:
        """Update agent statistics."""
        if agent_id not in self.agents:
            return

        stats = self.agents[agent_id]["statistics"]

        if "conversations" in stats_update:
            stats["total_conversations"] += stats_update["conversations"]

        if "messages" in stats_update:
            stats["total_messages"] += stats_update["messages"]

        if "tokens" in stats_update:
            stats["total_tokens"] += stats_update["tokens"]

        if "response_time_ms" in stats_update:
            # বাংলা মন্তব্য (ROOT-CAUSE FIX): আগে averaging formula
            # `total_conversations` কে "কতবার response_time আপডেট হয়েছে" হিসেবে
            # ধরে নিত। কিন্তু একটা call-এ conversations=10 পাঠালেও সেটা একটাই
            # response_time স্যাম্পল -- ফলে avg 1200/10=120 হয়ে যেত, প্রত্যাশিত
            # 1200 না। এখন response_time samples-এর নিজস্ব কাউন্টার দিয়ে ঠিকঠাক
            # running average রাখা হচ্ছে।
            sample_count = stats.get("_response_time_samples", 0)
            current_total = stats["avg_response_time_ms"] * sample_count
            new_total = current_total + stats_update["response_time_ms"]
            sample_count += 1
            stats["avg_response_time_ms"] = new_total / sample_count
            stats["_response_time_samples"] = sample_count

    @staticmethod
    def _sanitize_agent(agent: dict[str, Any]) -> dict[str, Any]:
        """Remove sensitive fields from agent object."""
        safe = {
            "id": agent["id"],
            "name": agent["name"],
            "description": agent.get("description", ""),
            "owner_id": agent["owner_id"],
            "system_prompt": agent["system_prompt"],
            "model": agent["model"],
            "configuration": agent["configuration"],
            "hitl_config": agent.get("hitl_config", {}),
            "tools": agent.get("tools", []),
            "status": agent["status"],
            "created_at": agent["created_at"].isoformat(),
            "updated_at": agent["updated_at"].isoformat(),
            "statistics": agent.get("statistics", {}),
        }
        return safe


# ============================================================================
# TEST FIXTURES SPECIFIC TO AGENTS
# ============================================================================


@pytest.fixture
def agent_service() -> MockAgentService:
    """Create fresh agent service instance for each test."""
    return MockAgentService()


@pytest.fixture
async def sample_agent(
    agent_service: MockAgentService, sample_user_data: dict[str, Any]
) -> dict[str, Any]:
    """Pre-created sample agent."""
    return await agent_service.create_agent(
        name="Research Assistant",
        owner_id=sample_user_data["id"],
        system_prompt="You are a helpful research assistant.",
        description="Helps with research tasks",
        model="gpt-4-turbo",
        tools=["web_search", "calculator"],
    )


# ============================================================================
# TEST CLASS: Agent Creation
# ============================================================================


class TestAgentCreation:
    """Tests for creating new agents."""

    @pytest.mark.unit
    @pytest.mark.critical
    @pytest.mark.asyncio
    async def test_create_valid_agent(
        self,
        agent_service: MockAgentService,
        sample_user_data: dict[str, Any],
        assertions: CustomAssertions,
    ):
        """Should successfully create valid agent."""
        agent = await agent_service.create_agent(
            name="Test Agent",
            owner_id=sample_user_data["id"],
            system_prompt="You are a test assistant.",
            model="gpt-4-turbo",
            description="A test agent",
            tools=["web_search"],
        )

        assert agent is not None
        assert "id" in agent
        assertions.assert_valid_uuid(agent["id"], version=4)
        assert agent["name"] == "Test Agent"
        assert agent["owner_id"] == sample_user_data["id"]
        assert agent["system_prompt"] == "You are a test assistant."
        assert agent["model"] == "gpt-4-turbo"
        assert agent["description"] == "A test agent"
        assert "web_search" in agent["tools"]
        assert agent["status"] == "active"
        assert "api_key_hash" not in agent  # Should be hidden

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_generates_unique_ids(
        self, agent_service: MockAgentService, sample_user_data: dict[str, Any]
    ):
        """Should generate unique IDs for each agent."""
        agents = []

        for i in range(10):
            agent = await agent_service.create_agent(
                name=f"Agent {i}",
                owner_id=sample_user_data["id"],
                system_prompt=f"You are agent {i}.",
            )
            agents.append(agent)

        ids = [a["id"] for a in agents]
        assert len(ids) == len(set(ids)), "All agent IDs should be unique"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_sets_timestamps(
        self, agent_service: MockAgentService, sample_user_data: dict[str, Any]
    ):
        """Should set created_at and updated_at timestamps."""
        before_create = datetime.now(UTC)

        agent = await agent_service.create_agent(
            name="Timestamp Test", owner_id=sample_user_data["id"], system_prompt="Test prompt"
        )

        after_create = datetime.now(UTC)

        created_at = datetime.fromisoformat(agent["created_at"])
        updated_at = datetime.fromisoformat(agent["updated_at"])

        assert before_create <= created_at <= after_create
        assert before_create <= updated_at <= after_create

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_with_default_configuration(
        self, agent_service: MockAgentService, sample_user_data: dict[str, Any]
    ):
        """Should use default configuration when none provided."""
        agent = await agent_service.create_agent(
            name="Default Config Test", owner_id=sample_user_data["id"], system_prompt="Test prompt"
        )

        config = agent["configuration"]
        assert "temperature" in config
        assert "max_tokens" in config
        assert config["temperature"] == 0.7
        assert config["max_tokens"] == 2048

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_with_custom_configuration(
        self, agent_service: MockAgentService, sample_user_data: dict[str, Any]
    ):
        """Should accept custom configuration."""
        custom_config = {
            "temperature": 0.3,
            "max_tokens": 4096,
            "top_p": 1.0,
        }

        agent = await agent_service.create_agent(
            name="Custom Config Test",
            owner_id=sample_user_data["id"],
            system_prompt="Test prompt",
            configuration=custom_config,
        )

        config = agent["configuration"]
        assert config["temperature"] == 0.3
        assert config["max_tokens"] == 4096
        assert config["top_p"] == 1.0
        # Non-specified should use default
        assert config["frequency_penalty"] == 0.5

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reject_missing_name(
        self, agent_service: MockAgentService, sample_user_data: dict[str, Any]
    ):
        """Should reject agent without name."""
        with pytest.raises(ValueError, match="name"):
            await agent_service.create_agent(
                name="", owner_id=sample_user_data["id"], system_prompt="Test prompt"
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reject_missing_owner_id(self, agent_service: MockAgentService):
        """Should reject agent without owner_id."""
        with pytest.raises(ValueError, match="owner_id"):
            await agent_service.create_agent(
                name="Test Agent", owner_id="", system_prompt="Test prompt"
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reject_missing_system_prompt(
        self, agent_service: MockAgentService, sample_user_data: dict[str, Any]
    ):
        """Should reject agent without system_prompt."""
        with pytest.raises(ValueError, match="system_prompt"):
            await agent_service.create_agent(
                name="Test Agent", owner_id=sample_user_data["id"], system_prompt=""
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reject_invalid_model(
        self, agent_service: MockAgentService, sample_user_data: dict[str, Any]
    ):
        """Should reject invalid model names."""
        with pytest.raises(ValueError, match="Invalid model"):
            await agent_service.create_agent(
                name="Test Agent",
                owner_id=sample_user_data["id"],
                system_prompt="Test prompt",
                model="invalid-model-name",
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reject_invalid_tool(
        self, agent_service: MockAgentService, sample_user_data: dict[str, Any]
    ):
        """Should reject invalid tool names."""
        with pytest.raises(ValueError, match="Invalid tool"):
            await agent_service.create_agent(
                name="Test Agent",
                owner_id=sample_user_data["id"],
                system_prompt="Test prompt",
                tools=["valid_tool", "invalid_tool_name"],
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_accept_all_valid_models(
        self, agent_service: MockAgentService, sample_user_data: dict[str, Any]
    ):
        """Should accept all valid model names."""
        for model in agent_service.VALID_MODELS:
            agent = await agent_service.create_agent(
                name=f"{model} Agent",
                owner_id=sample_user_data["id"],
                system_prompt=f"Using {model}",
                model=model,
            )
            assert agent["model"] == model

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_accept_all_valid_tools(
        self, agent_service: MockAgentService, sample_user_data: dict[str, Any]
    ):
        """Should accept all valid tool names."""
        agent = await agent_service.create_agent(
            name="All Tools Agent",
            owner_id=sample_user_data["id"],
            system_prompt="Using all tools",
            tools=list(agent_service.AVAILABLE_TOOLS),
        )

        assert set(agent["tools"]) == agent_service.AVAILABLE_TOOLS


# ============================================================================
# TEST CLASS: Agent Retrieval
# ============================================================================


class TestAgentRetrieval:
    """Tests for retrieving agents."""

    @pytest.mark.unit
    @pytest.mark.critical
    @pytest.mark.asyncio
    async def test_get_existing_agent(
        self, agent_service: MockAgentService, sample_agent: dict[str, Any]
    ):
        """Should retrieve existing agent by ID."""
        retrieved = await agent_service.get_agent(sample_agent["id"])

        assert retrieved is not None
        assert retrieved["id"] == sample_agent["id"]
        assert retrieved["name"] == sample_agent["name"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_nonexistent_agent(self, agent_service: MockAgentService):
        """Should return None for nonexistent agent."""
        retrieved = await agent_service.get_agent("nonexistent-id")

        assert retrieved is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_hides_sensitive_fields(
        self, agent_service: MockAgentService, sample_agent: dict[str, Any]
    ):
        """Should hide sensitive fields like API key hash."""
        retrieved = await agent_service.get_agent(sample_agent["id"])

        assert "api_key_hash" not in retrieved

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_all_agents(
        self, agent_service: MockAgentService, sample_user_data: dict[str, Any]
    ):
        """Should list all agents with pagination info."""
        # Create multiple agents
        for i in range(5):
            await agent_service.create_agent(
                name=f"list Agent {i}", owner_id=sample_user_data["id"], system_prompt=f"Prompt {i}"
            )

        result = await agent_service.list_agents()

        assert "data" in result
        assert "total" in result
        assert "limit" in result
        assert "offset" in result
        assert len(result["data"]) >= 5
        assert result["total"] >= 5

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_filters_by_status(
        self, agent_service: MockAgentService, sample_user_data: dict[str, Any]
    ):
        """Should filter agents by status when specified."""
        # Create agents with different statuses
        await agent_service.create_agent(
            name="Active Agent",
            owner_id=sample_user_data["id"],
            system_prompt="Active",
            status="active",
        )
        await agent_service.create_agent(
            name="Paused Agent",
            owner_id=sample_user_data["id"],
            system_prompt="Paused",
            status="paused",
        )

        active_result = await agent_service.list_agents(status="active")
        paused_result = await agent_service.list_agents(status="paused")

        for agent in active_result["data"]:
            assert agent["status"] == "active"

        for agent in paused_result["data"]:
            assert agent["status"] == "paused"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_respects_pagination(
        self, agent_service: MockAgentService, sample_user_data: dict[str, Any]
    ):
        """Should respect pagination parameters."""
        # Create more agents than limit
        for i in range(10):
            await agent_service.create_agent(
                name=f"Paged Agent {i}",
                owner_id=sample_user_data["id"],
                system_prompt=f"Prompt {i}",
            )

        # Get first page
        page1 = await agent_service.list_agents(limit=5, offset=0)
        assert len(page1["data"]) == 5

        # Get second page
        page2 = await agent_service.list_agents(limit=5, offset=5)
        assert len(page2["data"]) == 5

        # Pages should have different agents
        page1_ids = {a["id"] for a in page1["data"]}
        page2_ids = {a["id"] for a in page2["data"]}
        assert len(page1_ids & page2_ids) == 0  # No overlap

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_agents_by_owner(
        self,
        agent_service: MockAgentService,
        sample_user_data: dict[str, Any],
        sample_admin_data: dict[str, Any],
    ):
        """Should filter agents by owner ID."""
        # Create agents for different owners
        for i in range(3):
            await agent_service.create_agent(
                name=f"User Agent {i}",
                owner_id=sample_user_data["id"],
                system_prompt=f"User prompt {i}",
            )

        for i in range(2):
            await agent_service.create_agent(
                name=f"Admin Agent {i}",
                owner_id=sample_admin_data["id"],
                system_prompt=f"Admin prompt {i}",
            )

        user_agents = await agent_service.get_agents_by_owner(sample_user_data["id"])
        admin_agents = await agent_service.get_agents_by_owner(sample_admin_data["id"])

        assert len(user_agents) >= 3
        assert len(admin_agents) >= 2

        for agent in user_agents:
            assert agent["owner_id"] == sample_user_data["id"]

        for agent in admin_agents:
            assert agent["owner_id"] == sample_admin_data["id"]


# ============================================================================
# TEST CLASS: Agent Updates
# ============================================================================


class TestAgentUpdates:
    """Tests for updating agents."""

    @pytest.mark.unit
    @pytest.mark.critical
    @pytest.mark.asyncio
    async def test_update_name(self, agent_service: MockAgentService, sample_agent: dict[str, Any]):
        """Should update agent name."""
        updated = await agent_service.update_agent(
            agent_id=sample_agent["id"], updates={"name": "Updated Name"}
        )

        assert updated["name"] == "Updated Name"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_description(
        self, agent_service: MockAgentService, sample_agent: dict[str, Any]
    ):
        """Should update agent description."""
        updated = await agent_service.update_agent(
            agent_id=sample_agent["id"], updates={"description": "New description here"}
        )

        assert updated["description"] == "New description here"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_system_prompt(
        self, agent_service: MockAgentService, sample_agent: dict[str, Any]
    ):
        """Should update system prompt."""
        new_prompt = "You are now an advanced research assistant with enhanced capabilities."

        updated = await agent_service.update_agent(
            agent_id=sample_agent["id"], updates={"system_prompt": new_prompt}
        )

        assert updated["system_prompt"] == new_prompt

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_model(
        self, agent_service: MockAgentService, sample_agent: dict[str, Any]
    ):
        """Should update agent model."""
        updated = await agent_service.update_agent(
            agent_id=sample_agent["id"], updates={"model": "gpt-4o-mini"}
        )

        assert updated["model"] == "gpt-4o-mini"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_configuration(
        self, agent_service: MockAgentService, sample_agent: dict[str, Any]
    ):
        """Should merge custom configuration with defaults."""
        new_config = {"temperature": 0.2, "max_tokens": 3000}

        updated = await agent_service.update_agent(
            agent_id=sample_agent["id"], updates={"configuration": new_config}
        )

        config = updated["configuration"]
        assert config["temperature"] == 0.2
        assert config["max_tokens"] == 3000
        # Unchanged should keep default
        assert config["frequency_penalty"] == 0.5

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_tools(
        self, agent_service: MockAgentService, sample_agent: dict[str, Any]
    ):
        """Should update agent tools list."""
        new_tools = ["code_interpreter", "file_manager", "sql_query"]

        updated = await agent_service.update_agent(
            agent_id=sample_agent["id"], updates={"tools": new_tools}
        )

        assert set(updated["tools"]) == set(new_tools)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_sets_updated_at(
        self, agent_service: MockAgentService, sample_agent: dict[str, Any]
    ):
        """Should update the updated_at timestamp."""
        original_updated = sample_agent["updated_at"]

        # Small delay to ensure time difference
        await asyncio.sleep(0.01)

        updated = await agent_service.update_agent(
            agent_id=sample_agent["id"], updates={"name": "Timestamp Check"}
        )

        new_updated = datetime.fromisoformat(updated["updated_at"])
        original_dt = datetime.fromisoformat(original_updated)

        assert new_updated > original_dt

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reject_updating_protected_fields(
        self, agent_service: MockAgentService, sample_agent: dict[str, Any]
    ):
        """Should reject updating protected fields."""
        with pytest.raises(ValueError, match="Cannot update"):
            await agent_service.update_agent(
                agent_id=sample_agent["id"],
                updates={"id": "new-id"},  # Protected
            )

        with pytest.raises(ValueError, match="Cannot update"):
            await agent_service.update_agent(
                agent_id=sample_agent["id"],
                updates={"owner_id": "new-owner"},  # Protected
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reject_invalid_model_in_update(
        self, agent_service: MockAgentService, sample_agent: dict[str, Any]
    ):
        """Should reject invalid model during update."""
        with pytest.raises(ValueError, match="Invalid model"):
            await agent_service.update_agent(
                agent_id=sample_agent["id"], updates={"model": "invalid-model"}
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reject_nonexistent_agent_update(self, agent_service: MockAgentService):
        """Should reject updating nonexistent agent."""
        with pytest.raises(ValueError, match="not found"):
            await agent_service.update_agent(agent_id="nonexistent-id", updates={"name": "Name"})


# ============================================================================
# TEST CLASS: Agent Deletion
# ============================================================================


class TestAgentDeletion:
    """Tests for deleting agents."""

    @pytest.mark.unit
    @pytest.mark.critical
    @pytest.mark.asyncio
    async def test_delete_existing_agent(
        self, agent_service: MockAgentService, sample_agent: dict[str, Any]
    ):
        """Should successfully delete existing agent."""
        deleted = await agent_service.delete_agent(sample_agent["id"])

        assert deleted is True

        # Should no longer exist
        retrieved = await agent_service.get_agent(sample_agent["id"])
        assert retrieved is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_delete_nonexistent_agent(self, agent_service: MockAgentService):
        """Should return False for nonexistent agent."""
        deleted = await agent_service.delete_agent("nonexistent-id")

        assert deleted is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_deleted_agent_not_in_listings(
        self, agent_service: MockAgentService, sample_agent: dict[str, Any]
    ):
        """Deleted agent should not appear in listings."""
        # Verify it exists initially
        listed = await agent_service.list_agents()
        pre_delete_ids = {a["id"] for a in listed["data"]}
        assert sample_agent["id"] in pre_delete_ids

        # Delete it
        await agent_service.delete_agent(sample_agent["id"])

        # Verify it's gone from listings
        listed_after = await agent_service.list_agents()
        post_delete_ids = {a["id"] for a in listed_after["data"]}
        assert sample_agent["id"] not in post_delete_ids


# ============================================================================
# TEST CLASS: Status Management
# ============================================================================


class TestStatusManagement:
    """Tests for agent status lifecycle."""

    @pytest.mark.unit
    @pytest.mark.critical
    @pytest.mark.asyncio
    async def test_change_to_valid_statuses(
        self, agent_service: MockAgentService, sample_agent: dict[str, Any]
    ):
        """Should change to any valid status."""
        valid_statuses = ["active", "paused", "archived", "error"]

        for status in valid_statuses:
            updated = await agent_service.change_status(
                agent_id=sample_agent["id"], new_status=status
            )
            assert updated["status"] == status

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reject_invalid_status(
        self, agent_service: MockAgentService, sample_agent: dict[str, Any]
    ):
        """Should reject invalid status values."""
        with pytest.raises(ValueError, match="Invalid status"):
            await agent_service.change_status(
                agent_id=sample_agent["id"], new_status="invalid_status"
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_paused_agent_not_active(
        self, agent_service: MockAgentService, sample_agent: dict[str, Any]
    ):
        """Paused agent should have 'paused' status."""
        await agent_service.change_status(agent_id=sample_agent["id"], new_status="paused")

        agent = await agent_service.get_agent(sample_agent["id"])
        assert agent["status"] == "paused"


# ============================================================================
# TEST CLASS: API Key Management
# ============================================================================


class TestAPIKeyManagement:
    """Tests for API key generation and validation."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_regenerate_api_key(
        self, agent_service: MockAgentService, sample_agent: dict[str, Any]
    ):
        """Should generate new API key."""
        new_key = await agent_service.regenerate_api_key(sample_agent["id"])

        assert new_key is not None
        assert new_key.startswith("sk-agent-")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_regenerate_fails_for_nonexistent(self, agent_service: MockAgentService):
        """Should fail when regenerating for nonexistent agent."""
        with pytest.raises(ValueError, match="not found"):
            await agent_service.regenerate_api_key("nonexistent-id")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_validate_correct_api_key_format(
        self, agent_service: MockAgentService, sample_agent: dict[str, Any]
    ):
        """Should validate correctly formatted API keys."""
        valid_key = await agent_service.regenerate_api_key(sample_agent["id"])

        is_valid = await agent_service.validate_api_key(
            agent_id=sample_agent["id"], api_key=valid_key
        )

        assert is_valid is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reject_wrong_format_api_key(
        self, agent_service: MockAgentService, sample_agent: dict[str, Any]
    ):
        """Should reject incorrectly formatted API keys."""
        invalid_keys = [
            "",
            "wrong-format",
            "sk-other-prefix",
            "bearer token",
        ]

        for key in invalid_keys:
            is_valid = await agent_service.validate_api_key(
                agent_id=sample_agent["id"], api_key=key
            )
            assert is_valid is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reject_for_nonexistent_agent(self, agent_service: MockAgentService):
        """Should reject validation for nonexistent agent."""
        is_valid = await agent_service.validate_api_key(
            agent_id="nonexistent-id", api_key="sk-agent-validformat"
        )

        assert is_valid is False


# ============================================================================
# TEST CLASS: Statistics Tracking
# ============================================================================


class TestStatisticsTracking:
    """Tests for agent statistics tracking."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_initial_statistics(
        self, agent_service: MockAgentService, sample_agent: dict[str, Any]
    ):
        """Newly created agent should have zeroed statistics."""
        stats = sample_agent["statistics"]

        assert stats["total_conversations"] == 0
        assert stats["total_messages"] == 0
        assert stats["total_tokens"] == 0
        assert stats["avg_response_time_ms"] == 0
        assert stats["success_rate"] == 100.0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_statistics(
        self, agent_service: MockAgentService, sample_agent: dict[str, Any]
    ):
        """Should update statistics correctly."""
        await agent_service.update_statistics(
            agent_id=sample_agent["id"],
            stats_update={
                "conversations": 10,
                "messages": 150,
                "tokens": 25000,
                "response_time_ms": 1200,
            },
        )

        agent = await agent_service.get_agent(sample_agent["id"])
        stats = agent["statistics"]

        assert stats["total_conversations"] == 10
        assert stats["total_messages"] == 150
        assert stats["total_tokens"] == 25000
        assert stats["avg_response_time_ms"] == 1200

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cumulative_statistics_updates(
        self, agent_service: MockAgentService, sample_agent: dict[str, Any]
    ):
        """Statistics should accumulate over multiple updates."""
        # First batch
        await agent_service.update_statistics(
            agent_id=sample_agent["id"],
            stats_update={
                "conversations": 5,
                "messages": 50,
                "tokens": 5000,
            },
        )

        # Second batch
        await agent_service.update_statistics(
            agent_id=sample_agent["id"],
            stats_update={
                "conversations": 5,
                "messages": 50,
                "tokens": 5000,
            },
        )

        agent = await agent_service.get_agent(sample_agent["id"])
        stats = agent["statistics"]

        assert stats["total_conversations"] == 10
        assert stats["total_messages"] == 100
        assert stats["total_tokens"] == 10000


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=agents", "--cov-report=term-missing"])
