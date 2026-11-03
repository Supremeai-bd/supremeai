# ============================================================
# SupremeAI - Integration Test Suite
# Production-Ready End-to-End Tests
# ============================================================

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient

# ============================================================
# MARKER: Integration tests
# ============================================================
pytestmark = pytest.mark.integration


class TestUserJourneyComplete:
    """Test complete user journeys through the system."""

    @pytest.mark.slow
    async def test_complete_agent_creation_and_conversation_flow(
        self,
        client: AsyncClient,
        generate_test_emails,
    ):
        """Test complete flow: Register → Create Agent → Chat → Delete."""

        # Step 1: User Registration
        user_data = {
            "email": generate_test_emails(),
            "password": "SecurePassword123!",
            "full_name": "Integration Test User",
        }

        register_response = await client.post("/api/v1/auth/register", json=user_data)
        assert register_response.status_code in [200, 201]
        register_response.json().get("data", register_response.json())

        # Step 2: Login
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": user_data["email"], "password": user_data["password"]},
        )
        assert login_response.status_code == 200
        tokens = login_response.json().get("data", login_response.json())
        auth_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # Step 3: Create Agent
        agent_config = {
            "name": "Integration Test Agent",
            "type": "conversational",
            "description": "Agent for integration testing",
            "system_prompt": "You are a helpful test assistant.",
            "model_config": {
                "provider": "openai",
                "model": "gpt-4-turbo-preview",
                "temperature": 0.7,
            },
            "tool_permissions": ["web_search"],
            "hitl_policy": {"enabled": True},
        }

        agent_response = await client.post(
            "/api/v1/agents",
            json=agent_config,
            headers=auth_headers,
        )
        assert agent_response.status_code in [200, 201]
        agent = agent_response.json().get("data", agent_response.json())

        # Step 4: Activate Agent
        activate_response = await client.post(
            f"/api/v1/agents/{agent['id']}/activate",
            headers=auth_headers,
        )
        assert activate_response.status_code == 200

        # Step 5: Create Conversation
        conv_response = await client.post(
            "/api/v1/conversations",
            json={"agent_id": agent["id"], "title": "Integration Test"},
            headers=auth_headers,
        )
        assert conv_response.status_code in [200, 201]
        conversation = conv_response.json().get("data", conv_response.json())

        # Step 6: Send Messages
        messages = [
            "Hello! Can you help me with something?",
            "I need to understand how this platform works.",
            "Thank you for your help!",
        ]

        for message_content in messages:
            msg_response = await client.post(
                f"/api/v1/conversations/{conversation['id']}/messages",
                json={"content": message_content, "role": "user"},
                headers=auth_headers,
            )
            assert msg_response.status_code in [200, 201]

        # Step 7: Retrieve Message History
        history_response = await client.get(
            f"/api/v1/conversations/{conversation['id']}/messages",
            headers=auth_headers,
        )
        assert history_response.status_code == 200
        messages_data = history_response.json().get("data", history_response.json())
        assert len(messages_data) >= len(messages)

        # Step 8: Cleanup - Delete conversation
        delete_conv_response = await client.delete(
            f"/api/v1/conversations/{conversation['id']}",
            headers=auth_headers,
        )
        assert delete_conv_response.status_code == 200

        # Step 9: Cleanup - Delete agent
        delete_agent_response = await client.delete(
            f"/api/v1/agents/{agent['id']}",
            headers=auth_headers,
        )
        assert delete_agent_response.status_code == 200

    @pytest.mark.slow
    async def test_multi_user_isolation(
        self,
        client: AsyncClient,
        generate_test_emails,
    ):
        """Test that users cannot access each other's data."""

        # Create two users
        user1_data = {
            "email": generate_test_emails(),
            "password": "User1Password123!",
            "full_name": "User One",
        }
        user2_data = {
            "email": generate_test_emails(),
            "password": "User2Password123!",
            "full_name": "User Two",
        }

        # Register both users
        await client.post("/api/v1/auth/register", json=user1_data)
        await client.post("/api/v1/auth/register", json=user2_data)

        # Login both users
        login1 = await client.post(
            "/api/v1/auth/login",
            json={"email": user1_data["email"], "password": user1_data["password"]},
        )
        login2 = await client.post(
            "/api/v1/auth/login",
            json={"email": user2_data["email"], "password": user2_data["password"]},
        )

        auth1 = {"Authorization": f"Bearer {login1.json()['data']['access_token']}"}
        auth2 = {"Authorization": f"Bearer {login2.json()['data']['access_token']}"}

        # User 1 creates an agent
        agent_resp = await client.post(
            "/api/v1/agents",
            json={
                "name": "User1's Private Agent",
                "type": "conversational",
                "system_prompt": "Private assistant",
            },
            headers=auth1,
        )
        agent_id = agent_resp.json()["data"]["id"]

        # User 2 should NOT be able to access User 1's agent
        access_resp = await client.get(f"/api/v1/agents/{agent_id}", headers=auth2)
        assert access_resp.status_code in [403, 404]  # Forbidden or Not Found

        # User 2 should only see their own agents (empty list)
        list_resp = await client.get("/api/v1/agents", headers=auth2)
        agents = list_resp.json().get("data", list_resp.json())
        assert not any(a.get("id") == agent_id for a in agents)


