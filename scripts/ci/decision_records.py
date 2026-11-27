#!/usr/bin/env python3
"""Collect bounded, abstract decision-pattern candidates from GitHub.

This is a local, read-only review aid: no writes to Supabase, no model calls,
no automatic approval, runtime prompt injection, or training. The output contains
only a fixed vocabulary and GitHub-derived public provenance, never record prose.
Schema validation does not establish correctness or privacy of the source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from typing import Any

OPEN = "<!-- ai-decision-record v1 -->"
CLOSE = "<!-- /ai-decision-record -->"
MAX_DOCUMENT_BYTES = 256_000
MAX_RECORD_BYTES = 16_000
MAX_RECORDS_PER_DOCUMENT = 20
MAX_CANDIDATES = 200
MAX_PAGES = 10
PAGE_SIZE = 100

# Small, fixed vocabulary: agent-provided free text never becomes shared logic.
# New vocabulary entries require code review and evaluation, not candidate input.
FAMILIES = frozenset({"debugging", "decision", "explanation", "personalization", "research", "safety", "other"})
STEPS = {
    "clarify_goal": "Identify the user's actual goal and relevant constraints.",
    "identify_unknowns": "Separate known facts from assumptions; ask when necessary.",
    "inspect_evidence": "Check the available evidence and its provenance.",
    "compare_alternatives": "Compare suitable alternatives against the stated constraints.",
    "consider_user_preferences": "Respect explicitly provided preferences without inferring sensitive traits.",
    "check_risks": "Identify safety, privacy, cost and failure risks relevant to the task.",
    "choose_proportionately": "Choose a proportionate approach and state its conditions.",
    "verify_outcome": "Test or independently check the outcome where feasible.",
    "state_limitations": "Communicate uncertainty, limitations and unverified claims.",
}
CHECKS = frozenset({"source_provenance", "reproducible_test", "user_constraints", "privacy", "cost", "safety", "human_review"})
STOPS = frozenset({"missing_evidence", "missing_consent", "unknown_cost", "unsafe_action", "requires_human_review"})
STATES = frozenset({"proposed", "tested", "blocked", "superseded"})
REPO_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
LOGIN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}(?:\[bot\])?\Z")


class CandidateError(ValueError):
    """Invalid or incomplete input; messages never include user record content."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise CandidateError("Duplicate JSON field")
        obj[key] = value
    return obj


def _tokens(value: Any, allowed: Any, maximum: int) -> list[str]:
    if not isinstance(value, list) or not 1 <= len(value) <= maximum:
        raise CandidateError("Invalid pattern list length")
    if any(not isinstance(item, str) or item not in allowed for item in value):
        raise CandidateError("Unknown pattern vocabulary")
    if len(set(value)) != len(value):
        raise CandidateError("Duplicate pattern vocabulary")
    return value


def validate_pattern(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"task_family", "steps", "checks", "stop_conditions"}:
        raise CandidateError("Invalid reasoning_pattern fields")
    family = value["task_family"]
    if not isinstance(family, str) or family not in FAMILIES:
        raise CandidateError("Unknown task family")
    return {
        "task_family": family,
        "steps": _tokens(value["steps"], STEPS, 8),
        "checks": _tokens(value["checks"], CHECKS, 7),
        "stop_conditions": _tokens(value["stop_conditions"], STOPS, 5),
    }


def _record_blocks(body: str) -> list[str]:
    if not isinstance(body, str) or len(body.encode("utf-8")) > MAX_DOCUMENT_BYTES:
        raise CandidateError("Source body is too large or invalid")
    blocks: list[str] = []
    cursor = 0
    while True:
        start = body.find(OPEN, cursor)
        stray_close = body.find(CLOSE, cursor)
        if start < 0:
            if stray_close >= 0:
                raise CandidateError("Unmatched closing marker")
            return blocks
        if 0 <= stray_close < start:
            raise CandidateError("Unmatched closing marker")
        end = body.find(CLOSE, start + len(OPEN))
        if end < 0 or body.find(OPEN, start + len(OPEN), end) >= 0:
            raise CandidateError("Unmatched or nested marker")
        block = body[start + len(OPEN):end].strip()
        if len(block.encode("utf-8")) > MAX_RECORD_BYTES or len(blocks) >= MAX_RECORDS_PER_DOCUMENT:
            raise CandidateError("Decision records exceed limits")
        blocks.append(block)
        cursor = end + len(CLOSE)


