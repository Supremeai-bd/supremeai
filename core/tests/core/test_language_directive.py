"""M19 P-C — language-loop closure চুক্তি-টেস্ট।

বাংলা: preferred_language সংরক্ষিত হয়েও মডেলে পৌঁছাত না (খোলা লুপ) —
এখন system-directive block হিসেবে পৌঁছায়; পছন্দ-অনুপস্থিত/en → byte-সমতুল্য
আজকের আচরণ; read-ব্যর্থতা লাউড + non-fatal; kill-switch অক্ষত।
"""

from __future__ import annotations

import pytest

from context_engine import ContextEngine, Section
from core.i18n.language_directive import (
    build_language_directive,
    language_loop_enabled,
    resolve_preferred_language,
)

# ---------------------------------------------------------------------------
# directive builder
# ---------------------------------------------------------------------------


def test_no_directive_for_absent_or_english():
    # বাংলা: পছন্দ-অনুপস্থিত/en = আজকের আচরণ — directive নেই।
    for lang in (None, "", "en", "en-US", "English"):
        assert build_language_directive(lang) is None


def test_bengali_directive_present():
    for lang in ("bn", "bn-BD", "bangla", "bengali"):
        directive = build_language_directive(lang)
        assert directive is not None
        assert "Bengali" in directive and "বাংলা" in directive


def test_other_language_generic_directive():
    directive = build_language_directive("hi")
    assert directive is not None and "(hi)" in directive


# ---------------------------------------------------------------------------
# kill-switch
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("raw", "expected"), [("off", False), ("on", True), ("", True)])
def test_language_loop_kill_switch(monkeypatch: pytest.MonkeyPatch, raw: str, expected: bool):
    monkeypatch.setenv("SUPREMEAI_LANGUAGE_LOOP", raw)
    assert language_loop_enabled() is expected


def test_language_loop_unknown_fail_closed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SUPREMEAI_LANGUAGE_LOOP", "maybe")
    assert language_loop_enabled() is False


# ---------------------------------------------------------------------------
# preference resolution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_absent_user_returns_none():
    assert await resolve_preferred_language(None) is None
    assert await resolve_preferred_language("") is None


@pytest.mark.asyncio
async def test_resolve_read_failure_loud_nonfatal(monkeypatch: pytest.MonkeyPatch):
    # বাংলা: store-ব্যর্থতায় directive-বিহীন চলমানতা — ক্র্যাশ নয়, ভান নয়।
    import database.supabase_client as supa

    class _Boom:
        client = property(lambda self: object())

    class _BrokenClient:
        def table(self, name):
            raise RuntimeError("store down")

    monkeypatch.setattr(supa, "db", type("DB", (), {"client": _BrokenClient()})())
    assert await resolve_preferred_language("u1") is None


@pytest.mark.asyncio
async def test_directive_flows_through_context_engine():
    # বাংলা: directive SYSTEM block হিসেবে assemble-এ টিকে থাকে (M07 চুক্তি)।
    directive = build_language_directive("bn")
    assert directive is not None
    from context_engine import ContextBlock

    blocks = [
        ContextBlock(section=Section.SYSTEM, text=directive, priority=0, block_id="lang-directive"),
        ContextBlock(section=Section.USER, text="hello", priority=0, block_id="user"),
    ]
    result = ContextEngine().assemble(blocks, max_input_tokens=2000)
    assert directive in result.prompt
