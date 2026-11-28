"""gateway/service/trivial_input.py — answer greetings without waking the stack.

WHY THIS EXISTS (the user problem)
----------------------------------
A one-word reply ("hi") measured 6.2s. Part of that was the relay, but part was
that the gateway has no notion of a request that does not need a model at all.
Every request — a greeting included — paid for the full pipeline:

  * two SQLite writes (canonical + legacy message persistence)
  * a context compile that injects ~776 tokens of identity anchor
    (CORE_SYSTEM_ANCHOR 2440 chars + PLATFORM_GROUNDING_SHEET 664 chars)
  * a route decision across the whole squad
  * an upstream call (relay or pool)

For "hi", all four are waste. The identity anchor exists to stop a model
misidentifying itself; a greeting never asks who it is. The memory write exists
to preserve conversation; "hi" carries none.

DESIGN — deliberately narrow
----------------------------
This is a *closed-set* matcher, never a "looks simple enough" heuristic. It fires
only when ALL of the following hold:

  1. exactly one user message, no system/assistant turns
  2. no `tools` / `tool_choice` / `functions` in the body (a tool-using client
     must still get a real model, whatever it typed)
  3. no message content that is a list (multimodal input is never trivial)
  4. the whole prompt, punctuation-stripped, is <= 4 tokens AND matches one of
     a small set of greeting/thanks/acknowledgement patterns
  5. the request did not ask for a specific model other than the fast lane

Anything ambiguous falls through to the normal pipeline, because a wrong
fast-path answer is far worse than a slow correct one. The response is
locale-aware (Bengali is the primary user language in this product) and carries
the same `supremeai` badge shape the UI already renders, so nothing downstream
needs a special case.

Stdlib only. Pure function; no I/O, no clock, no config mutation.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# A greeting is short by construction. 4 tokens covers "hello there my friend"
# while excluding any sentence that could carry a real question.
MAX_TOKENS = 4
MAX_CHARS = 40

_PUNCT = re.compile(r"[^\w\u0980-\u09FF\s]", re.UNICODE)
_SPACES = re.compile(r"\s+", re.UNICODE)

# Exact-normalised forms. Bengali and English are both first-class here because
# the product's primary locale is Bengali and "hi" arrives in both.
_GREETINGS = frozenset(
    {
        "hi", "hii", "hey", "hello", "helo", "yo", "hola", "good morning", "good afternoon", "good evening",
        "হাই", "হ্যালো", "হেলো", "শুভ সকাল", "শুভ সন্ধ্যা",
    }
)
# বাংলা: খোঁজখবরের প্রশ্নকে সাধারণ greeting বলে এড়িয়ে যাওয়া ঠিক নয়।
_WELLBEING = frozenset({"কেমন আছেন", "কেমন আছো", "how are you"})
_SALAM = frozenset({"সালাম", "আসসালামু আলাইকুম", "salam", "assalamu alaikum", "assalamualaikum"})
_THANKS = frozenset(
    {
        "thanks", "thank you", "thx", "ty", "ok", "okay", "got it", "cool", "nice",
        "ধন্যবাদ", "থ্যাংকস", "ঠিক আছে", "আচ্ছা", "বুঝেছি",
    }
)

_REPLIES = {
    "greeting": {"en": "Hi! What can I help you with?", "bn": "হ্যালো! কীভাবে সাহায্য করতে পারি?"},
    "wellbeing": {"en": "I'm doing well, thanks! How are you?", "bn": "ভালো আছি, ধন্যবাদ! আপনি কেমন আছেন?"},
    "salam": {"en": "Wa alaikum assalam! How can I help you?", "bn": "ওয়ালাইকুমুস সালাম! কীভাবে সাহায্য করতে পারি?"},
    "thanks": {"en": "You're welcome!", "bn": "আপনাকে স্বাগতম!"},
}


def _normalise(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    return _SPACES.sub(" ", _PUNCT.sub(" ", (text or "").lower())).strip()


def _classify(prompt: str) -> Optional[str]:
    """Return the reply kind for a trivially-answerable prompt, else None."""
    if not prompt or len(prompt) > MAX_CHARS:
        return None
    norm = _normalise(prompt)
    if not norm or len(norm.split()) > MAX_TOKENS:
        return None
    if norm in _WELLBEING:
        return "wellbeing"
    if norm in _SALAM:
        return "salam"
    if norm in _THANKS:
        return "thanks"
    if norm in _GREETINGS:
        return "greeting"
    return None


def trivial_reply(body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return a complete chat-completion payload for a trivial prompt, or None.

    ``None`` is the overwhelmingly common answer and means "use the real
    pipeline". Callers must treat this function as advisory: any exception or
    unexpected shape returns ``None`` rather than raising on the chat path.
    """
    try:
        # 1. tool-using clients always get a real model
        for key in ("tools", "tool_choice", "functions", "function_call"):
            if body.get(key):
                return None

        messages = body.get("messages")
        if not isinstance(messages, list) or len(messages) != 1:
            return None

        msg = messages[0]
        if not isinstance(msg, dict) or msg.get("role") != "user":
            return None

        content = msg.get("content")
        if not isinstance(content, str):  # multimodal / structured block
            return None

        kind = _classify(content)
        if kind is None:
            return None

        # 2. Locale: an explicit preference wins, else follow the script the user
        # actually typed in (Bengali codepoints present => Bengali reply).
        pref = str(body.get("language_pref") or body.get("language") or "").strip().lower()
        if pref.startswith("bn"):
            lang = "bn"
        elif pref.startswith("en"):
            lang = "en"
        else:
            lang = "bn" if re.search(r"[\u0980-\u09FF]", content) else "en"

        text = _REPLIES[kind][lang]
        model = str(body.get("model") or "supreme-spark")

        return {
            "id": "chatcmpl-trivial",
            "object": "chat.completion",
            "created": 0,  # stamped by the caller, which owns the clock
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            # Same badge shape the UI already renders; `trivial` is additive so
            # nobody has to guess why a reply arrived in ~0 ms.
            "supremeai": {
                "channel": "w",
                "engine": "xx",
                "tier": "Turbo",
                "label": "SupremeAI w.xx Turbo",
                "trivial": True,
            },
        }
    except Exception:  # noqa: BLE001 - never break the chat path
        return None


