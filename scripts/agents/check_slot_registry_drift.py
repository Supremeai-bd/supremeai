#!/usr/bin/env python3
"""check_slot_registry_drift.py — single-source-of-truth gate for slot governance.

#1821: the agent slot -> role mapping historically existed in FIVE conflicting
copies. This gate enforces that `docs/master_docs/AGENT_SLOT_REGISTRY.yaml`
is the ONLY source of truth and every other surface agrees with (or derives
from) it:

  1. backend/core/agent_registry.json   -> must NOT claim slots/branches/merge authority
  2. scripts/agents/dispatch_task_all_agents.py -> roles must be YAML-derived (resolve_active_agents)
  3. docs/agents/heartbeat-integration.md -> slot/tool table must match the YAML
  4. scripts/agents/agent_bot_registry.py -> must stay deleted (5th conflicting copy)
  5. scripts/git/push_as_agent.py         -> bot-credential map only (no role claims)
  6. scripts/agents/credential_manager.py  -> SSOT bot-credential map (#2644):
     roles must derive from the YAML role_pools (or the auditor alias of the
     planner-and-auditor pool); push_as_agent must IMPORT, not inline it.

Exit codes: 0 = no drift, 1 = drift detected (push/CI must fail).

Usage:
    python3 scripts/agents/check_slot_registry_drift.py            # human output
    python3 scripts/agents/check_slot_registry_drift.py --quiet    # gate mode
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
YAML_PATH = REPO_ROOT / "docs" / "master_docs" / "AGENT_SLOT_REGISTRY.yaml"
JSON_REGISTRY_PATH = REPO_ROOT / "backend" / "core" / "agent_registry.json"
DISPATCH_PATH = REPO_ROOT / "scripts" / "agents" / "dispatch_task_all_agents.py"
HEARTBEAT_DOC_PATH = REPO_ROOT / "docs" / "agents" / "heartbeat-integration.md"
DEAD_REGISTRY_PATH = REPO_ROOT / "scripts" / "agents" / "agent_bot_registry.py"
PUSH_AS_AGENT_PATH = REPO_ROOT / "scripts" / "git" / "push_as_agent.py"
CREDENTIAL_MANAGER_PATH = REPO_ROOT / "scripts" / "agents" / "credential_manager.py"

issues: list[str] = []


def fail(msg: str) -> None:
    issues.append(msg)


def load_yaml_slots() -> dict:
    """Return {slot_id: {'tool': str, 'active': bool}} from the governance YAML."""
    import yaml

    data = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))
    slots: dict = {}
    for slot in data.get("slots", []):
        slot_id = str(slot.get("slot", ""))
        if slot_id.startswith("agent-"):
            slots[slot_id] = {
                "tool": str(slot.get("tool", "")).strip(),
                "active": bool(slot.get("active", False)),
            }
    return slots


def check_json_registry() -> None:
    """agent_registry.json must be persona metadata only — zero governance claims."""
    if not JSON_REGISTRY_PATH.exists():
        return  # deleted entirely is also fine
    text = JSON_REGISTRY_PATH.read_text(encoding="utf-8")
    data = json.loads(text)
    for name, entry in data.items():
        if not isinstance(entry, dict):
            continue
        if (
            "metadata" in entry
            and isinstance(entry["metadata"], dict)
            and entry["metadata"].get("slot")
        ):
            fail(
                f"agent_registry.json: entry '{name}' has metadata.slot — slot claims belong to the governance YAML"
            )
        if "merge_pull_requests" in entry.get("permissions", []):
            fail(
                f"agent_registry.json: entry '{name}' claims 'merge_pull_requests' — merge authority is governed by the charter/pr-helper lane"
            )
        for field in ("description", "system_prompt"):
            val = str(entry.get(field, ""))
            if re.search(r"[Pp]ersistent branch:\s*agent-\d+", val):
                fail(
                    f"agent_registry.json: entry '{name}' {field} claims a persistent branch — branch slots belong to the governance YAML"
                )


def check_dispatch_script() -> None:
    """Dispatch roles must come from resolve_active_agents (YAML-derived)."""
    if not DISPATCH_PATH.exists():
        return
    text = DISPATCH_PATH.read_text(encoding="utf-8")
    if "resolve_active_agents" not in text:
        fail(
            "dispatch_task_all_agents.py: no resolve_active_agents() — role map must be derived from the governance YAML"
        )
    if re.search(r"active_agents\s*=\s*\{", text):
        fail(
            "dispatch_task_all_agents.py: hardcoded active_agents dict found — roles must come from resolve_active_agents() (YAML)"
        )
    # The YAML-derived resolver must agree with the YAML right now.
    sys.path.insert(0, str(DISPATCH_PATH.parent))
    try:
        # Import without executing asyncio.run (module __main__ guard protects us).
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "dispatch_task_all_agents", DISPATCH_PATH
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        resolved = mod.resolve_active_agents()
        yaml_slots = load_yaml_slots()
        for slot_id, info in resolved.items():
            want = yaml_slots.get(slot_id, {}).get("tool")
            if want is None:
                fail(
                    f"dispatch_task_all_agents.py: resolved slot '{slot_id}' is not in the governance YAML"
                )
            elif info["role"] != want:
                fail(
                    f"dispatch_task_all_agents.py: slot '{slot_id}' role '{info['role']}' != YAML tool '{want}'"
                )
        for slot_id, info in yaml_slots.items():
            if info["active"] and slot_id not in resolved:
                fail(
                    f"dispatch_task_all_agents.py: active YAML slot '{slot_id}' missing from resolved map"
                )
    except Exception as exc:  # noqa: BLE001 — gate must never crash silently
        fail(f"dispatch_task_all_agents.py: could not verify YAML derivation ({exc})")
    finally:
        sys.path.pop(0)


def check_heartbeat_doc() -> None:
    """Every slot row in the integration table must match the YAML tool + active flag."""
    if not HEARTBEAT_DOC_PATH.exists():
        return
    yaml_slots = load_yaml_slots()
    row_re = re.compile(r"^\|\s*(agent-\d+)\s*\|([^|]*)\|([^|]*)\|")
    seen: set[str] = set()
    for raw in HEARTBEAT_DOC_PATH.read_text(encoding="utf-8").splitlines():
        m = row_re.match(raw.strip())
        if not m:
            continue
        slot_id, tool_cell, active_cell = (
            m.group(1),
            m.group(2).strip(),
            m.group(3).strip(),
        )
        if slot_id not in yaml_slots:
            continue  # table may document retired slots; YAML governs live slots
        seen.add(slot_id)
        want_tool, want_active = (
            yaml_slots[slot_id]["tool"],
            yaml_slots[slot_id]["active"],
        )
        if want_tool and not tool_cell.startswith(want_tool):
            fail(
                f"heartbeat-integration.md: row {slot_id} tool '{tool_cell}' != YAML '{want_tool}'"
            )
        row_active = "✅" in active_cell or "✅" in tool_cell
        if row_active != want_active:
            state = "✅ active" if want_active else "❌ standby"
            fail(
                f"heartbeat-integration.md: row {slot_id} active flag ({'✅' if row_active else '❌'}) != YAML ({state})"
            )


def check_dead_registry() -> None:
    if DEAD_REGISTRY_PATH.exists():
        fail(
            "scripts/agents/agent_bot_registry.py still exists — the 5th conflicting registry copy must stay deleted (#1821)"
        )


def check_push_as_agent() -> None:
    """push_as_agent.py may hold bot CREDENTIALS only — no role/branch claims."""
    if not PUSH_AS_AGENT_PATH.exists():
        return
    text = PUSH_AS_AGENT_PATH.read_text(encoding="utf-8")
    if re.search(
        r"(?:from\s+agent_bot_registry\s+import|import\s+agent_bot_registry)", text
    ):
        fail("push_as_agent.py: still imports the deleted agent_bot_registry")
    if re.search(r'"role"\s*:', text):
        fail(
            "push_as_agent.py: claims role mapping — roles belong to the governance YAML"
        )
    # (#2644) SSOT: the slot→app map moved to credential_manager.py — an
    # inline copy here would resurrect the #1821 5th-registry drift class.
    if re.search(r"BOT_SLOT_CREDENTIALS\s*=\s*\{", text):
        fail(
            "push_as_agent.py: inline BOT_SLOT_CREDENTIALS found — import it from "
            "scripts/agents/credential_manager.py (SSOT, #2644)"
        )


def check_credential_manager() -> None:
    """#2644 SSOT gate: credential_manager's routing table must derive from
    the governance YAML — roles from role_pools (auditor = planner-and-auditor
    pool alias), bot identities in the supremeai-* family."""
    if not CREDENTIAL_MANAGER_PATH.exists():
        return
    import yaml

    text = CREDENTIAL_MANAGER_PATH.read_text(encoding="utf-8")
    data = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8")) or {}
    pool_roles = set((data.get("role_pools") or {}).keys())
    # planner-and-auditor is one pool (#2644 §2: audit agents share it)
    allowed_roles = pool_roles | {"auditor"}

    # BOT_SLOT_CREDENTIALS entries: parse the dict literal's bot_name/role lines
    block = re.search(
        r"BOT_SLOT_CREDENTIALS\s*=\s*\{(.*?)\n\}", text, re.DOTALL
    )
    if not block:
        fail("credential_manager.py: BOT_SLOT_CREDENTIALS table not found")
        return
    body = block.group(1)
    for m in re.finditer(r'"bot_name":\s*"([^"]+)"', body):
        if not m.group(1).startswith("supremeai-"):
            fail(
                f"credential_manager.py: bot_name '{m.group(1)}' outside the "
                "supremeai-* app family (governance YAML owns identities)"
            )
    for m in re.finditer(r'"role":\s*"([^"]+)"', body):
        if m.group(1) not in allowed_roles:
            fail(
                f"credential_manager.py: role '{m.group(1)}' is not a role_pools "
                "key in AGENT_SLOT_REGISTRY.yaml (or the 'auditor' alias) — "
                "roles belong to the governance YAML"
            )


def check_tower_live_drift() -> None:
    """ROOT-CAUSE FIX (#2723): verify the YAML registry against the LIVE tower.

    Previously this gate only checked file-to-file consistency (YAML vs JSON vs
    docs) — it NEVER connected to the live MCP tower to verify that slots
    marked `active: true` actually have a registered agent. Result: 6 slots
    marked active in the YAML were absent from the tower, and 3 agentIds
    diverged. This check now queries the tower's agent list via the same
    mcp_tower_client.py the agents use, and flags:
      - active slots with no tower agent
      - tower agents with no registry entry
      - agentId mismatches (registry tool name vs tower agentId)

    Graceful: if MCP_TOWER_URL is unset or the tower is unreachable, this
    check is SKIPPED (not failed) — matches AGENTS.md Step 2 "graceful offline
    fallback". The file-consistency checks above still run.
    """
    import os
    import subprocess

    tower_url = os.environ.get("MCP_TOWER_URL") or os.environ.get("MCP_SERVER_URL")
    if not tower_url:
        # No tower configured (local dev, CI without secrets) — skip live check
        return

    # Query the tower via mcp_tower_client.py status (JSON-parseable output)
    try:
        result = subprocess.run(
            ["python3", str(REPO_ROOT / "scripts" / "agents" / "mcp_tower_client.py"), "status"],
            capture_output=True, text=True, timeout=30, check=False,
            env={**os.environ, "MCP_TOWER_URL": tower_url},
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        # Tower unreachable — graceful skip (offline fallback, AGENTS.md Rule #3)
        return

    if result.returncode != 0:
        # Tower returned error — graceful skip, don't fail CI on tower outage
        return

    # Parse tower agents: lines like "  agent-3    state=online    agentId=supremeai-coder-1-bot"
    import re
    tower_agents: dict[str, dict[str, str]] = {}
    for line in result.stdout.splitlines():
        m = re.match(r"^\s+(agent-\d+)\s+state=(\w+)\s+agentId=(.+)$", line)
        if m:
            slot, state, agent_id = m.group(1), m.group(2), m.group(3).strip()
            tower_agents[slot] = {"state": state, "agentId": agent_id}

    if not tower_agents:
        return  # tower returned no agents — nothing to compare

    yaml_slots = load_yaml_slots()

    # Check 1: active YAML slots missing from tower
    for slot_id, info in yaml_slots.items():
        if info.get("active") and slot_id not in tower_agents:
            fail(
                f"tower-drift: slot '{slot_id}' marked active=true in YAML but "
                f"ABSENT from live tower (never registered or purged)"
            )

    # Check 2: tower agents not in YAML registry
    for slot_id in tower_agents:
        if slot_id not in yaml_slots:
            fail(
                f"tower-drift: tower has agent '{slot_id}' "
                f"(agentId={tower_agents[slot_id]['agentId']}) but YAML registry has no entry"
            )

    # Check 3: agentId mismatches (registry tool name vs tower agentId)
    # YAML 'tool' field is the canonical name; tower 'agentId' is what the
    # agent registered as. They should match (or the tower agentId should
    # contain the YAML tool name as a prefix/suffix).
    for slot_id, tower_info in tower_agents.items():
        if slot_id in yaml_slots:
            yaml_tool = yaml_slots[slot_id].get("tool", "")
            tower_aid = tower_info["agentId"]
            # Allow partial match (e.g. YAML "coder-1" vs tower "supremeai-coder-1-bot")
            # Also allow tower agentId to have a suffix like " (git PR merge & regression)"
            tower_aid_base = tower_aid.split(" (")[0].strip()
            if yaml_tool and yaml_tool not in tower_aid_base and tower_aid_base not in yaml_tool:
                fail(
                    f"tower-drift: slot '{slot_id}' agentId mismatch — "
                    f"YAML tool='{yaml_tool}' vs tower agentId='{tower_aid}'"
                )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", action="store_true", help="print failures only")
    parser.add_argument("--skip-tower", action="store_true",
                        help="skip live tower drift check (offline/CI without MCP_TOWER_URL)")
    args = parser.parse_args()

    if not YAML_PATH.exists():
        print(f"❌ governance YAML missing: {YAML_PATH}")
        return 1

    check_json_registry()
    check_dispatch_script()
    check_heartbeat_doc()
    check_dead_registry()
    check_push_as_agent()
    check_credential_manager()
    if not args.skip_tower:
        check_tower_live_drift()

    if issues:
        print(
            f"❌ [slot-registry-drift] {len(issues)} drift violation(s) vs AGENT_SLOT_REGISTRY.yaml (#1821):"
        )
        for i in issues:
            print(f"   - {i}")
        print(
            "   Fix: make the offending file agree with docs/master_docs/AGENT_SLOT_REGISTRY.yaml."
        )
        return 1

    if not args.quiet:
        print(
            "✅ [slot-registry-drift] all registry surfaces agree with AGENT_SLOT_REGISTRY.yaml (single source of truth)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
