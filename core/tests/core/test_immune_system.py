from unittest.mock import MagicMock

import pytest

from core.resilience.auto_remediation import AutoRemediation
from core.rules_mutator import RulesMutator


@pytest.fixture
def mock_redis(monkeypatch):
    queue = MagicMock()
    queue.configured = True
    # Default return for GET is None
    queue.get.return_value = None
    queue.incr.return_value = 1

    from core import services

    monkeypatch.setattr(services, "redis_queue", queue, raising=True)
    return queue


import pytest


@pytest.mark.asyncio
async def test_auto_remediation_success(tmp_path):
    # Create a temporary file to test patch application
    test_file = tmp_path / "test_vuln.py"
    test_file.write_text("password = 'hardcoded_secrets'\n", encoding="utf-8")

    remediator = AutoRemediation(gemini_api_key="mock-key")

    from unittest.mock import patch

    async def mock_acompletion(*args, **kwargs):
        return {
            "text": "# Secure Patch Applied for: Hardcoded secret detected\npassword = os.getenv('DB_PASSWORD')"
        }

    submitted = []

    async def mock_submit(*args, **kwargs):
        submitted.append(args)
        return "submitted-remediation-123"

    with (
        patch("core.llm.llm_gateway.llm_gateway.acompletion", new=mock_acompletion),
        patch.object(remediator, "_validate_file_path", return_value=str(test_file)),
        # The self-heal pipeline (sandbox AST validation + approval queue) is
        # a separate concern; patch its submit boundary so this test verifies
        # the AutoRemediation flow only.
        patch(
            "core.health.self_healer.RemediationPipeline.submit",
            new=mock_submit,
        ),
    ):
        # tenant_id is now mandatory (tenant isolation guard in
        # process_security_alert) — omitting it yields success=False.
        res = await remediator.process_security_alert(
            file_path=str(test_file),
            line_number=1,
            issue="Hardcoded secret detected",
            severity="high",
            tenant_id="tenant-1",
        )

    assert res["success"] is True
    assert res["patch_applied"] is True
    assert res["branch"] == "supremeai-improvements"

    # The patch is applied asynchronously by the RemediationPipeline
    # (submit -> sandbox validation -> apply), so the local file is unchanged
    # here; verify the generated fix was submitted to the pipeline instead.
    assert len(submitted) == 1
    assert "Secure Patch Applied" in str(submitted[0])


def test_rules_mutator_blocks_ip(mock_redis):
    mutator = RulesMutator()
    ip = "192.168.1.50"

    # Mock redis check returns something when blocked
    mock_redis.get.return_value = "blocked:suspicious_activity"
    assert mutator.is_ip_blocked(ip) is True

    # Try blocking
    mock_redis.get.return_value = None
    res = mutator.block_ip(ip, reason="ddos_attempt")
    assert res is True
    mock_redis.set.assert_called_with(f"blocklist:ip:{ip}", "blocked:ddos_attempt", ex=1800)
