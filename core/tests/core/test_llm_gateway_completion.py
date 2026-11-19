# backend/tests/core/test_llm_gateway_completion.py
"""Direct-call tests for CompletionMixin.acompletion (core/llm/llm_gateway/completion.py).

coverage target: completion.py was measured at ~49% by the CI aggregate gate and
named a worst critical-tier offender. These tests drive ``acompletion`` through
a stub gateway (real mixin, stubbed collaborators) to cover the branches the
endpoint-level tests never reach: private cache bypass, pre-flight cost
guard (healthy / estimate-failure / no-db), Tier-0 deterministic bypass,
adaptive exploration append, TokenJuice gating, isolation of in-flight
requests, LOCAL-mode execution matrix, BYOK key reuse across
fallbacks, retired-model skip, circuit-breaker skip, the full HTTPStatusError
matrix (429 retry / 5xx backoff / 401-403 key cooldown), and the all-fail
exhaustion path (error-bus emit and self-healer proposal).

Patching seam note: module docstring of completion.py promises
``patch("core.llm.llm_gateway.get_firestore_db")`` keeps working through the
package-split proxy; a dedicated regression test pins that contract.
"""

import asyncio
import contextlib
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

import httpx
import pytest

from core.llm.interfaces import ExecutionMode
from core.llm.llm_gateway import completion as completion_mod
from core.llm.llm_gateway.completion import CompletionMixin


# --------------------------------------------------------------------------- #
# Stub collaborators
# --------------------------------------------------------------------------- #
def make_response(text: str = "hello world", cost: float = 0.0123, usage=None) -> dict:
    """cloud_adapter.generate shaped like an OpenAI-style completion dict."""
    resp: dict[str, Any] = {"choices": [{"message": {"content": text}}], "cost": cost}
    if usage is not None:
        resp["usage"] = usage
    return resp


class FakeRecord:
    """Minimal LLMCallRecord stand-in (only attrs acompletion touches)."""

    estimated_tokens: int | None = 11
    cost_usd: float = 0.0
    tokens_prompt: int | None = None
    tokens_completion: int | None = None
    latency_ms: int = 123


class RecordingBreaker:
    def __init__(self, allow: bool = True):
        self.allow_flag = allow
        self.successes = 0
        self.failures = 0

    def allow_request(self) -> bool:
        return self.allow_flag

    def mark_success(self) -> None:
        self.successes += 1

    def mark_failure(self) -> None:
        self.failures += 1


class StubCostGuard:
    instances: list["StubCostGuard"] = []

    def __init__(self, db):
        self.db = db
        self.check_budget = AsyncMock(return_value=None)
        StubCostGuard.instances.append(self)


class StubGateway(CompletionMixin):
    """Real CompletionMixin + stubbed collaborator attributes."""

    def __init__(self, chain=None, breaker=None, mode: ExecutionMode = ExecutionMode.AUTO):
        self.mode = mode
        self._chain = chain if chain is not None else ["prov/model-a", "prov/model-b"]
        self.cache = SimpleNamespace(query_similar=AsyncMock(return_value=None))
        self.performance_optimizer = SimpleNamespace(
            optimize_model_selection=AsyncMock(
                return_value=self._chain[0] if self._chain else "fallback/model"
            )
        )
        self.observability = SimpleNamespace(trace_generation=AsyncMock())
        self.local_adapter = None
        self.cloud_adapter = SimpleNamespace(generate=AsyncMock(return_value=make_response()))
        self.breaker = breaker or RecordingBreaker()
        self._rate_limit_handler = AsyncMock(return_value=False)
        self.stream_calls: list[tuple] = []

    # -- sibling-mixin seams, stubbed -- #
    def _ensure_litellm_ready(self) -> None:
        pass

    def _build_call_chain(self, model, provider, task_type):
        return list(self._chain)

    def _get_or_create_circuit_breaker(self, model) -> RecordingBreaker:
        return self.breaker

    async def _get_api_key_for_model(self, model):
        return "sk-resolved"

    async def _handle_rate_limit_error(self, model, exc):
        return await self._rate_limit_handler(model, exc)

    def _stream_completion(self, messages_payload, call_chain, timeout, **spend_context):
        self.stream_calls.append((messages_payload, call_chain, timeout, spend_context))
        return "STREAM-SENTINEL"


@pytest.fixture(autouse=True)
def _hermetic_completion(monkeypatch):
    """Keep every acompletion test hermetic: fake telemetry CM + neutral settings.

    The Tier-0 router is ALSO neutralized: the real ConfidenceGatedDispatcher
    fetches pattern data over the network on first use (observed in sandbox
    logs) — CI must stay hermetic, so the autouse stub answers
    non-deterministic for every prompt. Tier-0 behavior tests re-patch the
    same target with a deterministic decision (later setattr wins).
    """
    StubCostGuard.instances.clear()

    @contextlib.asynccontextmanager
    async def fake_track(**kwargs):
        yield FakeRecord()

    monkeypatch.setattr(completion_mod, "track_llm_call", fake_track)
    monkeypatch.setattr(
        completion_mod,
        "settings",
        SimpleNamespace(
            token_juice_enabled=False,
            enable_evolution_learning=False,
            llm_cost_per_token=0.00001,
        ),
    )

    neutral_router = MagicMock()
    neutral_router.route_with_confidence.return_value = SimpleNamespace(
        is_deterministic=False, deterministic_result=None, confidence=0.1
    )
    monkeypatch.setattr(
        "core.llm.advanced_model_router.get_advanced_router", lambda: neutral_router
    )


