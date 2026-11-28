#!/usr/bin/env python3
"""Apply approved admin rule proposals from Supabase into rules.yml (auto-PR).

Owner dashboard flow (constitution rule ``owner_action_queue_protocol``):
admin POSTs proposals via ``/admin-api/agent-rules/proposals`` → rows land in
``agent_rule_updates`` (status=proposed, deduped) → this scheduled job renders
each proposal into ``.github/constitution/rules.yml`` (hard_rules), regenerates
AGENTS.md via the SSOT generator, and opens one auto-PR per proposal in this
repo. Admin then reviews/merges; the dashboard flips the row applied/rejected.

Advisory by design: missing creds or zero proposals exit 0; a failing proposal
is reported and skipped, never blocks the rest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = REPO_ROOT / ".github" / "constitution" / "rules.yml"
TABLE = "agent_rule_updates"
REPO = os.getenv("GH_REPO") or os.getenv("GITHUB_REPOSITORY") or "Supremeai-bd/supremeai"


def _conf() -> tuple[str, str] | None:
    url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or "").strip()
    if not url.startswith("https://") or not key:
        return None
    return url, key


def _rest(url: str, key: str, method: str, path: str, payload: dict | None = None) -> list[dict]:
    req = urllib.request.Request(
        f"{url}/rest/v1/{path}",
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return json.loads(body) if body.strip() else []


def _propose_rules_edit(rules_text: str, rule_key: str, rule_text: str) -> str:
    """Append the new hard rule before ``freedoms:`` (mirrors SSOT layout)."""
    if f"  {rule_key}:" in rules_text:
        raise ValueError(f"rule_key '{rule_key}' already exists in rules.yml")
    anchor = "freedoms:"
    idx = rules_text.index(anchor)
    entry = f'  {rule_key}: "{rule_text}"\n\n'
    return rules_text[:idx] + entry + rules_text[idx:]


def _run(cmd: list[str], cwd: Path = REPO_ROOT) -> str:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def apply_proposal(row: dict[str, Any], create_pr: bool) -> int:
    """Return the PR number, or 0 when nothing was needed / PR creation skipped."""
    rule_key = str(row["rule_key"])
    rule_text = str(row["rule_text"])
    proposal_id = str(row["proposal_id"])
    title = str(row.get("title") or f"constitution: add rule {rule_key}")

    rules_text = RULES_PATH.read_text(encoding="utf-8")
    new_text = _propose_rules_edit(rules_text, rule_key, rule_text)
    sha = hashlib.sha256(f"{rule_key}:{rule_text}".encode()).hexdigest()[:12]
    branch = f"bot/agent-rule-{rule_key}-{sha}"

    RULES_PATH.write_text(new_text, encoding="utf-8", newline="")
    try:
        sys.path.insert(0, str(REPO_ROOT))
        from scripts.ci.generate_agents_md import main as gen_main  # type: ignore[attr-defined]

        gen_main()  # regenerates AGENTS.md; raises on drift
    finally:
        pass

    _run(["git", "config", "user.name", "github-actions[bot]"])
    _run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"])
    _run(["git", "checkout", "-B", branch])
    _run(["git", "add", str(RULES_PATH.relative_to(REPO_ROOT)), "AGENTS.md"])
    _run(["git", "commit", "-m", f"feat(constitution): apply admin rule proposal {rule_key} ({sha})"])
    if not create_pr:
        _run(["git", "checkout", "-", ])
        return 0
    _run(["git", "push", "-u", "origin", branch, "--force"])
    pr_number = _run(
        [
            "gh", "pr", "create",
            "--title", f"feat(constitution): admin rule proposal - {title}",
            "--body",
            ("Applies an admin-dashboard rule proposal into the constitution SSOT.\n\n"
            f"- proposal_id: `{proposal_id}`\n- rule_key: `{rule_key}`\n"
            f"- content_sha256 (first 12): `{sha}`\n- source: Supabase `agent_rule_updates`\n\n"
            "AGENTS.md regenerated from rules.yml by `scripts/ci/generate_agents_md.py`."),
        ]
    ).rsplit("/", 1)[-1]
    print(f"[applied] {rule_key} -> PR {pr_number}")
    return int(pr_number) if pr_number.isdigit() else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create-pr", action="store_true", help="push branch and open the PR")
    parser.add_argument("--dry-run", action="store_true", help="print what would be applied")
    args = parser.parse_args(argv)

    conf = _conf()
    if not conf:
        print("::warning::SUPABASE_URL/SERVICE key missing - nothing to apply (advisory).")
        return 0
    url, key = conf
    try:
        rows = _rest(url, key, "GET", f"{TABLE}?status=eq.proposed&order=created_at.asc&limit=20")
    except Exception as exc:
        print(f"::warning::Could not fetch proposals: {type(exc).__name__} (advisory).")
        return 0
    if not rows:
        print("[clean] No pending admin rule proposals.")
        return 0
    print(f"[queue] {len(rows)} proposal(s) pending")
    failures = 0
    for row in rows:
        rule_key = str(row.get("rule_key"))
        try:
            if args.dry_run:
                print(f"[dry-run] would apply {rule_key}: {str(row.get('title'))[:80]}")
                continue
            pr = apply_proposal(row, create_pr=args.create_pr)
            if pr:
                _rest(url, key, "PATCH", f"{TABLE}?proposal_id=eq.{row['proposal_id']}", {"status": "applied", "applied_pr": pr})
        except Exception as exc:
            failures += 1
            print(f"::warning::proposal {rule_key} failed: {type(exc).__name__}: {exc}")
            _rest(url, key, "PATCH", f"{TABLE}?proposal_id=eq.{row['proposal_id']}", {"status": "rejected"})
    return 0 if failures < len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
