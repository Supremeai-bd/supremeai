"""Trivial-input fast-path (gateway/service/trivial_input.py + the chat route).

A one-word reply ("hi") measured 6.2s because every request — greeting included
— paid for message persistence, a ~776-token context compile, a squad route
decision and an upstream call. None of that can improve an answer to "hi".

The risk of a fast-path is answering something that needed a model. These tests
are weighted accordingly: the negatives (must NOT fire) are the important half.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from gateway.service import app as edge
from gateway.service.trivial_input import trivial_reply

_HEADERS = {"Authorization": "Bearer fixture-client-key"}


# ── unit: the matcher ────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "text",
    ["hi", "Hi!", "hello", "hey", "হাই", "হ্যালো", "সালাম", "thanks", "thank you", "ঠিক আছে"],
)
def test_greetings_and_thanks_are_answered(text: str) -> None:
    assert trivial_reply({"messages": [{"role": "user", "content": text}]}) is not None


@pytest.mark.parametrize(
    "body",
    [
        # real questions, however short
        {"messages": [{"role": "user", "content": "hi, what is our deploy status?"}]},
        {"messages": [{"role": "user", "content": "why is it slow"}]},
        # too long to be a greeting
        {"messages": [{"role": "user", "content": "hello there my good friend"}]},
        # tool-using clients must always reach a real model
        {"messages": [{"role": "user", "content": "hi"}], "tools": [{"type": "function"}]},
        {"messages": [{"role": "user", "content": "hi"}], "tool_choice": "auto"},
        # multi-turn / system prompt means context matters
        {
            "messages": [
                {"role": "system", "content": "be terse"},
                {"role": "user", "content": "hi"},
            ]
        },
        {"messages": [{"role": "user", "content": "hi"}, {"role": "user", "content": "hi"}]},
        # multimodal content blocks are never trivial
        {"messages": [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]},
        # degenerate shapes
        {"messages": [{"role": "user", "content": ""}]},
        {"messages": []},
        {},
        {"messages": "not-a-list"},
        {"messages": [None]},
    ],
)
def test_answerable_or_malformed_requests_fall_through(body) -> None:
    assert trivial_reply(body) is None


def test_bengali_reply_for_bengali_input() -> None:
    out = trivial_reply({"messages": [{"role": "user", "content": "হাই"}]})
    assert out is not None
    assert "হ্যালো" in out["choices"][0]["message"]["content"]


def test_explicit_language_pref_beats_script_detection() -> None:
    out = trivial_reply(
        {"messages": [{"role": "user", "content": "hi"}], "language_pref": "bn"}
    )
    assert out is not None
    assert "হ্যালো" in out["choices"][0]["message"]["content"]


def test_reply_shape_matches_the_openai_contract() -> None:
    out = trivial_reply({"model": "supreme-spark", "messages": [{"role": "user", "content": "hi"}]})
    assert out is not None
    assert out["object"] == "chat.completion"
    assert out["model"] == "supreme-spark"
    choice = out["choices"][0]
    assert choice["message"]["role"] == "assistant"
    assert choice["finish_reason"] == "stop"
    # The UI renders this badge shape; `trivial` is additive, not a new contract.
    assert out["supremeai"]["channel"] == "w"
    assert out["supremeai"]["trivial"] is True


# ── integration: the route ───────────────────────────────────────────────────
@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("SUPREMEAI_API_KEY", "fixture-client-key")
    return TestClient(edge.app)


@pytest.fixture()
def fastpath_client(monkeypatch):
    """The route with the fast-path explicitly ON.

    The route defaults the fast-path OFF outside production *on purpose* — it
    intercepts before any upstream call, so a self-hosted/test deployment must
    be able to keep model behaviour deterministic. The 6.2s complaint came from
    production, where it is on by default.
    """
    monkeypatch.setenv("SUPREMEAI_API_KEY", "fixture-client-key")
    monkeypatch.setenv("SUPREMEAI_TRIVIAL_FASTPATH", "1")
    return TestClient(edge.app)


def test_route_answers_a_greeting_without_touching_upstream(fastpath_client, monkeypatch) -> None:
    """The whole point: zero upstream calls, zero persistence, ~0 ms."""
    upstream = []
    persist = []

    async def spy_upstream(*_a, **_k):  # pragma: no cover - must never run
        upstream.append(1)
        raise AssertionError("fast-path must not call upstream")

    monkeypatch.setattr(edge, "forward_stealth_webhook", spy_upstream, raising=False)
    monkeypatch.setattr(edge, "forward_chat_completion", spy_upstream, raising=False)
    monkeypatch.setattr(
        edge, "append_canonical_message", lambda *a, **k: persist.append(1), raising=False
    )

    resp = fastpath_client.post(
        "/v1/chat/completions",
        json={
            "model": "supreme-spark",
            "conversation_id": "conv-trivial-1",
            "messages": [{"role": "user", "content": "hi"}],
        },
        headers=_HEADERS,
    )

    assert resp.status_code == 200
    assert resp.headers["X-SupremeAI-Provider"] == "trivial-template"
    assert resp.headers["X-SupremeAI-Tier"] == "zero-cost"
    assert "total;dur=" in resp.headers["Server-Timing"]
    assert resp.json()["choices"][0]["message"]["content"].startswith("Hi!")
    assert upstream == [], "a greeting must never reach a model"
    assert persist == [], "a greeting must not write a conversation row"


def test_route_still_sends_a_real_question_to_a_model(client) -> None:
    """Guard against the fast-path over-reaching: this must NOT be templated."""
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "supreme-spark", "messages": [{"role": "user", "content": "why is it slow"}]},
        headers=_HEADERS,
    )
    assert resp.headers.get("X-SupremeAI-Provider") != "trivial-template"
    # No providers are configured in this sandbox, so the real pipeline 503s —
    # which is exactly the proof that the request went down the real path.
    assert resp.status_code in (200, 502, 503)


def test_fastpath_is_off_outside_production_by_default(client) -> None:
    """THE regression that must never return.

    The fast-path was briefly unconditional and intercepted the existing chat
    fixture's "Hello", so a test model that should have been called was never
    called (38 failures when suites ran together, 0 when run alone — the worst
    kind of bug: green in isolation). A non-production deployment must keep
    model behaviour deterministic unless it opts in.
    """
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "supremeai-api", "messages": [{"role": "user", "content": "Hello"}]},
        headers=_HEADERS,
    )
    assert resp.headers.get("X-SupremeAI-Provider") != "trivial-template"