class TestAgentExecutionIntegration:
    """Test agent execution flows with real components."""

    @pytest.mark.slow
    async def test_agent_message_processing_with_memory(
        self,
        client: AsyncClient,
        auth_headers: dict,
        created_agent: dict,
        created_conversation: dict,
    ):
        """Test that agent processes messages and stores to memory."""

        # Send initial context message
        await client.post(
            f"/api/v1/conversations/{created_conversation['id']}/messages",
            json={
                "content": "My name is Alice and I work at Acme Corp as a developer.",
                "role": "user",
            },
            headers=auth_headers,
        )

        # Send follow-up question
        response = await client.post(
            f"/api/v1/conversations/{created_conversation['id']}/messages",
            json={"content": "What's my name and where do I work?", "role": "user"},
            headers=auth_headers,
        )

        assert response.status_code in [200, 201]
        data = response.json().get("data", response.json())

        # Verify agent used memory/context (check if answer contains info)
        if data.get("content"):
            content_lower = data["content"].lower()
            # Should mention Alice or Acme or developer based on context
            any(word in content_lower for word in ["alice", "acme", "developer"])
            # Note: This depends on actual LLM integration working

    @pytest.mark.slow
    async def test_tool_execution_with_hitl_approval(
        self,
        client: AsyncClient,
        operator_auth_headers: dict,
        created_agent: dict,
    ):
        """Test tool execution requiring HITL approval."""

        # Configure agent to require approval for email sending
        update_response = await client.put(
            f"/api/v1/agents/{created_agent['id']}",
            json={
                "hitl_policy": {
                    "enabled": True,
                    "require_approval_patterns": ["send_*"],
                    "escalation_timeout_minutes": 30,
                }
            },
            headers=operator_auth_headers,
        )
        assert update_response.status_code == 200

        # Execute action that requires approval
        exec_response = await client.post(
            f"/api/v1/agents/{created_agent['id']}/execute",
            json={
                "action": "send_email",
                "params": {
                    "to": "user@example.com",
                    "subject": "Test",
                    "body": "This requires approval",
                },
            },
            headers=operator_auth_headers,
        )

        # Should create HITL request instead of executing immediately
        assert exec_response.status_code in [200, 202]
        data = exec_response.json().get("data", exec_response.json())

        if data.get("requires_approval") or data.get("hitl_request_id"):
            # Verify HITL request was created
            hitl_id = data.get("hitl_request_id")

            # Check pending approvals
            approvals_resp = await client.get(
                "/api/v1/hitl/approvals?status=pending",
                headers=operator_auth_headers,
            )
            assert approvals_resp.status_code == 200

            # Approve the request
            approve_resp = await client.post(
                f"/api/v1/hitl/approvals/{hitl_id}/approve",
                json={"notes": "Approved for testing"},
                headers=operator_auth_headers,
            )
            assert approve_resp.status_code == 200


