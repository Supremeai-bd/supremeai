#!/usr/bin/env python3
r"""SupremeAI â€” Collective Agent Memory & Problem-Solving Layer CLI.

Implements the "Search Before Solving Â· Pave Before Leaving Â· Gap Before Guessing" workflow:
1. Search database & LESSONS_LEARNED.md for how previous agents solved the same issue.
2. Record newly validated solutions into database memory and LESSONS_LEARNED.md.
3. Record Solution Gaps (failed attempts, missing capabilities, future path) when no solution exists.
4. Verify MCP Control Tower connection contract.
5. Tower semantic fallback (#1747, slice 1): when local recall is thin, query
   the Control Tower's semantic memory tier (memory_search_semantic /
   memory_get_similar_tasks). Every hit carries a "tier" label; tower
   unavailability degrades gracefully to local-only results (warn, exit 0).

Usage:
    # 1. Search for existing solutions:
    python scripts/agents/agent_solution_memory.py search --query "UnicodeEncodeError charmap"

    # 2. Record a validated solution:
    python scripts/agents/agent_solution_memory.py record \
        --task-id "2237" \
        --problem "PowerShell cp1252 stdout fails on UTF-8 emojis" \
        --solution "Prefix command with PYTHONIOENCODING=utf-8" \
        --lesson "Always set PYTHONIOENCODING in windows terminal subprocesses" \
        --status "VERIFIED" \
        --tags "windows,encoding,powershell"

    # 3. Record a Solution Gap (when no solution yet exists):
    python scripts/agents/agent_solution_memory.py gap \
        --task-id "1042" \
        --problem "Authentication token refresh fails inside isolated container" \
        --failed-attempts "OAuth refresh failed; stored token caused security violation" \
        --missing-capability "credential.refresh.scoped" \
        --future-path "Implement scoped credential broker endpoint"

    # 4. Verify MCP connection:
    python scripts/agents/agent_solution_memory.py verify-mcp
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# Ensure repository root is in sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

LESSONS_FILE = REPO_ROOT / "LESSONS_LEARNED.md"
MCP_CONFIG_FILE = REPO_ROOT / "mcp.json"
SQLITE_DB_PATH = REPO_ROOT / "data" / "supremeai.db"
STRATEGIC_FILE = REPO_ROOT / "data" / "strategic_decisions.jsonl"

# --- Tower semantic-memory tier (#1747 slice 1: Gold Pearl, stdlib-only) ---
# Session pattern mirrors examples/mcp-client-py/client.py (docs/MCP_CONNECT.md):
# initialize -> Mcp-Session-Id -> notifications/initialized -> tools/call.
TOWER_MCP_URL = os.environ.get(
    "SUPREMEAI_MCP_TOWER_URL",
    os.environ.get("MCP_TOWER_URL", "https://supremeai-mcp-tower.onrender.com"),
).rstrip("/")
if not TOWER_MCP_URL.endswith("/mcp"):
    TOWER_MCP_URL += "/mcp"
TOWER_FALLBACK_MIN_HITS = 3  # default; per-call override via MEMORY_TOWER_FALLBACK_MIN_HITS
TOWER_TIMEOUT_SECS = float(os.environ.get("MEMORY_TOWER_TIMEOUT_SECS", "6"))
_MCP_ACCEPT = "application/json, text/event-stream"


def _fallback_min_hits() -> int:
    """Local-recall threshold below which the tower tier is queried (#1747)."""
    try:
        return int(os.environ.get("MEMORY_TOWER_FALLBACK_MIN_HITS", str(TOWER_FALLBACK_MIN_HITS)))
    except ValueError:
        return TOWER_FALLBACK_MIN_HITS


def _tower_post(session_id: str | None, payload: dict[str, Any]) -> tuple[str, str]:
    """POST one JSON-RPC message to the tower; return (sse_body, session_id)."""
    import urllib.error
    import urllib.request

    headers = {"Content-Type": "application/json", "Accept": _MCP_ACCEPT}
    if session_id:
        headers["mcp-session-id"] = session_id
    req = urllib.request.Request(
        TOWER_MCP_URL, data=json.dumps(payload).encode("utf-8"),
        headers=headers, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TOWER_TIMEOUT_SECS) as resp:  # nosec B310 â€” tower MCP endpoint, env-overridable with pinned https default; audited #2081
            return (resp.read().decode("utf-8", errors="replace"),
                    resp.headers.get("mcp-session-id") or session_id or "")
    except urllib.error.HTTPError as err:  # honest failure class (4xx/5xx)
        raise RuntimeError(f"tower HTTP {err.code}") from err


def _parse_mcp_results(body: str) -> list[dict[str, Any]]:
    """Extract MCP result payloads from an SSE body ('data: <json>' lines)."""
    out: list[dict[str, Any]] = []
    for line in body.splitlines():
        if not line.startswith("data: "):
            continue
        try:
            msg = json.loads(line[6:])
        except json.JSONDecodeError:
            continue
        if isinstance(msg, dict) and isinstance(msg.get("result"), dict):
            out.append(msg["result"])
    return out


def _coerce_memory_items(result: dict[str, Any]) -> list[Any]:
    """Normalize a tower memory tool result to an item list (shapes vary)."""
    items: list[Any] = []
    for part in result.get("content") or []:
        if not (isinstance(part, dict) and part.get("type") == "text"):
            continue
        try:
            parsed = json.loads(part.get("text", ""))
        except (json.JSONDecodeError, TypeError):
            parsed = part.get("text", "")
        if isinstance(parsed, dict):
            for key in ("results", "tasks"):
                if isinstance(parsed.get(key), list):
                    items.extend(parsed[key])
        elif isinstance(parsed, list):
            items.extend(parsed)
        elif parsed:
            items.append({"text": str(parsed)})
    return [item for item in items if item is not None]


def _tower_semantic_hits(query: str) -> list[dict[str, Any]]:
    """Query the tower semantic tier (one session, two read-only tools).

    Raises on any tower failure â€” callers degrade to local-only results.
    """
    _, session_id = _tower_post(None, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "agent-solution-memory", "version": "1.0.0"},
        },
    })
    _tower_post(session_id, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    hits: list[dict[str, Any]] = []
    plans = (
        ("memory_search_semantic", "tower-semantic", "semantic"),
        ("memory_get_similar_tasks", "tower-similar-tasks", "similar-task"),
    )
    for tool, tier, hit_type in plans:
        body, session_id = _tower_post(session_id, {
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": tool, "arguments": {"query": query, "limit": 5}},
        })
        for result in _parse_mcp_results(body):
            for item in _coerce_memory_items(result):
                if isinstance(item, dict):
                    text = str(item.get("text") or item.get("summary") or item.get("outcome")
                               or item.get("context") or item.get("title") or "")
                    task_id = str(item.get("task_id") or item.get("id") or "unknown")
                    solution = str(item.get("solution") or "")
                else:
                    text, task_id, solution = str(item), "unknown", ""
                if text:
                    hits.append({
                        "task_id": task_id, "type": hit_type, "problem": text,
                        "solution": solution, "success": True,
                        "source": f"tower:{tool}", "tier": tier,
                    })
    return hits


def search_local_lessons(query: str) -> list[dict[str, str]]:
    """Search LESSONS_LEARNED.md for relevant entries matching keywords in query."""
    hits = []
    if not LESSONS_FILE.exists():
        return hits

    terms = [t.lower() for t in re.split(r"[\s,:;\-_]+", query) if len(t) > 2]
    if not terms:
        return hits

    try:
        content = LESSONS_FILE.read_text(encoding="utf-8", errors="replace")
    except Exception as err:
        print(f"[WARN] Failed reading LESSONS_LEARNED.md: {err}", file=sys.stderr)
        return hits

    for line in content.splitlines():
        line_clean = line.strip()
        if not line_clean.startswith("|") or "Date" in line_clean or "---" in line_clean:
            continue
        line_lower = line_clean.lower()
        score = sum(1 for term in terms if term in line_lower)
        if score > 0:
            hits.append({"text": line_clean, "score": score, "source": "LESSONS_LEARNED.md", "tier": "lessons-file"})

    hits.sort(key=lambda x: x["score"], reverse=True)
    return hits[:5]


def search_database_memory(query: str) -> list[dict[str, Any]]:
    """Search episodic memory or SQLite database for similar past task solutions and gaps."""
    hits = []
    try:
        from memory.episodic_memory import EpisodicMemory

        ep_mem = EpisodicMemory(db_path=str(SQLITE_DB_PATH))
        results = ep_mem.recall_episodes(query=query)
        for ep in results:
            hits.append({
                "task_id": ep.get("task_id", ep.get("id", "unknown")),
                "type": ep.get("event_type", "solution"),
                "problem": ep.get("context", ep.get("input_data", "")),
                "solution": ep.get("outcome", ep.get("output_data", "")),
                "success": ep.get("success", True),
                "source": "EpisodicMemory (Database)",
                "tier": "local-episodic",
            })
    except Exception:
        pass
    if len(hits) < _fallback_min_hits():
        # #1747: local recall thin -> tower semantic tier fallback.
        # Graceful degradation is the contract: tower unreachable or tool
        # error -> local-only results, warn line, exit stays 0, never a crash,
        # never fabricated hits.
        try:
            hits.extend(_tower_semantic_hits(query))
        except Exception as err:
            print(
                f"[WARN] Tower semantic tier unavailable ({type(err).__name__}); serving local-only results.",
                file=sys.stderr,
            )
    return hits


def record_solution(
    task_id: str,
    problem: str,
    solution: str,
    lesson: str,
    status: str = "VERIFIED",
    tags: list[str] | None = None,
) -> bool:
    """Record solution into database episodic memory and LESSONS_LEARNED.md."""
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    clean_task = task_id.lstrip("#")

    # 1. Store in Database Episodic Memory
    try:
        from memory.episodic_memory import EpisodicMemory

        ep_mem = EpisodicMemory(db_path=str(SQLITE_DB_PATH))
        ep_mem.store_episode(
            event_type="solution",
            context=problem,
            outcome=solution,
            importance=1.0,
            success=True,
            tags=tags or [],
            metadata={
                "lesson": lesson,
                "task_id": clean_task,
                "status": status,
                "source": "agent_solution_memory",
                "verified": status == "VERIFIED",
            },  # #1747: additive provenance stamping (schema-compatible)
        )
        print(f"âœ… Stored solution [{status}] into Database Episodic Memory for task #{clean_task}.")
    except Exception as err:
        print(f"[INFO] Database storage skipped ({err}), recording to file.")

    # 2. Append to LESSONS_LEARNED.md if not already recorded
    if LESSONS_FILE.exists():
        try:
            content = LESSONS_FILE.read_text(encoding="utf-8", errors="replace")
            new_entry = f"| {now_str} | #{clean_task} | {problem} | {solution} | {lesson} |"
            if clean_task not in content:
                lines = content.splitlines()
                table_idx = -1
                for i, l in enumerate(lines):
                    if l.strip().startswith("| :---"):
                        table_idx = i + 1
                        break
                if table_idx != -1:
                    lines.insert(table_idx, new_entry)
                    LESSONS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    print(f"âœ… Appended entry to LESSONS_LEARNED.md (# {clean_task}).")
                else:
                    with open(LESSONS_FILE, "a", encoding="utf-8") as f:
                        f.write(f"\n{new_entry}\n")
                    print(f"âœ… Appended entry to end of LESSONS_LEARNED.md (# {clean_task}).")
            else:
                print(f"â„¹ï¸ Issue #{clean_task} already present in LESSONS_LEARNED.md.")
        except Exception as err:
            print(f"[ERROR] Failed writing to LESSONS_LEARNED.md: {err}", file=sys.stderr)
            return False

    return True


def record_solution_gap(
    task_id: str,
    problem: str,
    failed_attempts: str,
    missing_capability: str,
    future_path: str,
) -> bool:
    """Record a Solution Gap when no known solution exists to pave the way for future agents."""
    clean_task = task_id.lstrip("#")
    try:
        from memory.episodic_memory import EpisodicMemory

        ep_mem = EpisodicMemory(db_path=str(SQLITE_DB_PATH))
        ep_mem.store_episode(
            event_type="solution_gap",
            context=problem,
            outcome=f"GAP: missing capability '{missing_capability}'. Path: {future_path}",
            importance=0.9,
            success=False,
            tags=["gap", missing_capability],
            metadata={
                "task_id": clean_task,
                "failed_attempts": failed_attempts,
                "missing_capability": missing_capability,
                "future_path": future_path,
                "status": "GAP",
                "source": "agent_solution_memory",
            },  # #1747: additive provenance stamping (schema-compatible)
        )
        print(f"ðŸ§­ Solution Gap [GAP-{clean_task}] recorded in Database Memory:")
        print(f"   Missing Capability: {missing_capability}")
        print(f"   Future Recommended Path: {future_path}")
        return True
    except Exception as err:
        # EpisodicMemory is an optional runtime adapter.  Keep gap recording
        # best-effort, matching record_solution, so a missing adapter does not
        # report a valid gap submission as a command failure.
        print(f"[WARN] Episodic gap storage skipped ({err}); continuing.", file=sys.stderr)
        return True


def verify_mcp() -> bool:
    """Verify MCP Control Tower connection contract."""
    print("ðŸ” Checking SupremeAI MCP Tower connection contract...")
    
    # 1. Check workspace config (mcp.json)
    if MCP_CONFIG_FILE.exists():
        try:
            cfg = json.loads(MCP_CONFIG_FILE.read_text(encoding="utf-8"))
            servers = cfg.get("mcpServers", {})
            if "supremeai-control-tower" in servers:
                print("âœ… Valid MCP Tower contract found in mcp.json.")
                return True
        except Exception:
            pass

    # 2. Check environment variable contract
    mcp_env = os.environ.get("MCP_TOWER_URL", os.environ.get("MCP_SERVER_URL", ""))
    if mcp_env:
        print("âœ… Valid MCP Tower contract found in environment (MCP_TOWER_URL).")
        return True

    print("âŒ No valid MCP Tower contract found (checked mcp.json and MCP_TOWER_URL).", file=sys.stderr)
    return False



def record_strategic_decision(
    task_id,
    decision,
    what_not_to_do,
    why_not,
    source_legitimacy='',
    source_legitimacy_audit=None,
    agent='',
    tags=None,
    **kwargs,
) -> bool:
    tid = str(task_id).strip().lstrip('#')
    if not all(str(x).strip() for x in (tid, decision, what_not_to_do, why_not)):
        return False
    audit = source_legitimacy if source_legitimacy_audit is None else source_legitimacy_audit
    entry = {
        'task_id': tid,
        'decision': decision,
        'what_not_to_do': what_not_to_do,
        'why_not': why_not,
        'source_legitimacy_audit': audit,
        'agent': agent,
        'tags': list(tags) if tags else [],
    }
    try:
        STRATEGIC_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STRATEGIC_FILE, 'a', encoding='utf-8') as f:
            f.write(__import__('json').dumps(entry, ensure_ascii=False) + chr(10))
    except Exception:
        return False
    return True