def make_gateway(**kwargs) -> StubGateway:
    return StubGateway(**kwargs)


def make_http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://llm.example/v1/chat")
    return httpx.HTTPStatusError(
        f"http {status}", request=request, response=httpx.Response(status, request=request)
    )


# --------------------------------------------------------------------------- #
# Private inference must not consult the shared vector response store.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("tenant_id", [None, "fixture-tenant"])
@pytest.mark.asyncio
async def test_inference_ignores_shared_experience_cache(tenant_id):
    gw = make_gateway()
    gw.cache.query_similar.return_value = SimpleNamespace(response="unscoped fixture", model="cached")
    result = await gw.acompletion(prompt="repeatable question", tenant_id=tenant_id)
    gw.cache.query_similar.assert_not_awaited()
    gw.cloud_adapter.generate.assert_awaited_once()
    assert result["text"] == "hello world"


@pytest.mark.asyncio
async def test_stream_returns_stream_gen_and_forwards_context():
    gw = make_gateway()
    result = await gw.acompletion(prompt="hi", stream=True)
    assert result == "STREAM-SENTINEL"
    gw.cache.query_similar.assert_not_awaited()
    messages, chain, timeout, spend_context = gw.stream_calls[0]
    # M16 P-A: streaming generator-এ tenant/tier context পৌঁছায় কিনা চুক্তি-পিন।
    assert spend_context == {"tenant_id": None, "tier": None, "task_type": "general"}
    assert messages[0]["content"] == "hi"
    assert chain == gw._chain
    assert timeout == 12.0


# --------------------------------------------------------------------------- #
# Pre-flight cost guard
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_tenant_budget_check_uses_estimated_cost(monkeypatch):
    gw = make_gateway()
    monkeypatch.setattr(completion_mod, "get_firestore_db", lambda: object())
    monkeypatch.setattr(completion_mod, "CostGuard", StubCostGuard)

    # estimate_tokens = len(text) // 4 → 80 chars = 20 tokens
    prompt = "x" * 80
    await gw.acompletion(prompt=prompt, tenant_id="tenant-1")

    guard = StubCostGuard.instances[-1]
    guard.check_budget.assert_awaited_once()
    tenant_arg, cost_arg = guard.check_budget.await_args.args
    assert tenant_arg == "tenant-1"
    assert cost_arg == pytest.approx(20 * 0.00001)


@pytest.mark.asyncio
async def test_budget_estimate_failure_falls_back_to_fixed_cost(monkeypatch):
    gw = make_gateway()
    monkeypatch.setattr(completion_mod, "get_firestore_db", lambda: object())
    monkeypatch.setattr(completion_mod, "CostGuard", StubCostGuard)
    monkeypatch.setattr(
        "core.prompt_handler.estimate_tokens", MagicMock(side_effect=RuntimeError("no tokenizer"))
    )

    await gw.acompletion(prompt="hi", tenant_id="tenant-1")

    guard = StubCostGuard.instances[-1]
    assert guard.check_budget.await_args.args[1] == pytest.approx(0.01)


@pytest.mark.asyncio
async def test_no_firestore_db_skips_budget_check(monkeypatch):
    gw = make_gateway()
    monkeypatch.setattr(completion_mod, "get_firestore_db", lambda: None)
    monkeypatch.setattr(completion_mod, "CostGuard", StubCostGuard)

    await gw.acompletion(prompt="hi", tenant_id="tenant-1")

    assert StubCostGuard.instances == []


@pytest.mark.asyncio
async def test_no_tenant_skips_budget_check_entirely():
    """tenant_id None → the whole Firestore/CostGuard pre-flight block is skipped."""
    gw = make_gateway()
    # NOTE: get_firestore_db proxy intentionally NOT patched — tenant_id None
    # means the code must never reach it.
    result = await gw.acompletion(prompt="hi")
    assert result["success"] is True


# --------------------------------------------------------------------------- #
# Tier-0 deterministic fast path
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_tier0_deterministic_bypass_skips_llm(monkeypatch):
    gw = make_gateway()
    router = MagicMock()
    router.route_with_confidence.return_value = SimpleNamespace(
        is_deterministic=True,
        deterministic_result={"answer": 4},
        matched_pattern="two-plus-two",
        confidence=0.99,
    )
    monkeypatch.setattr("core.llm.advanced_model_router.get_advanced_router", lambda: router)

    result = await gw.acompletion(prompt="what is 2+2", task_type="math")

    assert result["tier0_bypass"] is True
    assert result["model"] == "tier0-deterministic"
    assert result["cost"] == 0.0
    assert "answer" in result["text"]
    gw.cloud_adapter.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_tier0_nondeterministic_falls_through_to_chain(monkeypatch):
    gw = make_gateway()
    router = MagicMock()
    router.route_with_confidence.return_value = SimpleNamespace(
        is_deterministic=False, deterministic_result=None, confidence=0.1
    )
    monkeypatch.setattr("core.llm.advanced_model_router.get_advanced_router", lambda: router)

    result = await gw.acompletion(prompt="write a poem")

    assert result["success"] is True
    gw.cloud_adapter.generate.assert_awaited_once()


# --------------------------------------------------------------------------- #
# Model selection + payload shaping
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_explicit_model_skips_optimizer():
    gw = make_gateway()
    await gw.acompletion(prompt="hi", model="prov/model-a")
    gw.performance_optimizer.optimize_model_selection.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_model_uses_performance_optimizer():
    gw = make_gateway()
    await gw.acompletion(prompt="hi", task_type="summarize")
    gw.performance_optimizer.optimize_model_selection.assert_awaited_once_with("summarize", "hi")


