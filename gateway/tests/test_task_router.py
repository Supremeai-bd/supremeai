"""
Task Router Tests — Cost Guard Logic Coverage
v4.0: Ensures LLM cost guard works correctly in production

Tests cover:
  - Budget limit enforcement
  - Per-request cost tracking
  - Rate limiting per provider
  - Fallback behavior when budget exhausted
  - Admin override capabilities
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.skip(
    "Hallucinated config surface: budget_service and rate_limiter are not implemented in task router.",
    allow_module_level=True,
)


class TestCostGuardBudgetLimits:
    """Test budget enforcement logic."""

    @pytest.mark.unit
    async def test_budget_exceeded_returns_error(self, client, admin_headers):
        """When monthly budget exceeded, new tasks should be rejected."""
        from decimal import Decimal

        # Mock budget service to show exceeded budget
        with patch("api.routes.task_router.budget_service") as mock_budget:
            mock_budget.get_monthly_spend = AsyncMock(return_value=Decimal("100.00"))
            mock_budget.get_budget_limit = AsyncMock(return_value=Decimal("50.00"))
            mock_budget.is_budget_exceeded = AsyncMock(return_value=True)

            response = await client.post(
                "/api/v1/tasks",
                json={
                    "prompt": "Test task",
                    "model": "gemini-pro",
                },
                headers=admin_headers,
            )

            assert response.status_code == 402  # Payment Required
            assert "budget" in response.json()["detail"].lower()

    @pytest.mark.unit
    async def test_within_budget_allows_task(self, client, admin_headers):
        """When within budget, tasks proceed normally."""

        with patch("api.routes.task_router.budget_service") as mock_budget:
            mock_budget.is_budget_exceeded = AsyncMock(return_value=False)
            mock_budget.track_cost = AsyncMock()

            with patch("api.routes.task_router.task_queue") as mock_queue:
                mock_queue.enqueue = AsyncMock(return_value="task-123")

                response = await client.post(
                    "/api/v1/tasks",
                    json={
                        "prompt": "Test task within budget",
                        "model": "gemini-pro",
                    },
                    headers=admin_headers,
                )

                assert response.status_code == 201


class TestCostGuardRateLimiting:
    """Test per-provider rate limiting."""

    @pytest.mark.unit
    async def test_gemini_rate_limit_enforced(self, client, admin_headers):
        """Gemini RPM limit should be enforced."""
        with patch("api.routes.task_router.rate_limiter") as mock_rl:
            # Simulate rate limit hit
            mock_rl.is_rate_limited = AsyncMock(return_value=True)
            mock_rl.get_retry_after = MagicMock(return_value=60)

            response = await client.post(
                "/api/v1/tasks",
                json={"prompt": "Rate limited task", "model": "gemini-pro"},
                headers=admin_headers,
            )

            assert response.status_code == 429  # Too Many Requests
            assert "Retry-After" in response.headers

    @pytest.mark.unit
    async def test_groq_rate_limit_enforced(self, client, admin_headers):
        """Groq RPM limit should be enforced."""
        with patch("api.routes.task_router.rate_limiter") as mock_rl:
            mock_rl.is_rate_limited = AsyncMock(return_value=True)

            response = await client.post(
                "/api/v1/tasks",
                json={"prompt": "Groq rate limit test", "model": "llama-3"},
                headers=admin_headers,
            )

            assert response.status_code == 429


class TestCostGuardCostTracking:
    """Test accurate cost tracking per request."""

    @pytest.mark.unit
    async def test_cost_tracked_on_completion(self, client, admin_headers):
        """Cost should be tracked when task completes."""
        from decimal import Decimal

        with patch("api.routes.task_router.budget_service") as mock_budget:
            mock_budget.track_cost = AsyncMock()

            # Mock successful task execution
            with patch("api.routes.task_router.execute_task") as mock_exec:
                mock_exec.return_value = {
                    "id": "task-123",
                    "status": "completed",
                    "cost_usd": Decimal("0.002"),
                    "tokens_used": 150,
                }

                response = await client.post(
                    "/api/v1/tasks",
                    json={"prompt": "Track cost task"},
                    headers=admin_headers,
                )

                assert response.status_code == 201
                mock_budget.track_cost.assert_called_once()

    @pytest.mark.unit
    async def test_zero_cost_on_error(self, client, admin_headers):
        """No cost tracked when task fails."""
        with patch("api.routes.task_router.budget_service") as mock_budget:
            mock_budget.track_cost = AsyncMock()

            with patch("api.routes.task_router.execute_task") as mock_exec:
                mock_exec.side_effect = Exception("LLM Error")

                response = await client.post(
                    "/api/v1/tasks",
                    json={"prompt": "Error task"},
                    headers=admin_headers,
                )

                assert response.status_code == 500
                mock_budget.track_cost.assert_not_called()


class TestCostGuardAdminOverride:
    """Test admin can bypass certain limits."""

    @pytest.mark.unit
    async def test_admin_can_override_soft_limit(self, client, admin_headers):
        """Admin users can exceed soft limits but not hard limits."""

        with patch("api.routes.task_router.budget_service") as mock_budget:
            # Soft limit exceeded, hard limit not
            mock_budget.is_budget_exceeded = AsyncMock(return_value=False)
            mock_budget.is_soft_limit_exceeded = AsyncMock(return_value=True)
            mock_budget.is_hard_limit_exceeded = AsyncMock(return_value=False)

            response = await client.post(
                "/api/v1/tasks",
                json={"prompt": "Admin override task"},
                headers=admin_headers,
            )

            # Should succeed (soft limit allows admin)
            assert response.status_code in (200, 201)

    @pytest.mark.unit
    async def test_hard_limit_blocks_everyone(self, client, admin_headers):
        """Hard limit blocks even admins."""
        with patch("api.routes.task_router.budget_service") as mock_budget:
            mock_budget.is_hard_limit_exceeded = AsyncMock(return_value=True)

            response = await client.post(
                "/api/v1/tasks",
                json={"prompt": "Hard limit task"},
                headers=admin_headers,
            )

            assert response.status_code == 402
