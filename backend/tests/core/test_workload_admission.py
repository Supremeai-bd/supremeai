"""Workload admission controller regression tests (#3156).

বাংলা: এই টেস্টগুলো নিশ্চিত করে যে workload amplification attack প্রতিরোধ
করা হয় — agent count, parallelism, prompt size, retry, queue depth সব
dimension-এ quota enforced।
"""

from __future__ import annotations

import os

import pytest

from core.security.workload_admission import (
    AdmissionRequest,
    AdmissionVerdict,
    WorkloadAdmissionController,
)


@pytest.fixture
def controller():
    return WorkloadAdmissionController()


class TestAgentCountQuota:
    """Agent count per user must not exceed configured max."""

    def test_within_agent_limit_allowed(self, controller):
        req = AdmissionRequest(user_id="u1", agent_count=3)
        result = controller.admit(req)
        assert result.verdict == AdmissionVerdict.ALLOW

    def test_at_exact_agent_limit_allowed(self, controller):
        req = AdmissionRequest(user_id="u1", agent_count=5)
        result = controller.admit(req)
        assert result.verdict == AdmissionVerdict.ALLOW

    def test_over_agent_limit_rejected(self, controller):
        req = AdmissionRequest(user_id="u1", agent_count=10)
        result = controller.admit(req)
        assert result.verdict == AdmissionVerdict.REJECT
        assert result.http_status == 422
        assert "agent_count=10 exceeds max=5" in result.reason


class TestParallelismQuota:
    """Parallel tasks per request must not exceed configured max."""

    def test_within_parallelism_allowed(self, controller):
        req = AdmissionRequest(user_id="u1", parallelism=5)
        result = controller.admit(req)
        assert result.verdict == AdmissionVerdict.ALLOW

    def test_over_parallelism_rejected(self, controller):
        req = AdmissionRequest(user_id="u1", parallelism=20)
        result = controller.admit(req)
        assert result.verdict == AdmissionVerdict.REJECT
        assert "parallelism=20 exceeds max=10" in result.reason


class TestPromptTokenQuota:
    """Prompt size must not exceed configured token max."""

    def test_small_prompt_allowed(self, controller):
        req = AdmissionRequest(user_id="u1", prompt_text="Hello world")
        result = controller.admit(req)
        assert result.verdict == AdmissionVerdict.ALLOW

    def test_huge_prompt_rejected(self, controller):
        # 200k chars ≈ 50k tokens > 32k max
        huge_prompt = "x" * 200_000
        req = AdmissionRequest(user_id="u1", prompt_text=huge_prompt)
        result = controller.admit(req)
        assert result.verdict == AdmissionVerdict.REJECT
        assert "prompt_tokens" in result.reason
        assert "exceeds max=32000" in result.reason

    def test_empty_prompt_allowed(self, controller):
        req = AdmissionRequest(user_id="u1", prompt_text="")
        result = controller.admit(req)
        assert result.verdict == AdmissionVerdict.ALLOW


class TestRetryAmplification:
    """Retry count must not exceed max (prevents retry-based amplification)."""

    def test_within_retry_limit_allowed(self, controller):
        req = AdmissionRequest(user_id="u1", retry_count=2)
        result = controller.admit(req)
        assert result.verdict == AdmissionVerdict.ALLOW

    def test_over_retry_limit_throttled(self, controller):
        req = AdmissionRequest(user_id="u1", retry_count=5)
        result = controller.admit(req)
        assert result.verdict == AdmissionVerdict.THROTTLE
        assert result.http_status == 429
        assert "retry_count=5 exceeds max=3" in result.reason
        assert "amplification" in result.reason


class TestQueueDepthBackpressure:
    """Queue depth must not exceed max (prevents queue replay)."""

    def test_within_queue_depth_allowed(self, controller):
        req = AdmissionRequest(user_id="u1", queue_depth=20)
        result = controller.admit(req)
        assert result.verdict == AdmissionVerdict.ALLOW

    def test_over_queue_depth_throttled(self, controller):
        req = AdmissionRequest(user_id="u1", queue_depth=100)
        result = controller.admit(req)
        assert result.verdict == AdmissionVerdict.THROTTLE
        assert result.http_status == 429
        assert "queue_depth=100 exceeds max=50" in result.reason
        assert "backpressure" in result.reason


class TestCombinedWorkload:
    """Combined agent_count × parallelism × prompt must pass ALL checks."""

    def test_combined_within_all_limits_allowed(self, controller):
        req = AdmissionRequest(
            user_id="u1",
            agent_count=3,
            parallelism=5,
            prompt_text="Do the task",
        )
        result = controller.admit(req)
        assert result.verdict == AdmissionVerdict.ALLOW

    def test_combined_first_failure_rejected(self, controller):
        # agent_count fails first (10 > 5) even if others are fine
        req = AdmissionRequest(
            user_id="u1",
            agent_count=10,
            parallelism=3,
            prompt_text="ok",
        )
        result = controller.admit(req)
        assert result.verdict == AdmissionVerdict.REJECT
        assert "agent_count" in result.reason

    def test_evidence_includes_all_dimensions(self, controller):
        req = AdmissionRequest(
            user_id="u1",
            tenant_id="t1",
            agent_count=2,
            parallelism=3,
            prompt_text="test prompt",
            retry_count=1,
            queue_depth=5,
        )
        result = controller.admit(req)
        assert result.verdict == AdmissionVerdict.ALLOW
        assert result.evidence["user_id"] == "u1"
        assert result.evidence["tenant_id"] == "t1"
        assert result.evidence["agent_count"] == 2
        assert result.evidence["parallelism"] == 3
        assert result.evidence["retry_count"] == 1
        assert result.evidence["queue_depth"] == 5
        assert "limits" in result.evidence
        assert result.evidence["prompt_tokens_estimated"] > 0


class TestConfigurableLimits:
    """Limits are configurable via env vars."""

    def test_env_override_agent_limit(self):
        # বাংলা: env var সেট করে reload করলে limit বদলায় — env-driven config।
        import importlib
        os.environ["WORKLOAD_MAX_AGENTS"] = "1"
        import core.security.workload_admission as mod
        importlib.reload(mod)
        assert mod.MAX_AGENTS_PER_USER == 1, "env override should set max to 1"
        req = mod.AdmissionRequest(user_id="u1", agent_count=2)
        ctrl = mod.WorkloadAdmissionController()
        result = ctrl.admit(req)
        assert result.verdict == mod.AdmissionVerdict.REJECT
        assert "max=1" in result.reason
        # cleanup
        del os.environ["WORKLOAD_MAX_AGENTS"]
        importlib.reload(mod)