def search_strategic_memory(query, limit=5, **kwargs):
    if not query or not str(query).strip():
        return []
    try:
        lim = int(limit)
    except (TypeError, ValueError):
        lim = 5
    if lim <= 0:
        return []
    terms = [t for t in str(query).lower().split() if t]
    if not terms:
        return []
    term_set = set(terms)
    if not STRATEGIC_FILE.exists():
        return []
    results = []
    try:
        with open(STRATEGIC_FILE, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = __import__('json').loads(line)
                except Exception:
                    continue
                if not isinstance(entry, dict):
                    continue
                text = ' '.join([
                    str(entry.get('decision', '')),
                    str(entry.get('what_not_to_do', '')),
                    str(entry.get('why_not', '')),
                    ' '.join(str(t) for t in (entry.get('tags') or [])),
                    str(entry.get('agent', '')),
                ]).lower()
                score = sum(1 for t in term_set if t in text)
                if score > 0:
                    r = dict(entry)
                    r['score'] = score
                    results.append(r)
    except Exception:
        return []
    results.sort(key=lambda r: r.get('score', 0), reverse=True)
    return results[:lim]


def format_strategic_block(entries):
    if not entries:
        return ''
    lines = ['## Strategic Red Lines', '']
    for e in entries:
        tid = e.get('task_id', '')
        lines.append('- #' + str(tid) + ': ' + str(e.get('what_not_to_do', '')))
        lines.append('  - Why not: ' + str(e.get('why_not', '')))
        lines.append('  - Source: ' + str(e.get('source_legitimacy_audit', '')))
    return chr(10).join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SupremeAI Collective Agent Memory & Problem-Solving Layer CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Search Command
    search_parser = subparsers.add_parser("search", help="Search past solutions by problem or error query")
    search_parser.add_argument("--query", "-q", required=True, help="Error message, symptom, or task description")

    # Record Command
    record_parser = subparsers.add_parser("record", help="Record newly validated solution for future agents")
    record_parser.add_argument("--task-id", required=True, help="GitHub Issue ID or task identifier")
    record_parser.add_argument("--problem", required=True, help="Problem summary or error signature")
    record_parser.add_argument("--solution", required=True, help="Exact validated solution recipe")
    record_parser.add_argument("--lesson", required=True, help="Prevention rule / lesson learned")
    record_parser.add_argument("--status", default="VERIFIED", choices=["UNVERIFIED", "EXPERIMENTAL", "VERIFIED", "RECOMMENDED"], help="Trust status")
    record_parser.add_argument("--tags", default="", help="Comma-separated tags")

    # Gap Command (Path B)
    gap_parser = subparsers.add_parser("gap", help="Record a Solution Gap when no solution yet exists")
    gap_parser.add_argument("--task-id", required=True, help="GitHub Issue ID or task identifier")
    gap_parser.add_argument("--problem", required=True, help="Problem summary or symptom")
    gap_parser.add_argument("--failed-attempts", required=True, help="What previous approaches were tried and failed")
    gap_parser.add_argument("--missing-capability", required=True, help="Missing system or tool capability")
    gap_parser.add_argument("--future-path", required=True, help="Recommended next path for future agents")

    # Verify MCP Command
    subparsers.add_parser("verify-mcp", help="Verify MCP Control Tower connection contract")

    args = parser.parse_args()

    if args.command == "search":
        print(f"ðŸ” Searching SupremeAI Collective Memory for: '{args.query}'...\n")
        lessons = search_local_lessons(args.query)
        db_hits = search_database_memory(args.query)

        if not lessons and not db_hits:
            print("âš ï¸ No exact previous solutions found in system memory.")
            print("ðŸ‘‰ Recommendation: Check available capabilities, or record a Solution Gap ('gap') if missing tools!")
            return 0

        print(f"Found {len(lessons) + len(db_hits)} potential reference(s):\n")
        if lessons:
            print("ðŸ“‹ Matches from LESSONS_LEARNED.md:")
            for hit in lessons:
                print(f"  â€¢ {hit['text']}")
            print()
        if db_hits:
            print("ðŸ§  Matches from Database Episodic Memory:")
            for hit in db_hits:
                print(f"  â€¢ ({hit.get('tier', 'local')}) [{hit['type'].upper()} #{hit['task_id']}] {hit['problem']} -> {hit['solution']}")
            print()

        return 0

    elif args.command == "record":
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        success = record_solution(
            task_id=args.task_id,
            problem=args.problem,
            solution=args.solution,
            lesson=args.lesson,
            status=args.status,
            tags=tags,
        )
        return 0 if success else 1

    elif args.command == "gap":
        success = record_solution_gap(
            task_id=args.task_id,
            problem=args.problem,
            failed_attempts=args.failed_attempts,
            missing_capability=args.missing_capability,
            future_path=args.future_path,
        )
        return 0 if success else 1

    elif args.command == "verify-mcp":
        return 0 if verify_mcp() else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())



