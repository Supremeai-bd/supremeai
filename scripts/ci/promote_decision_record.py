"""Stage validated AI decision records into Candidate DB and promote only after verification.

Stage 1 (stage_candidate): extracts `<!-- ai-decision-record v1 -->` JSON from commit/PR text,
validates via `scripts/ci/decision_records.py`, and writes to `ai_decision_candidates` with
`status = 'pending_verification'` (never directly to `ai_verified_memories`).

Stage 2 (promote_candidate): promotes a candidate to `ai_verified_memories` only when
explicitly approved by an authorized reviewer.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ci.decision_records import collect_document
from scripts.ci.ingest_pr_knowledge import post_to_supabase


def stage_candidate(
    repo: str,
    source_kind: str,
    source_number: int,
    body: str,
    commit_sha: str = "",
    post_fn: Callable[[str, str, str, dict[str, Any]], bool] = post_to_supabase,
    supabase_url: str | None = None,
    supabase_key: str | None = None,
) -> list[dict[str, Any]]:
    """Validate decision records in body and stage them as `pending_verification`."""
    doc = {
        "id": max(source_number, 1),
        "body": body,
        "updated_at": "2026-11-28T00:00:00Z",
        "user": {"login": "supremeai-agent"},
    }
    records = collect_document(repo, max(source_number, 1), "issue", doc)
    if not records:
        raise ValueError("No valid ai-decision-record v1 block found")

    url = supabase_url if supabase_url is not None else os.environ.get("SUPABASE_URL", "")
    key = supabase_key if supabase_key is not None else os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    staged: list[dict[str, Any]] = []
    for rec in records:
        row = {
            "repo": repo,
            "source_kind": source_kind,
            "source_number": source_number,
            "commit_sha": commit_sha or None,
            "agent": rec.get("source", {}).get("author", "unknown"),
            "task_type": rec.get("task_family", "other"),
            "task_ref": f"{source_kind}:{source_number}" if source_number else (commit_sha or "commit"),
            "decision": rec.get("task_family", "other"),
            "reason": "validated_decision_record",
            "record_json": rec,
            "status": "pending_verification",
        }
        if url and key:
            if not post_fn(url, key, "ai_decision_candidates", row):
                raise RuntimeError("Failed to stage candidate into ai_decision_candidates")
        staged.append(row)
    return staged


def promote_candidate(
    candidate_id: int,
    candidate_row: dict[str, Any],
    reviewer: str,
    approved: bool = False,
    post_fn: Callable[[str, str, str, dict[str, Any]], bool] = post_to_supabase,
    supabase_url: str | None = None,
    supabase_key: str | None = None,
) -> dict[str, Any]:
    """Promote an approved candidate into `ai_verified_memories` (fail-closed)."""
    if not approved or not reviewer.strip():
        raise PermissionError("Promotion requires explicit approval and reviewer identity")
    if candidate_row.get("status") not in ("pending_verification", "approved"):
        raise ValueError(f"Candidate {candidate_id} is not promotable (status={candidate_row.get('status')})")

    rec = candidate_row.get("record_json") or {}
    pattern = rec.get("reasoning_pattern") if isinstance(rec, dict) else None
    memory_row = {
        "candidate_id": candidate_id,
        "task_family": pattern.get("task_family") if isinstance(pattern, dict) else None,
        "decision": candidate_row["decision"],
        "reasoning_pattern": pattern,
        "promoted_by": reviewer.strip(),
    }

    url = supabase_url if supabase_url is not None else os.environ.get("SUPABASE_URL", "")
    key = supabase_key if supabase_key is not None else os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if url and key:
        if not post_fn(url, key, "ai_verified_memories", memory_row):
            raise RuntimeError("Failed to promote candidate into ai_verified_memories")
    return memory_row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage AI decision records into Candidate DB")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--kind", choices=["commit", "issue", "pr"], default="commit")
    parser.add_argument("--number", type=int, default=0)
    parser.add_argument("--commit-sha", default="")
    parser.add_argument("--body-file", required=True)
    args = parser.parse_args(argv)

    body = Path(args.body_file).read_text(encoding="utf-8")
    staged = stage_candidate(args.repo, args.kind, args.number, body, commit_sha=args.commit_sha)
    print(f"Staged {len(staged)} candidate(s) with status=pending_verification")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