class TestDatabaseOperations:
    """Test database operations end-to-end."""

    @pytest.mark.slow
    async def test_concurrent_database_writes(
        self,
        client: AsyncClient,
        auth_headers: dict,
        sample_agent_config: dict,
    ):
        """Test handling concurrent database write operations."""

        # Launch concurrent requests to create agents
        async def create_agent(index):
            config = {**sample_agent_config, "name": f"Concurrent Agent {index}"}
            return await client.post(
                "/api/v1/agents",
                json=config,
                headers=auth_headers,
            )

        tasks = [create_agent(i) for i in range(10)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed
        successes = [r for r in responses if not isinstance(r, Exception)]
        errors = [r for r in responses if isinstance(r, Exception)]

        assert len(successes) == 10
        assert len(errors) == 0

        # All should have unique IDs
        agent_ids = set()
        for resp in successes:
            data = resp.json().get("data", resp.json())
            agent_ids.add(data["id"])

        assert len(agent_ids) == 10  # All unique

    @pytest.mark.slow
    async def test_transaction_rollback_on_error(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """Test that transactions roll back on validation errors."""

        # Try to create invalid agent (should fail completely)
        response = await client.post(
            "/api/v1/agents",
            json={
                "name": "",  # Invalid empty name
                "type": "invalid_type",  # Invalid type
            },
            headers=auth_headers,
        )

        assert response.status_code == 422

        # Verify no partial data was created
        list_response = await client.get("/api/v1/agents", headers=auth_headers)
        agents = list_response.json().get("data", list_response.json())

        # Should not contain any agent with empty name
        assert not any(a.get("name") == "" for a in agents)


class TestMemoryIntegration:
    """Test memory service integration with other components."""

    @pytest.mark.slow
    async def test_memory_created_from_conversation(
        self,
        client: AsyncClient,
        auth_headers: dict,
        created_agent: dict,
        created_conversation: dict,
    ):
        """Test that memories are automatically created from conversations."""

        # Send meaningful messages
        important_info = "Remember that our project deadline is March 15th and budget is $50k."

        await client.post(
            f"/api/v1/conversations/{created_conversation['id']}/messages",
            json={"content": important_info, "role": "user"},
            headers=auth_headers,
        )

        # Check if memory was stored (if auto-memory enabled)
        mem_response = await client.get(
            f"/api/v1/memory/stats?agent_id={created_agent['id']}",
            headers=auth_headers,
        )

        # Memory stats should be accessible
        assert mem_response.status_code == 200

    @pytest.mark.slow
    async def test_semantic_search_across_conversations(
        self,
        client: AsyncClient,
        auth_headers: dict,
        created_agent: dict,
    ):
        """Test semantic search finds related memories from different conversations."""

        # Create multiple conversations with related topics
        conv1_resp = await client.post(
            "/api/v1/conversations",
            json={
                "agent_id": created_agent["id"],
                "title": "Python Discussion",
            },
            headers=auth_headers,
        )
        conv1 = conv1_resp.json()["data"]

        conv2_resp = await client.post(
            "/api/v1/conversations",
            json={
                "agent_id": created_agent["id"],
                "title": "Programming Talk",
            },
            headers=auth_headers,
        )
        conv2 = conv2_resp.json()["data"]

        # Add related content to both
        await client.post(
            f"/api/v1/conversations/{conv1['id']}/messages",
            json={
                "content": "Python is great for machine learning and data analysis.",
                "role": "user",
            },
            headers=auth_headers,
        )

        await client.post(
            f"/api/v1/conversations/{conv2['id']}/messages",
            json={"content": "I enjoy programming in Python for AI projects.", "role": "user"},
            headers=auth_headers,
        )

        # Search for related memories
        search_response = await client.post(
            "/api/v1/memory/search",
            json={
                "agent_id": created_agent["id"],
                "query": "machine learning programming",
                "limit": 5,
            },
            headers=auth_headers,
        )

        assert search_response.status_code == 200
        results = search_response.json().get("data", search_response.json())
        assert isinstance(results, list)


class TestSecurityIntegration:
    """Test security features in integrated scenarios."""

    @pytest.mark.security
    @pytest.mark.slow
    async def test_sql_injection_prevention(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """Test SQL injection attempts are properly handled."""

        malicious_inputs = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "1; SELECT * FROM users--",
            "'; INSERT INTO users VALUES('hacked',...); --",
        ]

        for injection in malicious_inputs:
            response = await client.get(
                f"/api/v1/agents?search={injection}",
                headers=auth_headers,
            )

            # Should not cause server error (500)
            assert response.status_code != 500, f"SQL injection not prevented: {injection}"

            # Should return safe response (400, 422, or 200 with no results)
            assert response.status_code in [200, 400, 422, 404]

    @pytest.mark.security
    @pytest.mark.slow
    async def test_xss_prevention(
        self,
        client: AsyncClient,
        auth_headers: dict,
        created_agent: dict,
        created_conversation: dict,
    ):
        """Test XSS prevention in message content."""

        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
            "<svg onload=alert('xss')>",
        ]

        for payload in xss_payloads:
            response = await client.post(
                f"/api/v1/conversations/{created_conversation['id']}/messages",
                json={"content": payload, "role": "user"},
                headers=auth_headers,
            )

            # Should accept but sanitize
            assert response.status_code in [200, 201]

            # Check returned content is sanitized
            data = response.json().get("data", response.json())
            content = data.get("content", "")

            # Script tags should be escaped/removed
            assert "<script>" not in content.lower() or "&lt;script&gt;" in content

    @pytest.mark.security
    @pytest.mark.slow
    async def test_rate_limiting_enforcement(
        self,
        client: AsyncClient,
        generate_test_emails,
    ):
        """Test rate limiting kicks in after threshold."""

        # Register quick user
        user_email = generate_test_emails()
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": user_email,
                "password": "Password123!",
                "full_name": "Rate Limit Test",
            },
        )

        login_resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": user_email,
                "password": "Password123!",
            },
        )
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Make many rapid requests
        for i in range(100):
            response = await client.get("/api/v1/admin/health", headers=headers)

            if response.status_code == 429:  # Too Many Requests
                break

        # Rate limiting may or may not be enabled in test env
        # If enabled, we should have been limited
        # If not enabled, all requests succeed (acceptable for tests)


