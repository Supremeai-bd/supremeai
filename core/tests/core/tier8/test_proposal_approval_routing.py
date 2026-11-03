"""#2529 — tier8 refactor proposals → ApprovalWorkflow human-gate routing টেস্ট।

বাংলা মন্তব্য: dry-run-passed প্রস্তাব এখন approval queue-তে যায় (log-and-drop
নয়); cooldown নীরবে গোনা হয়; approval module অনুপস্থিত হলে feedback-fallback।
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("core.tier8.codebase_refactor_proposer")

from adaptive_engine.approval_workflow import ProposalCooldownError
from core.tier8.codebase_refactor_proposer import (
    CodebaseRefactorProposer,
    ImprovementProposal,
)


def _proposal(
    weakness_type: str = "LONG_FUNCTION",
    target_file: str = "backend/api/routes/chat.py",
    confidence: float = 0.9,
    dry_run_passed: bool = False,
) -> ImprovementProposal:
    # frozen dataclass — মিউটেশন নয়, constructor-এই ফ্ল্যাগ
    return ImprovementProposal(
        proposal_id=f"prop-test-{weakness_type.lower()}",
        target_file=target_file,
        weakness_type=weakness_type,
        severity="medium",
        suggested_patch="@@ -10,3 +10,9 @@ refactor sketch",
        confidence=confidence,
        rationale="Auto-detected long function; split for maintainability",
        dry_run_passed=dry_run_passed,
    )


def _proposer_with_proposals(proposals: list[ImprovementProposal]) -> CodebaseRefactorProposer:
    """সিঙ্গেলটন বাইপাস করে fresh proposer — _proposals ইনজেক্টেড।"""
    feedback = MagicMock()
    # প্রকৃত মেথড async — fallback-assertion-এর জন্য AsyncMock দরকার
    feedback.record_suggestion_feedback = AsyncMock()
    proposer = object.__new__(CodebaseRefactorProposer)
    proposer.__dict__.update(
        {
            "_proposals": list(proposals),
            "_max_proposals": 50,
            "_min_confidence": 0.85,
            "_scan_interval": 3600.0,
            "_feedback": feedback,
            "_llm": None,
        }
    )
    return proposer


def _patched_workflow(
    monkeypatch: pytest.MonkeyPatch, *, raise_cooldown: bool = False
) -> MagicMock:
    wf = MagicMock()
    wf.propose = AsyncMock(
        side_effect=ProposalCooldownError("cooldown") if raise_cooldown else None
    )
    import adaptive_engine.approval_workflow as aw

    monkeypatch.setattr(aw, "get_approval_workflow", lambda: wf)
    return wf


async def test_dry_run_passed_routes_to_approval(monkeypatch):
    """মূল চুক্তি: dry-run-passed প্রস্তাব ApprovalWorkflow.propose() পায়।"""
    wf = _patched_workflow(monkeypatch)
    p = _proposal(dry_run_passed=True)
    proposer = _proposer_with_proposals([p])

    await proposer._apply_approved()

    wf.propose.assert_awaited_once()
    proposal_arg = wf.propose.call_args[0][0]
    assert proposal_arg.kind.value == "LEARNING_PROPOSAL"
    assert "LONG_FUNCTION" in proposal_arg.title
    assert proposal_arg.payload["target_file"] == "backend/api/routes/chat.py"
    assert proposal_arg.payload["confidence"] == pytest.approx(0.9)
    assert proposal_arg.dedup_key == "tier8-refactor:LONG_FUNCTION:backend/api/routes/chat.py"
    # প্রস্তাব queue-তে গেছে — ফাইলার feedback-fallback হয়নি
    proposer._feedback.record_suggestion_feedback.assert_not_awaited()
    # প্রসেস হয়ে বাদ
    assert proposer._proposals == []


async def test_not_dry_run_passed_skipped(monkeypatch):
    """dry-run পাস করেনি এমন প্রস্তাব queue-তে যাবে না — অপেক্ষমান থাকবে।"""
    wf = _patched_workflow(monkeypatch)
    p = _proposal(confidence=0.99)  # confidence উঁচু কিন্তু dry_run পাস নয়
    proposer = _proposer_with_proposals([p])

    await proposer._apply_approved()

    wf.propose.assert_not_awaited()
    assert len(proposer._proposals) == 1  # রয়ে গেছে


async def test_cooldown_treated_as_routed(monkeypatch):
    """ProposalCooldownError — একই প্রস্তাব pending; নতুন entry নয়, fallback-ও নয়।"""
    wf = _patched_workflow(monkeypatch, raise_cooldown=True)
    p = _proposal(dry_run_passed=True)
    proposer = _proposer_with_proposals([p])

    await proposer._apply_approved()

    wf.propose.assert_awaited_once()
    proposer._feedback.record_suggestion_feedback.assert_not_awaited()
    assert proposer._proposals == []


async def test_routing_failure_falls_back_to_feedback(monkeypatch):
    """propose() অন্য কারণে ব্যর্থ → আগের log-only fallback আচরণ অক্ষুণ্ণ।"""
    wf = MagicMock()
    wf.propose = AsyncMock(side_effect=RuntimeError("db down"))
    import adaptive_engine.approval_workflow as aw

    monkeypatch.setattr(aw, "get_approval_workflow", lambda: wf)
    p = _proposal(dry_run_passed=True)
    proposer = _proposer_with_proposals([p])

    await proposer._apply_approved()

    proposer._feedback.record_suggestion_feedback.assert_awaited_once()
    assert proposer._proposals == []


async def test_low_confidence_not_processed(monkeypatch):
    """min_confidence-এর নিচে — dry_run পাস থাকলেও queue/fallback কিছুই নয়।"""
    wf = _patched_workflow(monkeypatch)
    p = _proposal(confidence=0.5, dry_run_passed=True)
    proposer = _proposer_with_proposals([p])

    await proposer._apply_approved()

    wf.propose.assert_not_awaited()
    assert len(proposer._proposals) == 1


async def test_batch_routes_each_proposal(monkeypatch):
    """একাধিক approved প্রস্তাব — প্রতিটি আলাদা queue-entry পায়।"""
    wf = _patched_workflow(monkeypatch)
    proposals = []
    for i in range(3):
        proposals.append(
            _proposal(
                weakness_type=f"WEAKNESS_{i}",
                target_file=f"backend/file_{i}.py",
                dry_run_passed=True,
            )
        )
    proposer = _proposer_with_proposals(proposals)

    await proposer._apply_approved()

    assert wf.propose.await_count == 3
    dedup_keys = [c.args[0].dedup_key for c in wf.propose.await_args_list]
    assert len(set(dedup_keys)) == 3  # প্রতিটির dedup-key স্বতন্ত্র
