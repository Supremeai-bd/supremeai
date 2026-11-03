"""Context Engine (M2, ERR-F03) — unit tests.

Pins the smallest-sufficient-context contract:
- token estimation sanity (ASCII + Bengali-heavy text);
- budget resolution per provider (from PROVIDER_TOKEN_BUDGETS) + default;
- assembly: everything fits → nothing dropped, deterministic order;
- over-budget: low-priority knowledge dropped first, history by recency,
  user message ALWAYS present, report reflects drops;
- tiny budget: user message hard-truncated with the truncation marker,
  system capped at its section cap;
- determinism: same input → identical prompt (stable sort).
"""

from __future__ import annotations

import pytest

from context_engine import (
    DEFAULT_INPUT_BUDGET,
    ContextBlock,
    ContextEngine,
    Section,
    estimate_tokens,
    resolve_input_budget,
)
from context_engine.engine import _TRUNCATION_MARK


def test_estimate_tokens_ascii_and_bengali():
    assert estimate_tokens("") == 0
    ascii_text = "a" * 400  # ~100 tokens
    assert 90 <= estimate_tokens(ascii_text) <= 110
    bengali_text = "বাংলা" * 100  # 400 non-ascii chars → safety factor applies
    assert estimate_tokens(bengali_text) > estimate_tokens("a" * 400)


def test_resolve_budget_provider_and_default():
    assert resolve_input_budget("gemini") == 6_000  # from PROVIDER_TOKEN_BUDGETS
    assert resolve_input_budget("unknown-provider") == DEFAULT_INPUT_BUDGET
    assert resolve_input_budget(None) == DEFAULT_INPUT_BUDGET


def test_assemble_keeps_everything_when_it_fits():
    engine = ContextEngine()
    blocks = [
        ContextBlock(Section.SYSTEM, "Be helpful.", 0, "sys"),
        ContextBlock(Section.MEMORY, "User prefers Bengali.", 0, "mem1"),
        ContextBlock(Section.KNOWLEDGE, "- fact one", 0, "kb0"),
        ContextBlock(Section.USER, "What is Supabase?", 0, "user"),
    ]
    out = engine.assemble(blocks, max_input_tokens=2_000)
    assert out.report.fits
    assert out.report.dropped == []
    assert "What is Supabase?" in out.prompt
    assert "[System Knowledge Base]" in out.prompt
    assert "[Relevant Memory Context]" in out.prompt
    # Final order: system → memory → knowledge → user
    assert out.prompt.index("Be helpful.") < out.prompt.index("User prefers")
    assert out.prompt.index("User prefers") < out.prompt.index("fact one")
    assert out.prompt.index("fact one") < out.prompt.index("What is Supabase?")


def test_over_budget_drops_lowest_priority_knowledge_first():
    engine = ContextEngine()
    big_kb = "\n".join(f"- knowledge chunk {i} " + "x" * 200 for i in range(12))
    blocks = [
        ContextBlock(Section.SYSTEM, "sys", 0, "sys"),
        ContextBlock(Section.KNOWLEDGE, "- vital fact", 0, "kb-vital"),
        ContextBlock(Section.KNOWLEDGE, big_kb, 11, "kb-bulk"),
        ContextBlock(Section.USER, "question", 0, "user"),
    ]
    out = engine.assemble(blocks, max_input_tokens=400)
    assert "question" in out.prompt  # user NEVER dropped
    assert "vital fact" in out.prompt  # high priority kept
    assert "kb-bulk" in out.report.dropped  # low priority dropped
    assert out.report.fits


def test_history_filled_by_recency_then_size():
    engine = ContextEngine()
    blocks = [
        ContextBlock(Section.HISTORY, "old turn " + "y" * 800, 5, "h-old"),  # ≈202 tok > cap
        ContextBlock(Section.HISTORY, "recent turn " + "y" * 50, 0, "h-new"),
        ContextBlock(Section.USER, "q", 0, "user"),
    ]
    out = engine.assemble(blocks, max_input_tokens=200)
    assert "recent turn" in out.prompt
    assert "h-old" in out.report.dropped  # exceeds the 75% history section cap