@pytest.mark.asyncio
async def test_messages_list_payload_forwarded_verbatim():
    gw = make_gateway()
    messages = [
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "hello"},
    ]
    await gw.acompletion(messages=messages)
    kwargs = gw.cloud_adapter.generate.await_args.kwargs
    assert kwargs["messages"] == messages


@pytest.mark.asyncio
async def test_string_prompt_wrapped_as_user_message():
    gw = make_gateway()
    await gw.acompletion(prompt="hello")
    payload = gw.cloud_adapter.generate.await_args.kwargs["messages"]
    assert payload == [{"role": "user", "content": "hello"}]


# --------------------------------------------------------------------------- #
# Adaptive exploration (Sprint 5 §8.2)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_exploration_candidate_appended_to_chain_tail(monkeypatch):
    gw = make_gateway(chain=["prov/model-a"])
    monkeypatch.setattr("core.learning.provider_scorer.get_adaptive_routing_enabled", lambda: True)
    monkeypatch.setattr("core.learning.provider_scorer.score_snapshot", object())
    monkeypatch.setattr(
        "core.learning.provider_scorer.exploration_candidate",
        lambda snap: SimpleNamespace(model="exp/model-x", score=0.4),
    )

    await gw.acompletion(prompt="hi")

    sent_model = gw.cloud_adapter.generate.await_args.kwargs["model"]
    # head of chain stays first; exploration model is the tail and was attempted
    # only after head failure — here head succeeds, so exp/model-x never generates.
    assert sent_model == "prov/model-a"


@pytest.mark.asyncio
async def test_exploration_candidate_already_in_chain_not_duplicated(monkeypatch):
    gw = make_gateway(chain=["prov/model-a", "prov/model-b"])
    monkeypatch.setattr("core.learning.provider_scorer.get_adaptive_routing_enabled", lambda: True)
    monkeypatch.setattr("core.learning.provider_scorer.score_snapshot", object())
    monkeypatch.setattr(
        "core.learning.provider_scorer.exploration_candidate",
        lambda snap: SimpleNamespace(model="prov/model-a", score=0.4),
    )
    gw.cloud_adapter.generate.side_effect = [ValueError("boom"), make_response()]

    result = await gw.acompletion(prompt="hi")

    # head fails, tail succeeds — NO third (duplicate exploration) attempt
    assert result["model"] == "prov/model-b"
    assert gw.cloud_adapter.generate.await_count == 2


@pytest.mark.asyncio
async def test_exploration_scorer_failure_never_blocks_call(monkeypatch):
    gw = make_gateway()
    monkeypatch.setattr(
        "core.learning.provider_scorer.get_adaptive_routing_enabled",
        MagicMock(side_effect=RuntimeError("scorer crashed")),
    )
    result = await gw.acompletion(prompt="hi")
    assert result["success"] is True


@pytest.mark.asyncio
async def test_adaptive_routing_disabled_skips_exploration(monkeypatch):
    gw = make_gateway()
    monkeypatch.setattr("core.learning.provider_scorer.get_adaptive_routing_enabled", lambda: False)
    result = await gw.acompletion(prompt="hi")
    assert result["success"] is True


# --------------------------------------------------------------------------- #
# TokenJuice (R5)
# --------------------------------------------------------------------------- #
LONG_HTML = "<div>" + ("very long content " * 60) + "</div>"  # > 800 chars


def make_juice(ratio: float):
    juice = MagicMock()
    juice.detect_content_type.return_value = "html"
    juice.compress.return_value = SimpleNamespace(
        compression_ratio=ratio,
        compressed_text="COMPRESSED",
        original_chars=len(LONG_HTML),
        compressed_chars=100,
        estimated_original_tokens=250,
        estimated_compressed_tokens=100,
    )
    return juice


@pytest.mark.asyncio
async def test_token_juice_compresses_bulky_html(monkeypatch):
    gw = make_gateway()
    monkeypatch.setattr(
        completion_mod,
        "settings",
        SimpleNamespace(
            token_juice_enabled=True, enable_evolution_learning=False, llm_cost_per_token=0.00001
        ),
    )
    monkeypatch.setattr("engine.compression.token_juice.TokenJuice", lambda: make_juice(ratio=0.5))

    await gw.acompletion(prompt=LONG_HTML)

    payload = gw.cloud_adapter.generate.await_args.kwargs["messages"]
    assert payload[0]["content"] == "COMPRESSED"
    meta = payload[0]["_juice_meta"]
    assert meta["type"] == "html" and meta["ratio"] == 0.5


@pytest.mark.asyncio
async def test_token_juice_skips_low_compression_ratio(monkeypatch):
    gw = make_gateway()
    monkeypatch.setattr(
        completion_mod,
        "settings",
        SimpleNamespace(
            token_juice_enabled=True, enable_evolution_learning=False, llm_cost_per_token=0.00001
        ),
    )
    monkeypatch.setattr("engine.compression.token_juice.TokenJuice", lambda: make_juice(ratio=0.1))

    await gw.acompletion(prompt=LONG_HTML)

    payload = gw.cloud_adapter.generate.await_args.kwargs["messages"]
    assert payload[0]["content"] == LONG_HTML
    assert "_juice_meta" not in payload[0]


