"""#3211 Living Issue Architecture — pure-unit tests.

Covers:
- AC-2: append_living_observation wiring (gh-call mocked; fail-honest semantics)
- AC-4: Alternative Solutions Ledger formatter (pure) + missing-arg gate
- AC-3: force_multiplier_tier classification + build_queue tier tie-break
- Distinct signatures on the same file remain permitted (AC-5 semantic,
  enforced via fingerprint() composition — different root_cause/scope => diff fp)

Run: python -m pytest tests/test_living_issue_dedup.py --noconftest -q
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

# priority_queue_ledger gh_bin() import-সময়ে gh খোঁজে — না পেলে sys.exit(1)।
# টেস্ট-লোডার নিজেই deterministic করে: GH_BIN সেট করে দিই (আছে হলে)।
_gh = shutil.which("gh") or "/tmp/gh_2.63.2_linux_amd64/bin/gh"
if _gh and os.path.isfile(_gh):
    os.environ.setdefault("GH_BIN", _gh)


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ci = _load("create_issue_mod", "scripts/agents/create_issue.py")
pq = _load("pq_ledger_mod", "scripts/agents/priority_queue_ledger.py")
fp = _load("fp_mod", "scripts/agents/issue_fingerprint.py")


# --- AC-4: Alternative Solutions Ledger formatter (pure) ---------------------


class TestAlternativeSolutionsLedger:
    def test_table_contains_both_approaches_and_recommendation(self):
        out = ci.format_alternative_solutions_ledger("keep polling", "force now", "force with evidence")
        assert "**A (previous)**" in out and "keep polling" in out
        assert "**B (proposed)**" in out and "force now" in out
        assert "force with evidence" in out

    def test_table_is_markdown_with_header(self):
        out = ci.format_alternative_solutions_ledger("a", "b", "c")
        assert out.startswith("### ⚖️ Alternative Solutions Ledger")
        assert "| Approach | Description | Trade-offs |" in out
        assert "|---|---|---|" in out

    def test_whitespace_inputs_are_stripped(self):
        out = ci.format_alternative_solutions_ledger("  a  ", "  b  ", "  c  ")
        assert "| **A (previous)** | a |" in out
        assert "| **B (proposed)** | b |" in out
        assert "c" in out.split("**Comparative Recommendation:**")[1]


# --- AC-2: living observation append (gh mocked, fail-honest) ----------------


class TestLivingObservation:
    def _fake_gh(self, code=0, out="https://github.com/x/y#issuecomment-1\n"):
        res = subprocess.CompletedProcess(args=[], returncode=code, stdout=out, stderr="")
        return patch.object(subprocess, "run", return_value=res)

    def test_success_posts_comment_and_returns_url(self):
        with self._fake_gh(0) as _:
            ok, url = ci.append_living_observation(3211, "t", "b", "fp-1")
        assert ok is True and "issuecomment" in url

    def test_gh_failure_is_fail_honest(self):
        res = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="boom")
        with patch.object(subprocess, "run", return_value=res):
            ok, err = ci.append_living_observation(3211, "t", "b", "fp-1")
        assert ok is False and "boom" in err

    def test_body_carries_fingerprint_and_header(self):
        with self._fake_gh(0) as p:
            ci.append_living_observation(3211, "would-be title", "obs body", "fp-9", role="coder")
            body = p.call_args.args[0][5]
        assert "Living Issue Update" in body and "`fp-9`" in body and "would-be title" in body


# --- AC-3: force-multiplier tiers + queue ordering ----------------------------


class TestForceMultiplierTier:
    def test_tier1_weapons_and_gateways(self):
        assert pq.force_multiplier_tier("fix(agents): claim gate misroute", []) == 1
        assert pq.force_multiplier_tier("x", [{"name": "area:ci"}, {"name": "type:bug"}]) in (2, 3)

    def test_tier2_core_infra(self):
        assert pq.force_multiplier_tier("security(vault): rotate", []) == 2
        assert pq.force_multiplier_tier("fix(db): schema drift", []) == 2

    def test_tier3_leaf_default(self):
        assert pq.force_multiplier_tier("fix(ui): button padding", []) == 3

    def test_label_words_count(self):
        assert pq.force_multiplier_tier("unrelated title", [{"name": "area:ci"}]) >= 2

    def test_tier_beats_age_within_same_priority(self):
        older_leaf = {"title": "fix(ui): padding", "labels": [{"name": "P1-high"}], "createdAt": "2026-01-01T00:00:00Z"}
        newer_weapon = {"title": "fix(ci): claim gate", "labels": [{"name": "P1-high"}], "createdAt": "2026-06-01T00:00:00Z"}
        queue = pq.build_queue([older_leaf, newer_weapon])
        # ৪-tuple contract (worker-engine merge): (rank, seq, createdAt, issue) → issue = row[3]
        assert queue[0][3]["title"].startswith("fix(ci)")


# --- AC-5 semantic: distinct signatures on same file are distinct fingerprints


class TestDistinctSignatures:
    def test_same_file_different_root_cause_differs(self):
        a = fp.fingerprint("SECURITY", "bug in auth.py", "auth.py", "logic")
        b = fp.fingerprint("SECURITY", "bug in auth.py", "auth.py", "concurrency")
        assert a != b

    def test_same_signature_is_equal(self):
        a = fp.fingerprint("SECURITY", "token leak", "auth.py", "hardcoding")
        b = fp.fingerprint("SECURITY", "token leak", "auth.py", "hardcoding")
        assert a == b
