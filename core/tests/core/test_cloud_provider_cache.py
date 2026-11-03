"""Tests for PLAN-001: Anthropic prompt caching on the LiteLLM gateway.

Asserts (per plan Part 2 "How to do it" Change 4):
(a) when the routed model is Anthropic-family, the system prompt block carries
    `cache_control: {"type": "ephemeral"}` in the messages passed to
    litellm.acompletion (mocked — no network, no LLM call in CI);
(b) when the provider is Gemini/Groq/OpenAI, no `cache_control` is added and
    the messages list stays untouched;
(c) the returned usage dict surfaces `cache_read_input_tokens` /
    `cache_creation_input_tokens` when present in the LiteLLM response.

The litellm dependency is stubbed at the adapter boundary (`_get_litellm`),
so these tests never import or call the real LiteLLM client.
"""

from types import SimpleNamespace

import pytest

from core.llm.providers.cloud_adapter import (
    CloudProviderAdapter,
    _is_anthropic_family_model,
    _mark_anthropic_cache_blocks,
)

CLAUDE_MODEL = "anthropic/claude-3-5-sonnet-20241022"
GEMINI_MODEL = "gemini-1.5-flash"

SYSTEM_TEXT = "You are SupremeAI, a personalized autonomous coding assistant."


def _fake_response(cache_read=None, cache_creation=None):
    usage = SimpleNamespace(
        prompt_tokens=100,
        completion_tokens=20,
        total_tokens=120,
        cache_read_input_tokens=cache_read,
        cache_creation_input_tokens=cache_creation,
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(role="assistant", content="ok"))],
        usage=usage,
        model=CLAUDE_MODEL,
    )


class RecordingLiteLLM:
    """Captures the messages list handed to acompletion and returns a canned response."""

    def __init__(self, response):
        self.response = response
        self.captured = None

    async def acompletion(self, **kwargs):
        self.captured = kwargs
        return self.response


@pytest.fixture
def adapter(monkeypatch):
    a = CloudProviderAdapter()
    return a


def _wire(adapter, monkeypatch, response):
    stub = RecordingLiteLLM(response)
    monkeypatch.setattr(adapter, "_get_litellm", lambda: stub)
    return stub


# ---------------------------------------------------------------------------
# (a) Anthropic-family → cache_control markers present
# ---------------------------------------------------------------------------


async def test_anthropic_system_prompt_has_cache_control(adapter, monkeypatch):
    stub = _wire(adapter, monkeypatch, _fake_response())
    messages = [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "hello"},
    ]
    await adapter.generate(model=CLAUDE_MODEL, messages=messages)
    sent = stub.captured["messages"]
    system_block = sent[0]["content"]
    assert isinstance(system_block, list), "system content must be block-encoded for Anthropic"
    assert system_block[0]["type"] == "text"
    assert system_block[0]["text"] == SYSTEM_TEXT
    assert system_block[0]["cache_control"] == {"type": "ephemeral"}
    # Non-system messages pass through untouched.
    assert sent[1] == {"role": "user", "content": "hello"}


async def test_openrouter_anthropic_prefix_also_marked(adapter, monkeypatch):
    stub = _wire(adapter, monkeypatch, _fake_response())
    await adapter.generate(
        model="openrouter/anthropic/claude-3.5-sonnet",
        messages=[{"role": "system", "content": SYSTEM_TEXT}],
    )
    assert isinstance(stub.captured["messages"][0]["content"], list)


def test_mark_helper_is_pure_and_never_mutates_caller():
    original = [{"role": "system", "content": SYSTEM_TEXT}, {"role": "user", "content": "hi"}]
    snapshot = [dict(m) for m in original]
    out = _mark_anthropic_cache_blocks(original, model=CLAUDE_MODEL)
    assert original == snapshot, "caller's list must not be mutated"
    assert out[0]["content"][0]["cache_control"] == {"type": "ephemeral"}