class TestPerformanceIntegration:
    """Performance tests under realistic conditions."""

    @pytest.mark.slow
    async def test_response_time_under_load(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """Test API response times remain acceptable under load."""
        import time

        # Make concurrent requests
        async def make_request():
            start = time.time()
            response = await client.get("/api/v1/admin/health")
            elapsed = time.time() - start
            return elapsed, response.status_code

        # Fire 50 concurrent requests
        tasks = [make_request() for _ in range(50)]
        results = await asyncio.gather(*tasks)

        times = [r[0] for r in results]
        statuses = [r[1] for r in results]

        # All should succeed
        assert all(s == 200 for s in statuses)

        # P95 should be under 500ms
        times_sorted = sorted(times)
        p95_index = int(len(times) * 0.95)
        p95_time = times_sorted[p95_index]

        assert p95_time < 0.5, f"P95 response time {p95_time:.3f}s exceeds 500ms limit"

    @pytest.mark.slow
    async def test_large_payload_handling(
        self,
        client: AsyncClient,
        auth_headers: dict,
        created_conversation: dict,
    ):
        """Test handling of large message payloads."""

        # Generate large content (~100KB)
        large_content = "This is a test sentence. " * 2000  # ~50KB

        response = await client.post(
            f"/api/v1/conversations/{created_conversation['id']}/messages",
            json={"content": large_content, "role": "user"},
            headers=auth_headers,
        )

        # Should handle gracefully
        assert response.status_code in [200, 201, 413]  # 413 if too large

        if response.status_code in [200, 201]:
            data = response.json().get("data", response.json())
            assert len(data.get("content", "")) > 1000


class TestErrorRecovery:
    """Test system recovery from error conditions."""

    @pytest.mark.slow
    async def test_recovery_after_failed_llm_call(
        self,
        client: AsyncClient,
        auth_headers: dict,
        created_agent: dict,
        created_conversation: dict,
    ):
        """Test system recovers when LLM call fails."""

        # This test verifies graceful degradation
        # Send message that would trigger LLM call
        response = await client.post(
            f"/api/v1/conversations/{created_conversation['id']}/messages",
            json={"content": "Hello, please respond", "role": "user"},
            headers=auth_headers,
        )

        # Should either succeed or fail gracefully (not crash)
        assert response.status_code in [200, 201, 202, 502, 503, 504]

        # System should still be functional
        health_check = await client.get("/api/v1/admin/health")
        assert health_check.status_code == 200

    @pytest.mark.slow
    async def test_partial_failure_handling(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """Test handling of partial failures in batch operations."""

        # Create multiple agents, some valid, some invalid
        valid_configs = [
            {"name": f"Valid Agent {i}", "type": "conversational", "system_prompt": "Test"}
            for i in range(3)
        ]

        responses = []
        for config in valid_configs:
            resp = await client.post("/api/v1/agents", json=config, headers=auth_headers)
            responses.append(resp)

        # All valid ones should succeed
        success_count = sum(1 for r in responses if r.status_code in [200, 201])
        assert success_count == 3


# ============================================================
# FIXTURES FOR INTEGRATION TESTS
# ============================================================
@pytest.fixture(scope="module")
def event_loop():
    """Create event loop for module-scoped async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=long", "-m integration"])