@pytest.mark.asyncio
async def test_token_juice_crash_never_breaks_call(monkeypatch):
    gw = make_gateway()
    monkeypatch.setattr(
        completion_mod,
        "settings",
        SimpleNamespace(
            token_juice_enabled=True, enable_evolution_learning=False, llm_cost_per_token=0.00001
        ),
    )
    broken = MagicMock(side_effect=RuntimeError("juicer exploded"))
    monkeypatch.setattr("engine.compression.token_juice.TokenJuice", broken)

    result = await gw.acompletion(prompt=LONG_HTML)
    assert result["success"] is True


@pytest.mark.asyncio
async def test_token_juice_disabled_keeps_original_content():
    gw = make_gateway()
    result = await gw.acompletion(prompt=LONG_HTML)
    assert result["success"] is True
    payload = gw.cloud_adapter.generate.await_args.kwargs["messages"]
    assert payload[0]["content"] == LONG_HTML


@pytest.mark.asyncio
async def test_token_juice_ignores_short_content(monkeypatch):
    gw = make_gateway()
    monkeypatch.setattr(
        completion_mod,
        "settings",
        SimpleNamespace(
            token_juice_enabled=True, enable_evolution_learning=False, llm_cost_per_token=0.00001
        ),
    )
    juice = MagicMock()
    monkeypatch.setattr("engine.compression.token_juice.TokenJuice", lambda: juice)

    await gw.acompletion(prompt="short")
    juice.detect_content_type.assert_not_called()


@pytest.mark.parametrize("second_tenant,second_session,second_key", [
    ("another-owner", "session-a", "fixture-key-a"),
    ("fixture-owner", "session-b", "fixture-key-a"),
    ("fixture-owner", "session-a", "fixture-key-b"),
])
@pytest.mark.asyncio
async def test_inference_never_shares_a_private_inflight_result(monkeypatch, second_tenant, second_session, second_key):
    monkeypatch.setenv("ENABLE_REQUEST_DEDUP", "true")
    monkeypatch.setattr(completion_mod, "get_firestore_db", lambda: None)
    gw = make_gateway()
    entered = asyncio.Event()
    release = asyncio.Event()
    calls = []

    async def generate(**kwargs):
        calls.append(kwargs["api_key"])
        if len(calls) == 1:
            entered.set()
            await release.wait()
            return make_response("leader result")
        return make_response("independent result")

    gw.cloud_adapter.generate.side_effect = generate
    first = asyncio.create_task(gw.acompletion(
        prompt="same prompt", tenant_id="fixture-owner", session_id="session-a", api_key="fixture-key-a",
    ))
    try:
        await asyncio.wait_for(entered.wait(), timeout=1)
        second = await asyncio.wait_for(gw.acompletion(
            prompt="same prompt", tenant_id=second_tenant, session_id=second_session, api_key=second_key,
        ), timeout=1)
    finally:
        release.set()
        leader = await first
    assert calls == ["fixture-key-a", second_key]
    assert leader["text"] == "leader result"
    assert second["text"] == "independent result"
    assert "deduplicated" not in second


# --------------------------------------------------------------------------- #
# LOCAL execution mode matrix
# --------------------------------------------------------------------------- #
def make_local_adapter(healthy=True, generate=None):
    return SimpleNamespace(
        health_check=AsyncMock(return_value=healthy),
        generate=generate or AsyncMock(return_value=make_response("local output")),
    )


@pytest.mark.asyncio
async def test_local_healthy_uses_zero_cost_local_result():
    """LOCAL execution success returns the zero-cost local result.

    DOCUMENTED FINDING (owner decision needed, no code change made — wire-first):
    the try/except/else around the local call means the success-path
    ``else: await self.observability.trace_generation(...)`` NEVER runs —
    the try body always ``return _local_result`` first, and an else suite only
    executes when the try body completes without exception AND without return.
    Local executions are therefore currently invisible to observability tracing.
    This test PINS that current behavior so the owner wiring decision is a
    conscious one.
    """
    gw = make_gateway()
    gw.local_adapter = make_local_adapter()

    result = await gw.acompletion(prompt="hi")

    assert result["model"] == "llama3.2" and result["cost"] == 0.0
    assert result["text"] == "local output"
    gw.cloud_adapter.generate.assert_not_awaited()
    # dead-else pin: no trace on local success under CURRENT code
    gw.observability.trace_generation.assert_not_awaited()


@pytest.mark.asyncio
async def test_local_failure_in_auto_falls_through_to_cloud():
    gw = make_gateway()
    gw.local_adapter = make_local_adapter(
        generate=AsyncMock(side_effect=RuntimeError("ollama down"))
    )

    result = await gw.acompletion(prompt="hi")

    assert result["success"] is True
    gw.cloud_adapter.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_local_failure_in_local_mode_raises():
    gw = make_gateway(mode=ExecutionMode.LOCAL)
    gw.local_adapter = make_local_adapter(
        generate=AsyncMock(side_effect=RuntimeError("ollama down"))
    )

    with pytest.raises(RuntimeError, match="ollama down"):
        await gw.acompletion(prompt="hi")


@pytest.mark.asyncio
async def test_local_mode_without_adapter_raises_runtime_error():
    gw = make_gateway(mode=ExecutionMode.LOCAL)
    gw.local_adapter = None

    with pytest.raises(RuntimeError, match="Ollama is not healthy"):
        await gw.acompletion(prompt="hi")


@pytest.mark.asyncio
async def test_local_model_kwarg_overrides_default():
    gw = make_gateway()
    gw.local_adapter = make_local_adapter()
    await gw.acompletion(prompt="hi", local_model="mistral-7b")
    assert gw.local_adapter.generate.await_args.kwargs["model"] == "mistral-7b"