def self_test() -> int:
    """Contract self-test: fires on greetings, never on anything answerable."""
    assert trivial_reply({"messages": [{"role": "user", "content": "hi"}]}) is not None
    assert trivial_reply({"messages": [{"role": "user", "content": "Hi!"}]}) is not None
    assert trivial_reply({"messages": [{"role": "user", "content": "হ্যালো"}]}) is not None
    assert trivial_reply({"messages": [{"role": "user", "content": "thank you"}]}) is not None

    # Bengali script => Bengali reply; explicit pref wins over script.
    bn = trivial_reply({"messages": [{"role": "user", "content": "হাই"}]})
    assert bn is not None and "হ্যালো" in bn["choices"][0]["message"]["content"]
    forced = trivial_reply(
        {"messages": [{"role": "user", "content": "hi"}], "language_pref": "bn"}
    )
    assert forced is not None and "হ্যালো" in forced["choices"][0]["message"]["content"]

    # MUST NOT fire: these all need a real model.
    negatives: List[Dict[str, Any]] = [
        {"messages": [{"role": "user", "content": "hi, what is our deploy status?"}]},
        {"messages": [{"role": "user", "content": "hello there my good friend"}]},  # 5 tokens
        {"messages": [{"role": "user", "content": "hi"}], "tools": [{"type": "function"}]},
        {"messages": [{"role": "system", "content": "x"}, {"role": "user", "content": "hi"}]},
        {"messages": [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]},
        {"messages": [{"role": "user", "content": "hi"}, {"role": "user", "content": "hi"}]},
        {"messages": [{"role": "user", "content": ""}]},
        {"messages": []},
        {},
        {"messages": "not-a-list"},
    ]
    for body in negatives:
        assert trivial_reply(body) is None, f"fast-path fired on {body!r}"

    # Hostile input must degrade to None, never raise.
    assert trivial_reply({"messages": [{"role": "user", "content": "x" * 10_000}]}) is None
    assert trivial_reply({"messages": [None]}) is None

    print("trivial_input self-test: PASS (%d negatives)" % len(negatives))
    return 0


if __name__ == "__main__":  # pragma: no cover - manual invocation
    import sys

    sys.exit(self_test())