def test_is_anthropic_family_detection_matrix():
    assert _is_anthropic_family_model("claude-3-opus")
    assert _is_anthropic_family_model("anthropic/claude-2")
    assert _is_anthropic_family_model("openrouter/anthropic/claude-3.5-sonnet")
    assert not _is_anthropic_family_model("gemini-1.5-flash")
    assert not _is_anthropic_family_model("groq/llama-3.3-70b-versatile")
    assert not _is_anthropic_family_model("gpt-4o-mini")
    assert not _is_anthropic_family_model(None)
    assert not _is_anthropic_family_model("")


# ---------------------------------------------------------------------------
# (b) Non-Anthropic → no cache_control leak
# ---------------------------------------------------------------------------


async def test_gemini_system_prompt_has_no_cache_control(adapter, monkeypatch):
    stub = _wire(adapter, monkeypatch, _fake_response())
    messages = [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "hello"},
    ]
    await adapter.generate(model=GEMINI_MODEL, messages=messages)
    sent = stub.captured["messages"]
    assert sent == messages, "non-Anthropic providers must receive the exact original messages"
    assert isinstance(sent[0]["content"], str)


async def test_groq_stream_path_has_no_cache_control(adapter, monkeypatch):
    async def _empty_stream(**kwargs):
        captured = kwargs
        # emulate: record and yield nothing
        RecordingLiteLLM.captured = captured
        return
        yield  # pragma: no cover — makes this an async generator

    class StreamStub:
        def __init__(self):
            self.captured = None

        async def acompletion(self, **kwargs):
            self.captured = kwargs
            return _empty_stream(**kwargs)

    stub = StreamStub()
    monkeypatch.setattr(adapter, "_get_litellm", lambda: stub)
    messages = [{"role": "system", "content": SYSTEM_TEXT}]
    async for _ in adapter.stream(model="groq/llama-3.3-70b-versatile", messages=messages):
        pass
    assert stub.captured["messages"] == messages


async def test_anthropic_stream_path_marks_prefix(adapter, monkeypatch):
    class StreamStub:
        def __init__(self):
            self.captured = None

        async def acompletion(self, **kwargs):
            self.captured = kwargs

            async def _gen():
                yield SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(role=None, content="hey"))],
                    model=CLAUDE_MODEL,
                )

            return _gen()

    stub = StreamStub()
    monkeypatch.setattr(adapter, "_get_litellm", lambda: stub)
    chunks = []
    async for chunk in adapter.stream(
        model=CLAUDE_MODEL, messages=[{"role": "system", "content": SYSTEM_TEXT}]
    ):
        chunks.append(chunk)
    assert len(chunks) == 1
    assert isinstance(stub.captured["messages"][0]["content"], list)


# ---------------------------------------------------------------------------
# (c) Usage cache metrics surfaced
# ---------------------------------------------------------------------------


async def test_usage_extracts_cache_metrics(adapter, monkeypatch):
    _wire(adapter, monkeypatch, _fake_response(cache_read=1200, cache_creation=350))
    result = await adapter.generate(
        model=CLAUDE_MODEL, messages=[{"role": "system", "content": SYSTEM_TEXT}]
    )
    assert result["usage"]["cache_read_input_tokens"] == 1200
    assert result["usage"]["cache_creation_input_tokens"] == 350
    assert result["usage"]["prompt_tokens"] == 100


async def test_usage_defaults_cache_metrics_to_zero_when_absent(adapter, monkeypatch):
    response = _fake_response()
    response.usage.cache_read_input_tokens = None
    response.usage.cache_creation_input_tokens = None
    _wire(adapter, monkeypatch, response)
    result = await adapter.generate(
        model=CLAUDE_MODEL, messages=[{"role": "system", "content": SYSTEM_TEXT}]
    )
    assert result["usage"]["cache_read_input_tokens"] == 0
    assert result["usage"]["cache_creation_input_tokens"] == 0


async def test_usage_cache_metrics_zero_for_non_anthropic(adapter, monkeypatch):
    _wire(adapter, monkeypatch, _fake_response())
    result = await adapter.generate(
        model=GEMINI_MODEL, messages=[{"role": "system", "content": SYSTEM_TEXT}]
    )
    assert result["usage"]["cache_read_input_tokens"] == 0
    assert result["usage"]["cache_creation_input_tokens"] == 0