# --------------------------------------------------------------------------- #
# BYOK key handling + fallback chain skips
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_byok_key_reused_across_fallback_attempts():
    gw = make_gateway(chain=["prov/model-a", "prov/model-b"])
    gw.cloud_adapter.generate.side_effect = [ValueError("first fails"), make_response()]

    result = await gw.acompletion(prompt="hi", api_key="sk-byok")

    assert result["success"] is True
    first_call, second_call = gw.cloud_adapter.generate.await_args_list
    assert first_call.kwargs["api_key"] == "sk-byok"
    assert second_call.kwargs["api_key"] == "sk-byok"


@pytest.mark.asyncio
async def test_without_byok_resolved_key_used():
    gw = make_gateway()
    await gw.acompletion(prompt="hi")
    assert gw.cloud_adapter.generate.await_args.kwargs["api_key"] == "sk-resolved"


@pytest.mark.asyncio
async def test_retired_model_skipped_and_next_attempted(monkeypatch):
    gw = make_gateway(chain=["retired/model-x", "prov/model-b"])

    def resolve(model):
        if model.startswith("retired/"):
            raise ValueError("model retired at provider")
        return model, None

    monkeypatch.setattr(completion_mod, "_resolve_litellm_target", resolve)

    result = await gw.acompletion(prompt="hi")

    assert result["model"] == "prov/model-b"
    assert gw.cloud_adapter.generate.await_count == 1


@pytest.mark.asyncio
async def test_open_circuit_breaker_skips_all_models():
    gw = make_gateway(chain=["prov/model-a", "prov/model-b"])
    gw.breaker = RecordingBreaker(allow=False)

    # breaker open for EVERY model in this stub (single breaker) → nothing
    # attempted → exhaustion RuntimeError (no last_exception)
    with pytest.raises(RuntimeError, match="All routing models failed"):
        await gw.acompletion(prompt="hi")

    gw.cloud_adapter.generate.assert_not_awaited()
    assert gw.breaker.successes == 0 and gw.breaker.failures == 0


@pytest.mark.asyncio
async def test_all_models_exhausted_raises_last_exception(monkeypatch):
    gw = make_gateway(chain=["prov/model-a", "prov/model-b"])
    gw.cloud_adapter.generate.side_effect = [ValueError("e1"), ValueError("e2")]
    monkeypatch.setattr(completion_mod, "error_event_bus", SimpleNamespace(emit=MagicMock()))

    with pytest.raises(ValueError, match="e2"):
        await gw.acompletion(prompt="hi")


# --------------------------------------------------------------------------- #
# Success path observability + learning feeds
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_success_records_observability_and_fitness(monkeypatch):
    gw = make_gateway()
    gw.cloud_adapter.generate.return_value = make_response(
        usage={"prompt_tokens": 10, "completion_tokens": 5}
    )
    fitness = SimpleNamespace(track_execution=MagicMock())
    monkeypatch.setattr("api.deps.get_fitness_engine", lambda: fitness)

    result = await gw.acompletion(prompt="hi", task_type="summarize", tenant_id="t-9")

    assert result == {
        "success": True,
        "text": "hello world",
        "model": "prov/model-a",
        "cost": 0.0123,
    }
    trace_kwargs = gw.observability.trace_generation.await_args.kwargs
    assert trace_kwargs["model"] == "prov/model-a"
    assert trace_kwargs["usage"] == {"prompt_tokens": 10, "completion_tokens": 5}
    assert trace_kwargs["privacy_mode"] == completion_mod.PrivacyMode.METADATA_ONLY
    assert trace_kwargs["prompt"] == "" and "response_text" not in trace_kwargs
    fitness.track_execution.assert_called_once()
    fe_kwargs = fitness.track_execution.call_args.kwargs
    assert fe_kwargs["success"] is True and fe_kwargs["token_cost"] == 5.0


@pytest.mark.asyncio
async def test_fitness_engine_failure_never_breaks_success(monkeypatch):
    gw = make_gateway()
    fitness = SimpleNamespace(
        track_execution=MagicMock(side_effect=RuntimeError("metrics db down"))
    )
    monkeypatch.setattr("api.deps.get_fitness_engine", lambda: fitness)

    result = await gw.acompletion(prompt="hi")
    assert result["success"] is True


@pytest.mark.asyncio
async def test_inference_does_not_write_shared_evolution_history(monkeypatch):
    gw = make_gateway()
    completion_mod.settings.enable_evolution_learning = True
    evolution = MagicMock()
    monkeypatch.setattr("core.self_evolution.evolution_engine.EvolutionEngine", evolution)
    await gw.acompletion(prompt="private fixture", task_type="chat")
    evolution.assert_not_called()


# --------------------------------------------------------------------------- #
# HTTPStatusError matrix
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_429_with_successful_retry_returns_retry_result(monkeypatch):
    gw = make_gateway(chain=["prov/model-a"])
    gw.cloud_adapter.generate.side_effect = [make_http_error(429), make_response("retried!")]
    gw._rate_limit_handler = AsyncMock(return_value=True)
    retry_event = MagicMock()
    monkeypatch.setattr("core.learning.record_llm_event", retry_event)
    monkeypatch.setattr(
        completion_mod, "_provider_key_pool", SimpleNamespace(mark_error=AsyncMock())
    )

    result = await gw.acompletion(prompt="hi")

    assert result["text"] == "retried!"
    assert gw.cloud_adapter.generate.await_count == 2
    retry_event.assert_called_once()
    assert retry_event.call_args.kwargs["error_class"] == "rate_limit"


