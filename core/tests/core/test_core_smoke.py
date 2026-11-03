from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_setup_logging_runs():
    from core.logging_config import setup_logging

    # Should not raise
    setup_logging()


def test_config_validators_basic():
    from core.config import Settings

    s = Settings(env="test")
    # Default CORS origins are localhost dev URLs (127.0.0.1 is not in the
    # default set; the cors_origins property is env-driven, not a field).
    assert "localhost" in " ".join(s.cors_origins)  # is_local()
    # ensure debug remains a bool
    assert isinstance(s.debug, bool)


@pytest.mark.anyio
async def test_llm_gateway_acompletion_monkeypatched(monkeypatch, tmp_path):
    """Smoke test: LLMGateway.acompletion returns success when cloud_adapter.generate
    is mocked. Patches cloud_adapter.generate directly (the internal API the gateway
    uses) instead of litellm.acompletion, which is only called inside CloudProviderAdapter
    and not directly reachable from this layer.

    Also stubs sys.modules['litellm'] so the test runs in environments where
    litellm is not installed (e.g. minimal CI matrix or local dev without ml deps).
    """
    import sys
    import types

    # Minimal litellm stub — just enough to satisfy the lazy `import litellm`
    # inside acompletion(). The actual call goes through cloud_adapter.generate
    # which we replace on the instance below.
    _litellm_stub = types.ModuleType("litellm")
    _litellm_stub.acompletion = AsyncMock()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "litellm", _litellm_stub)

    # Minimal response dict matching what cloud_adapter.generate returns to the
    # gateway's completion loop (see completion.py ~line 420 onward).
    async def fake_generate(*args, **kwargs):
        return {
            "choices": [{"message": {"content": "mocked-response", "role": "assistant"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "model": "test-model",
            "cost": 0.001,
        }

    from core.llm.llm_gateway import LLMGateway

    with patch(
        "core.cache.semantic_cache.SemanticCache.query_similar",
        new=AsyncMock(return_value=None),
    ):
        gateway = LLMGateway()
        # Patch cloud_adapter.generate directly on the instance so we bypass
        # API-key lookup, routing-chain exhaustion, and litellm import overhead.
        gateway.cloud_adapter.generate = fake_generate  # type: ignore[method-assign]
        # Mark litellm as already set up to skip _ensure_litellm_ready() overhead.
        gateway._litellm_ready = True
        # Isolate circuit breaker from earlier test runs that might have tripped global breaker
        fake_cb = MagicMock()
        fake_cb.allow_request.return_value = True
        gateway._get_or_create_circuit_breaker = lambda *args, **kwargs: fake_cb  # type: ignore[method-assign]
        monkeypatch.setattr(
            gateway, "_build_call_chain", lambda *a, **kw: ["test-provider/test-model"]
        )
        res = await gateway.acompletion(prompt="hi")
        assert res["success"] is True
        assert res["text"] == "mocked-response"