def _source(repo: str, number: int, kind: str, obj: dict[str, Any]) -> dict[str, Any]:
    if not REPO_RE.fullmatch(repo) or any(part in (".", "..") for part in repo.split("/")):
        raise CandidateError("Invalid repository")
    if not isinstance(number, int) or isinstance(number, bool) or number < 1:
        raise CandidateError("Invalid issue number")
    identity = obj.get("id")
    actor = (obj.get("user") or {}).get("login") if isinstance(obj.get("user"), dict) else None
    updated = obj.get("updated_at")
    if kind not in ("issue", "comment") or not isinstance(identity, int) or isinstance(identity, bool) or identity < 1:
        raise CandidateError("Invalid GitHub source identity")
    if not isinstance(actor, str) or not LOGIN_RE.fullmatch(actor):
        raise CandidateError("Missing GitHub source actor")
    if not isinstance(updated, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", updated):
        raise CandidateError("Missing GitHub source revision")
    # GitHub user.login is the author, not necessarily the last editor/reviewer.
    return {"repo": repo, "issue_number": number, "kind": kind, "object_id": identity, "author": actor, "updated_at": updated}


def collect_document(repo: str, number: int, kind: str, obj: dict[str, Any]) -> list[dict[str, Any]]:
    source = _source(repo, number, kind, obj)
    body = obj.get("body") or ""
    candidates = []
    for index, block in enumerate(_record_blocks(body)):
        try:
            record = json.loads(block, object_pairs_hook=_unique_object)
        except (json.JSONDecodeError, RecursionError, ValueError) as exc:
            raise CandidateError("Malformed decision record JSON") from exc
        if not isinstance(record, dict) or record.get("schema") != "ai-decision-record/1":
            raise CandidateError("Invalid decision record schema")
        if "reasoning_pattern" not in record:
            continue  # Older records remain compatible; no invented abstraction.
        pattern = validate_pattern(record["reasoning_pattern"])
        status = record.get("status")
        if not isinstance(status, str) or status not in STATES:
            raise CandidateError("Invalid decision record status")
        # Hash full record bytes so changing free-text evidence invalidates any
        # downstream review. It is a revision fingerprint, not verified evidence.
        digest = hashlib.sha256(block.encode("utf-8")).hexdigest()
        identity = json.dumps([source, index, digest], sort_keys=True, separators=(",", ":"))
        candidates.append({
            "schema": "ai-reasoning-candidate/1",
            "id": hashlib.sha256(identity.encode()).hexdigest(),
            "source": source,
            "record_index": index,
            "record_sha256": digest,
            "reported_status": status,
            "review_status": "quarantined",
            "pattern": pattern,
        })
    return candidates


def _github_get(endpoint: str) -> Any:
    try:
        result = subprocess.run(["gh", "api", "--method", "GET", endpoint], check=True, capture_output=True, timeout=30)
        return json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        raise CandidateError("GitHub read failed; no candidates exported") from exc


def collect_issue(repo: str, number: int, fetch=_github_get) -> list[dict[str, Any]]:
    # Validate before interpolating into GitHub endpoint paths.
    if not REPO_RE.fullmatch(repo) or any(part in (".", "..") for part in repo.split("/")) or number < 1:
        raise CandidateError("Invalid repository or issue number")
    issue = fetch(f"repos/{repo}/issues/{number}")
    if not isinstance(issue, dict) or issue.get("number") != number:
        raise CandidateError("GitHub issue response did not match requested issue")
    result = collect_document(repo, number, "issue", issue)
    seen_comment_ids: set[int] = set()
    for page in range(1, MAX_PAGES + 1):
        comments = fetch(f"repos/{repo}/issues/{number}/comments?per_page={PAGE_SIZE}&page={page}")
        if not isinstance(comments, list) or len(comments) > PAGE_SIZE:
            raise CandidateError("Invalid GitHub comment response")
        for comment in comments:
            if not isinstance(comment, dict):
                raise CandidateError("Invalid GitHub comment")
            comment_id = comment.get("id")
            if not isinstance(comment_id, int) or isinstance(comment_id, bool) or comment_id < 1 or comment_id in seen_comment_ids:
                raise CandidateError("Invalid or repeated GitHub comment identity")
            seen_comment_ids.add(comment_id)
            result.extend(collect_document(repo, number, "comment", comment))
            if len(result) > MAX_CANDIDATES:
                raise CandidateError("Candidate limit reached; refusing an incomplete result")
        if len(comments) < PAGE_SIZE:
            return result
    raise CandidateError("Comment limit reached; refusing an incomplete result")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--issue", type=int, help="GitHub issue or PR number to review")
    mode.add_argument("--catalog", action="store_true", help="Show the allowed abstract vocabulary")
    parser.add_argument("--repo", default=os.getenv("GH_REPO") or os.getenv("GITHUB_REPOSITORY") or "Supremeai-bd/supremeai")
    args = parser.parse_args(argv)
    if args.catalog:
        payload = {"families": sorted(FAMILIES), "steps": STEPS, "checks": sorted(CHECKS), "stop_conditions": sorted(STOPS)}
    else:
        try:
            candidates = collect_issue(args.repo, args.issue)
        except CandidateError as exc:
            print(f"Decision candidate collection failed: {exc}", file=sys.stderr)
            return 1
        payload = {"schema": "ai-reasoning-candidate-bundle/1", "review_status": "quarantined", "count": len(candidates), "candidates": candidates}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