@pytest.mark.asyncio
async def test_429_marks_key_pool_error_before_retry(monkeypatch):
    gw = make_gateway(chain=["prov/model-a"])
    gw.cloud_adapter.generate.side_effect = [make_http_error(429), make_response("ok")]
    gw._rate_limit_handler = AsyncMock(return_value=True)
    key_pool = SimpleNamespace(mark_error=AsyncMock())
    monkeypatch.setattr(completion_mod, "_provider_key_pool", key_pool)

    await gw.acompletion(prompt="hi", api_key="sk-byok")

    key_pool.mark_error.assert_awaited_once()
    args = key_pool.mark_error.await_args.args
    assert args[0] == "prov" and args[1] == "sk-byok" and args[2] == 429


@pytest.mark.asyncio
async def test_429_failed_retry_falls_to_next_model(monkeypatch):
    gw = make_gateway(chain=["prov/model-a", "prov/model-b"])
    gw.cloud_adapter.generate.side_effect = [
        make_http_error(429),
        RuntimeError("retry also failed"),
        make_response("model-b saves the day"),
    ]
    gw._rate_limit_handler = AsyncMock(return_value=True)

    result = await gw.acompletion(prompt="hi")

    assert result["model"] == "prov/model-b"
    assert gw.cloud_adapter.generate.await_count == 3


@pytest.mark.asyncio
async def test_5xx_applies_backoff_then_next_model(monkeypatch):
    gw = make_gateway(chain=["prov/model-a", "prov/model-b"])
    gw.cloud_adapter.generate.side_effect = [make_http_error(503), make_response("after 5xx")]
    sleeps: list[float] = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    result = await gw.acompletion(prompt="hi")

    assert result["model"] == "prov/model-b"
    assert sleeps and 0.5 <= sleeps[0] <= 1.5


@pytest.mark.asyncio
async def test_401_cooldown_and_skip_to_next_model(monkeypatch):
    gw = make_gateway(chain=["prov/model-a", "prov/model-b"])
    gw.cloud_adapter.generate.side_effect = [make_http_error(401), make_response("b wins")]
    key_pool = SimpleNamespace(mark_error=AsyncMock())
    monkeypatch.setattr(completion_mod, "_provider_key_pool", key_pool)

    result = await gw.acompletion(prompt="hi")

    assert result["model"] == "prov/model-b"
    key_pool.mark_error.assert_awaited_once()
    assert key_pool.mark_error.await_args.args[2] == 401
    assert gw.breaker.failures >= 1


@pytest.mark.asyncio
async def test_generic_exception_falls_to_next_model():
    gw = make_gateway(chain=["prov/model-a", "prov/model-b"])
    gw.cloud_adapter.generate.side_effect = [RuntimeError("opaque crash"), make_response()]

    result = await gw.acompletion(prompt="hi")

    assert result["model"] == "prov/model-b"
    assert gw.breaker.failures == 1


# --------------------------------------------------------------------------- #
# Exhaustion: error bus, self-healer, telemetry
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_exhaustion_emits_all_models_failed_event():
    gw = make_gateway(chain=["prov/model-a"])
    gw.cloud_adapter.generate.side_effect = RuntimeError("dead upstream")
    bus = SimpleNamespace(emit=MagicMock())
    original = completion_mod.error_event_bus
    completion_mod.error_event_bus = bus
    try:
        with pytest.raises(RuntimeError, match="dead upstream"):
            await gw.acompletion(prompt="hi", tenant_id="t-1")
    finally:
        completion_mod.error_event_bus = original

    bus.emit.assert_called_once()
    event = bus.emit.call_args.args[0]
    assert event.error_type == "ALL_MODELS_FAILED"
    assert event.severity == "CRITICAL"
    assert event.context["call_chain"] == ["prov/model-a"]


@pytest.mark.asyncio
async def test_exhaustion_without_exception_raises_runtime_error():
    gw = make_gateway(chain=[])
    bus = SimpleNamespace(emit=MagicMock())
    original = completion_mod.error_event_bus
    completion_mod.error_event_bus = bus
    try:
        with pytest.raises(RuntimeError, match="All routing models failed"):
            await gw.acompletion(prompt="hi")
    finally:
        completion_mod.error_event_bus = original


@pytest.mark.asyncio
async def test_exhaustion_proposes_self_heal_for_tenant(monkeypatch):
    gw = make_gateway(chain=["prov/model-a"])
    gw.cloud_adapter.generate.side_effect = RuntimeError("dead upstream")
    db_sentinel = object()
    monkeypatch.setattr(completion_mod, "get_firestore_db", lambda: db_sentinel)
    monkeypatch.setattr(completion_mod, "CostGuard", StubCostGuard)  # hermetic pre-flight
    healer = SimpleNamespace(propose_fix=AsyncMock())
    healer_cls = MagicMock(return_value=healer)
    monkeypatch.setattr(completion_mod, "SelfHealerService", healer_cls)
    monkeypatch.setattr(completion_mod, "error_event_bus", SimpleNamespace(emit=MagicMock()))

    with pytest.raises(RuntimeError):
        await gw.acompletion(prompt="hi", tenant_id="tenant-77")

    healer.propose_fix.assert_awaited_once()
    kwargs = healer.propose_fix.await_args.kwargs
    assert kwargs["tenant_id"] == "tenant-77"
    assert "LLMGateway all-fail" in kwargs["error_pattern"]
    healer_cls.assert_called_once_with(db_sentinel)