def test_tiny_budget_truncates_user_message_with_marker():
    engine = ContextEngine()
    huge_question = "word " * 4_000  # ≈ 1000 tokens > half of 300 budget
    blocks = [ContextBlock(Section.USER, huge_question, 0, "user")]
    out = engine.assemble(blocks, max_input_tokens=300)
    assert _TRUNCATION_MARK in out.prompt
    assert "user" in out.report.truncated_sections
    assert out.report.fits


def test_system_capped_at_section_cap():
    engine = ContextEngine()
    huge_system = "rule " * 2_000  # ≈ 500 tokens > 25% of 300 = 75 tokens
    blocks = [
        ContextBlock(Section.SYSTEM, huge_system, 0, "sys"),
        ContextBlock(Section.USER, "q", 0, "user"),
    ]
    out = engine.assemble(blocks, max_input_tokens=300)
    assert "system" in out.report.truncated_sections
    assert out.report.section_tokens["system"] <= 300 * 0.25 + 1  # +1 for marker
    assert "q" in out.prompt


def test_deterministic_assembly():
    engine = ContextEngine()

    def build():
        return [
            ContextBlock(Section.MEMORY, "m1", 1, "m1"),
            ContextBlock(Section.MEMORY, "m2", 0, "m2"),
            ContextBlock(Section.KNOWLEDGE, "k1", 0, "k1"),
            ContextBlock(Section.USER, "u", 0, "u"),
        ]

    a = engine.assemble(build(), max_input_tokens=1_000)
    b = engine.assemble(build(), max_input_tokens=1_000)
    assert a.prompt == b.prompt
    assert a.report.dropped == b.report.dropped


def test_best_fit_keeps_smaller_later_blocks():
    """A big low-priority block must not block smaller later blocks (best-fit)."""
    engine = ContextEngine()
    blocks = [
        ContextBlock(Section.KNOWLEDGE, "k-huge " + "z" * 1400, 0, "kb-huge"),  # ≈352 tok > cap
        ContextBlock(Section.KNOWLEDGE, "k-tiny", 1, "kb-tiny"),
        ContextBlock(Section.USER, "q", 0, "user"),
    ]
    out = engine.assemble(blocks, max_input_tokens=500)
    assert "kb-huge" in out.report.dropped  # exceeds the 60% knowledge section cap
    assert "k-tiny" in out.prompt  # still fits → kept (best-fit, not first-fit-stop)


def test_second_system_block_dropped_is_reported_not_silent():
    """P-G honesty: only the first system block is the contract, but any
    further system block must appear in report.dropped — never vanish silently."""
    engine = ContextEngine()
    blocks = [
        ContextBlock(Section.SYSTEM, "primary rules", 0, "sys-primary"),
        ContextBlock(Section.SYSTEM, "secondary rules", 1, "sys-secondary"),
        ContextBlock(Section.USER, "q", 0, "user"),
    ]
    out = engine.assemble(blocks, max_input_tokens=1_000)
    assert "primary rules" in out.prompt
    assert "secondary rules" not in out.prompt
    assert "sys-secondary" in out.report.dropped
    assert "sys-primary" not in out.report.dropped


def test_late_oversized_user_block_truncated_and_reported():
    """P-G honesty: an oversized user block arriving AFTER the first one is
    truncated (and reported) — never kept whole to silently blow the budget."""
    engine = ContextEngine()
    blocks = [
        ContextBlock(Section.USER, "short question", 0, "u1"),
        ContextBlock(Section.USER, "flood " * 2_000, 1, "u2"),  # ≈2501 tok ≫ 50% cap
    ]
    out = engine.assemble(blocks, max_input_tokens=300)
    assert "short question" in out.prompt
    assert _TRUNCATION_MARK in out.prompt
    assert "user" in out.report.truncated_sections
    assert out.report.fits


def test_oversized_system_block_after_first_is_dropped_not_truncated():
    """Only the first system block participates in keep/truncate; a second
    oversized one is a reported drop, never a silent budget violation."""
    engine = ContextEngine()
    blocks = [
        ContextBlock(Section.SYSTEM, "keep me", 0, "sys-1"),
        ContextBlock(Section.SYSTEM, "rule " * 5_000, 1, "sys-2-huge"),
        ContextBlock(Section.USER, "q", 0, "user"),
    ]
    out = engine.assemble(blocks, max_input_tokens=300)
    assert "keep me" in out.prompt
    assert "rule" not in out.prompt
    assert "sys-2-huge" in out.report.dropped
    assert "system" not in out.report.truncated_sections  # first block was small
