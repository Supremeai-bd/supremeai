#!/usr/bin/env python3
"""scripts/ci/landing_decision_compose.py — compose the landing decision.

`scripts/ci/tiny_brain_pr_guard.py` is the **authority** for whether a PR may
land: it is executed from the trusted base commit, it owns the CI-evidence and
protected-path policy, and it emits `decision` / `reason` on `GITHUB_OUTPUT`.

`scripts/ci/ai_pr_evaluator.py` is a **second opinion**: it scores Value (does
the PR solve a real problem?) and Safety (gates green, no conflict, synced,
claim chain) and returns AUTO_MERGE / PENDING / HOLD_AND_FIX / CLOSE.

This module defines the only permitted composition rule:

    **downgrade-only, fail-open.**

  * The advisor may turn AUTO_MERGE into OWNER_REVIEW (a human looks).
  * The advisor may NEVER upgrade anything — not OWNER_REVIEW into
    AUTO_MERGE, not BLOCKED into anything.
  * Any advisor problem (crash, timeout, unparsable output, PENDING) is a
    no-op: the authority's decision stands.

Why the asymmetry matters: the advisor is heuristic (heuristics + optional LLM
enrichment) and must never be able to widen its own blast radius into an
auto-merge. A false hold costs a human minute; a false auto-merge costs main.

Stdlib-only and pure so the rule is unit-testable without GitHub or a model.
"""

from __future__ import annotations

import json

AUTO_MERGE = "AUTO_MERGE"
OWNER_REVIEW = "OWNER_REVIEW"
BLOCKED = "BLOCKED"
PENDING = "PENDING"
HOLD_AND_FIX = "HOLD_AND_FIX"
CLOSE = "CLOSE"

# Advisor verdict -> reason recorded when the authority's AUTO_MERGE is held.
DOWNGRADE_REASONS = {
    HOLD_AND_FIX: "advisor_hold",
    CLOSE: "advisor_close",
}


def parse_verdict(stdout: str) -> str | None:
    """Extract the advisor verdict from `ai_pr_evaluator.py --json` stdout.

    Tolerates leading/trailing log noise by scanning for the last line that
    parses as a JSON object carrying a `verdict` string.
    """
    verdict: str | None = None
    for line in stdout.splitlines():
        candidate = line.strip()
        if not candidate.startswith("{") or not candidate.endswith("}"):
            continue
        try:
            payload = json.loads(candidate)
        except (ValueError, TypeError):
            continue
        if isinstance(payload, dict) and isinstance(payload.get("verdict"), str):
            verdict = payload["verdict"].strip().upper()
    return verdict


def compose(
    guard_decision: str, guard_reason: str, advisor_verdict: str | None
) -> tuple[str, str]:
    """Return `(decision, reason)` after applying the downgrade-only rule."""
    decision = (guard_decision or "").strip().upper()
    reason = (guard_reason or "").strip()
    if decision != AUTO_MERGE:
        return decision, reason
    held = DOWNGRADE_REASONS.get((advisor_verdict or "").strip().upper())
    if held is None:
        return decision, reason
    return OWNER_REVIEW, held


def main(argv: list[str] | None = None) -> int:
    """CLI seam for the workflow: `--decision D --reason R [--advisor-stdout FILE]`."""
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="downgrade-only landing decision compose")
    ap.add_argument("--decision", required=True)
    ap.add_argument("--reason", default="")
    ap.add_argument("--advisor-stdout", default=None, help="file with advisor stdout")
    args = ap.parse_args(argv)

    stdout = ""
    if args.advisor_stdout:
        try:
            with open(args.advisor_stdout, encoding="utf-8", errors="replace") as fh:
                stdout = fh.read()
        except OSError:
            stdout = ""
    decision, reason = compose(args.decision, args.reason, parse_verdict(stdout))
    sys.stdout.write(f"decision={decision}\nreason={reason}\n")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