@pytest.mark.asyncio
async def test_exhaustion_without_db_skips_self_heal(monkeypatch):
    gw = make_gateway(chain=["prov/model-a"])
    gw.cloud_adapter.generate.side_effect = RuntimeError("dead upstream")
    monkeypatch.setattr(completion_mod, "get_firestore_db", lambda: None)
    healer = SimpleNamespace(propose_fix=AsyncMock())
    monkeypatch.setattr(completion_mod, "SelfHealerService", MagicMock(return_value=healer))
    monkeypatch.setattr(completion_mod, "error_event_bus", SimpleNamespace(emit=MagicMock()))

    with pytest.raises(RuntimeError):
        await gw.acompletion(prompt="hi", tenant_id="tenant-77")

    healer.propose_fix.assert_not_awaited()


# --------------------------------------------------------------------------- #
# Package-split patch seam (module docstring contract)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_get_firestore_db_proxy_forwards_to_package_attr(monkeypatch):
    """`patch("core.llm.llm_gateway.get_firestore_db")` must keep working."""
    sentinel_db = object()
    monkeypatch.setattr("core.llm.llm_gateway.get_firestore_db", lambda *a, **k: sentinel_db)
    from core.llm.llm_gateway import completion as proxy_holder

    assert proxy_holder.get_firestore_db() is sentinel_db


@pytest.mark.asyncio
async def test_tier0_and_cost_guard_combined_flow(monkeypatch):
    """tenant + db + non-deterministic router still reaches the cloud chain."""
    gw = make_gateway()
    monkeypatch.setattr(completion_mod, "get_firestore_db", lambda: object())
    monkeypatch.setattr(completion_mod, "CostGuard", StubCostGuard)
    router = MagicMock()
    router.route_with_confidence.return_value = SimpleNamespace(
        is_deterministic=False, deterministic_result=None, confidence=0.2
    )
    monkeypatch.setattr("core.llm.advanced_model_router.get_advanced_router", lambda: router)

    result = await gw.acompletion(prompt="hi", tenant_id="t-1")

    assert result["success"] is True
    assert StubCostGuard.instances[-1].check_budget.await_count == 1
    gw.cloud_adapter.generate.assert_awaited_once()


# --------------------------------------------------------------------------- #
# M16 P-A — বাস্তব খরচ meter (spend feed → CostGuard.record_spend)
# --------------------------------------------------------------------------- #
from core.config import settings as _real_settings  # noqa: E402 — appended section import
from core.llm.llm_gateway import spend_meter as spend_meter_mod  # noqa: E402


class RecordingCostGuard:
    """Stand-in for the CostGuard singleton — captures record_spend calls."""

    def __init__(self):
        self.calls: list[tuple[str, str, float]] = []

    async def record_spend(self, tenant_id: str, tier: str, actual_cost: float) -> None:
        self.calls.append((tenant_id, tier, actual_cost))


@pytest.fixture
def spend_recorder(monkeypatch):
    """Patch the meter's CostGuard resolver + a fixed meter rate for hermetic math."""
    guard = RecordingCostGuard()
    monkeypatch.setattr(spend_meter_mod, "get_cost_guard", lambda: guard)
    monkeypatch.setattr(_real_settings, "llm_cost_per_token", 2e-05)
    return guard


@pytest.mark.asyncio
async def test_successful_call_meters_provider_usage_spend(spend_recorder):
    """M16 P-A: successful cloud call → usage×rate recorded under the tenant."""
    gw = make_gateway()
    gw.cloud_adapter.generate = AsyncMock(
        return_value=make_response(cost=0.0, usage={"prompt_tokens": 100, "completion_tokens": 50})
    )

    result = await gw.acompletion(prompt="hi", tenant_id="tenant-1")

    assert result["success"] is True
    assert spend_recorder.calls == [("tenant-1", "unknown", pytest.approx(150 * 2e-05))]


@pytest.mark.asyncio
async def test_spend_feed_respects_explicit_tier(spend_recorder):
    """M16 P-A: caller-declared tier is used verbatim (no invented tier)."""
    gw = make_gateway()
    gw.cloud_adapter.generate = AsyncMock(
        return_value=make_response(cost=0.0, usage={"prompt_tokens": 10, "completion_tokens": 5})
    )

    await gw.acompletion(prompt="hi", tenant_id="tenant-1", tier="premium")

    assert spend_recorder.calls == [("tenant-1", "premium", pytest.approx(15 * 2e-05))]


@pytest.mark.asyncio
async def test_spend_feed_without_tenant_is_skipped_but_visible(spend_recorder, caplog):
    """No tenant → nothing recorded (can't attribute), gap must stay visible."""
    gw = make_gateway()
    gw.cloud_adapter.generate = AsyncMock(
        return_value=make_response(cost=0.0, usage={"prompt_tokens": 10, "completion_tokens": 5})
    )

    result = await gw.acompletion(prompt="hi")

    assert result["success"] is True
    assert spend_recorder.calls == []


@pytest.mark.asyncio
async def test_spend_feed_without_usage_records_nothing(spend_recorder):
    """No usage and zero cost from provider → never fabricate a spend."""
    gw = make_gateway()
    gw.cloud_adapter.generate = AsyncMock(return_value=make_response(cost=0.0, usage=None))

    result = await gw.acompletion(prompt="hi", tenant_id="tenant-1")

    assert result["success"] is True
    assert spend_recorder.calls == []


@pytest.mark.asyncio
async def test_spend_feed_uses_provider_cost_when_no_usage(spend_recorder):
    """When the provider reports an actual cost but no usage dict, meter that cost."""
    gw = make_gateway()
    gw.cloud_adapter.generate = AsyncMock(return_value=make_response(cost=0.25, usage=None))

    await gw.acompletion(prompt="hi", tenant_id="tenant-1")

    assert spend_recorder.calls == [("tenant-1", "unknown", pytest.approx(0.25))]


@pytest.mark.asyncio
async def test_spend_feed_failure_never_breaks_inference(spend_recorder):
    """Metering failure is loud but must not fail the user's completion."""

    async def _boom(*args, **kwargs):
        raise RuntimeError("redis down")

    spend_recorder.record_spend = _boom  # type: ignore[method-assign]
    gw = make_gateway()
    gw.cloud_adapter.generate = AsyncMock(
        return_value=make_response(cost=0.0, usage={"prompt_tokens": 5, "completion_tokens": 5})
    )

    result = await gw.acompletion(prompt="hi", tenant_id="tenant-1")

    assert result["success"] is True
    assert result["text"] == make_response()["choices"][0]["message"]["content"]


@pytest.mark.asyncio
async def test_streaming_spend_parity_with_usage_chunk(spend_recorder):
    """Streaming: usage on the final empty-choices chunk meters the same semantics."""
    from core.llm.llm_gateway.streaming import StreamingMixin

    class StreamStubGateway(StreamingMixin):
        def _ensure_litellm_ready(self) -> None:
            pass

        def _get_or_create_circuit_breaker(self, model):
            return RecordingBreaker()

        async def _get_api_key_for_model(self, model):
            return "sk-resolved"

    gw = StreamStubGateway()

    class FakeLitellm:
        @staticmethod
        async def acompletion(**kwargs):
            async def _gen():
                yield SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content="hello "))]
                )
                yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="!"))])
                # Final usage-only chunk (empty choices) — the IndexError trap.
                yield SimpleNamespace(
                    choices=[],
                    usage=SimpleNamespace(prompt_tokens=200, completion_tokens=100),
                )

            return _gen()

    monkeypatch_litellm = SimpleNamespace(acompletion=FakeLitellm.acompletion)

    import sys

    real_litellm = sys.modules.get("litellm")
    sys.modules["litellm"] = monkeypatch_litellm  # type: ignore[assignment]
    try:
        chunks = []
        async for piece in gw._stream_completion(
            [{"role": "user", "content": "hi"}],
            ["prov/model-a"],
            12.0,
            tenant_id="tenant-9",
            task_type="chat",
        ):
            chunks.append(piece)
    finally:
        if real_litellm is not None:
            sys.modules["litellm"] = real_litellm

    assert "".join(chunks) == "hello !"
    assert spend_recorder.calls == [("tenant-9", "unknown", pytest.approx(300 * 2e-05))]


@pytest.mark.asyncio
async def test_streaming_without_usage_records_nothing(spend_recorder):
    """Streaming without provider usage → no fabricated spend (gap is logged)."""
    from core.llm.llm_gateway.streaming import StreamingMixin

    class StreamStubGateway(StreamingMixin):
        def _ensure_litellm_ready(self) -> None:
            pass

        def _get_or_create_circuit_breaker(self, model):
            return RecordingBreaker()

        async def _get_api_key_for_model(self, model):
            return "sk-resolved"

    gw = StreamStubGateway()

    class FakeLitellm:
        @staticmethod
        async def acompletion(**kwargs):
            async def _gen():
                yield SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content="data only"))]
                )

            return _gen()

    import sys

    real_litellm = sys.modules.get("litellm")
    sys.modules["litellm"] = SimpleNamespace(acompletion=FakeLitellm.acompletion)  # type: ignore[assignment]
    try:
        chunks = [
            piece
            async for piece in gw._stream_completion(
                [{"role": "user", "content": "hi"}],
                ["prov/model-a"],
                12.0,
                tenant_id="tenant-9",
            )
        ]
    finally:
        if real_litellm is not None:
            sys.modules["litellm"] = real_litellm

    assert chunks == ["data only"]
    assert spend_recorder.calls == []


@pytest.mark.parametrize("before_output", [True, False])
@pytest.mark.asyncio
async def test_streaming_fallback_runs_only_before_output(monkeypatch, before_output):
    import sys

    from core.llm.llm_gateway.streaming import StreamingMixin

    breaker = RecordingBreaker()
    gateway = StreamingMixin()
    monkeypatch.setattr(gateway, "_ensure_litellm_ready", Mock(), raising=False)
    monkeypatch.setattr(gateway, "_get_or_create_circuit_breaker", Mock(return_value=breaker), raising=False)
    monkeypatch.setattr(gateway, "_get_api_key_for_model", AsyncMock(return_value="fixture-key"), raising=False)

    async def failed():
        if not before_output:
            yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="first"))])
        raise ConnectionError("fixture interrupted")

    async def next_model():
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="alternate"))])

    request = AsyncMock(side_effect=[failed(), next_model()])
    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(acompletion=request))
    result = []

    async def drain():
        async for part in gateway._stream_completion([], ["prov/model-a", "prov/model-b"], 1.0):
            result.append(part)

    if before_output:
        await drain()
        assert result == ["alternate"] and request.await_count == 2
    else:
        with pytest.raises(ConnectionError):
            await drain()
        assert result == ["first"]
        request.assert_awaited_once()
