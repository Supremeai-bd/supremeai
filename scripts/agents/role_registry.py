#!/usr/bin/env python3
"""Role Registry & Dynamic Prompt composer (Roadmap v2.0 Phase 1/2/4/6 — #4143).

A read-only VIEW over EXISTING sources of truth — this module adds NO new SSOT:

  authority     → AUTHORITY_TIERS (here) — Phase 4's simple 3-tier matrix,
                  hard-coded + deterministic (NOT a 100-rule policy framework;
                  deterministic gates always outrank it — constitution §1.4)
  verification  → VERIFICATION_REQUIREMENTS (here)
  allowed tools → credential_manager.TASK_SCOPED_ENV_KEYS (env allowlist, #2644/#4134)
  GH scopes     → credential_manager.BOT_SLOT_CREDENTIALS (SSOT, #1821/#2644)
  constraints   → AGENT_RULES.md §3 "Role Policy Contracts" (parsed LIVE —
                  prose stays the single source for role policy text)

Phase 2.2 Dynamic Prompt = Role + authority + verification + tools + task.
Phase 6   plan_task_execution = Rule B single-vs-multi advisory planner
          (logging/contract use only — execution authority is unchanged).

Zero secrets are ever returned (env KEY NAMES and GitHub scope NAMES only).
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_RULES_PATH = REPO_ROOT / "AGENT_RULES.md"

# ─────────────── Phase 4: simple authority matrix (deterministic) ───────────────
# Three tiers, per Roadmap v2.0: Autonomous → Governed Autonomous → Human Required.
# governed_autonomous = the role acts alone but its output passes human-owned
# deterministic gates (PR gates, claim gates) before landing on main.
AUTHORITY_TIERS: dict[str, str] = {
    "planner": "autonomous",            # issues:write only — issue-output lane
    "auditor": "autonomous",            # read + issues:write, lease-scoped
    "watcher": "autonomous",            # read + platform health, evidence-backed issues
    "human-eyes": "autonomous",         # read-only browser evidence
    "breaker": "autonomous",            # zero-write adversarial sandbox
    "coder": "governed_autonomous",     # write lane — every PR passes the gate chain
    "pr-helper": "governed_autonomous", # PR lane — gate-governed
    "ci-fixer": "governed_autonomous",  # CI lane — gate-governed
    "platform": "governed_autonomous",  # infra lane — gate-governed
    "merge-agent": "human_required",    # merge authority is human/owner gated
    "super": "human_required",
}

# Role aliases → canonical registry keys (mirrors fleet naming variants).
ROLE_ALIASES: dict[str, str] = {
    "ci": "ci-fixer",
    "browser": "human-eyes",
    "scout": "planner",
    "adversarial": "breaker",
    "merge": "merge-agent",
}

# AGENT_RULES.md §3 headings (verbatim) per canonical role.
_RULES_HEADINGS: dict[str, str] = {
    "auditor": "Auditor",
    "planner": "Ecosystem Scout / Planner",
    "coder": "Coder",
    "ci-fixer": "CI Fixer",
    "watcher": "Watcher",
    "human-eyes": "Human-Eyes / Browser Agent",
    "breaker": "Breaker / Adversarial Auditor",
    "merge-agent": "Merge Agent",
}

# credential_manager uses slightly different role keys (TASK_SCOPED_ENV_KEYS /
# BOT_SLOT_CREDENTIALS) — map canonical → cm key (single source, no duplication).
_CM_ROLE_KEYS: dict[str, str] = {
    "ci-fixer": "ci",
    "human-eyes": "browser",
    "breaker": "rules_breaker",
}

# ─────────────── verification requirement per role (Phase 2.1) ───────────────
VERIFICATION_REQUIREMENTS: dict[str, str] = {
    "coder": "3-tier: reflection grep + live boot smoke + pytest green; Test Evidence section in PR body",
    "ci-fixer": "failed gate re-run green on current commit + recorded evidence",
    "breaker": "reproducible negative evidence (edge/malformed/stress); no production fix unless assigned",
    "auditor": "verified finding + existing issue/PR search + root-cause explanation",
    "planner": "Observation → Evidence → Relevance → smallest useful improvement → impact",
    "watcher": "evidence-backed health/quota/latency issue; approved fallback policy",
    "human-eyes": "reproducible browser journey evidence (steps + screenshot/console)",
    "pr-helper": "gate verdicts + evidence; scope conformance",
    "merge-agent": "evaluate-only verdict: READY / BLOCKED / REISSUE",
}

_CONSTRAINTS_CACHE: list[tuple[str, list[str]]] | None = None


class UnknownRoleError(ValueError):
    """Raised for roles outside the registry (typo or unregistered lane)."""


def canonical_role(role: str) -> str:
    """Normalize a role/alias to its canonical registry key."""
    r = (role or "").strip().lower()
    r = ROLE_ALIASES.get(r, r)
    # tolerate agent-name-ish inputs ("coder-1", "supremeai-coder-1")
    for known in AUTHORITY_TIERS:
        if r == known or r.startswith(known + "-") or r.endswith("-" + known):
            return known
    if r in AUTHORITY_TIERS:
        return r
    raise UnknownRoleError(
        f"unknown role '{role}' (known: {sorted(AUTHORITY_TIERS)}; aliases: {sorted(ROLE_ALIASES)})"
    )


def _parse_role_constraints() -> list[tuple[str, list[str]]]:
    """Parse AGENT_RULES.md §3 role sections once: [(heading, [lines])]."""
    global _CONSTRAINTS_CACHE
    if _CONSTRAINTS_CACHE is not None:
        return _CONSTRAINTS_CACHE
    sections: list[tuple[str, list[str]]] = []
    try:
        text = AGENT_RULES_PATH.read_text(encoding="utf-8")
    except OSError:
        _CONSTRAINTS_CACHE = sections
        return sections
    start = text.find("# 3. Role Policy Contracts")
    end = text.find("# 4.", start + 1) if start >= 0 else -1
    body = text[start:end if end > start else len(text)] if start >= 0 else ""
    current: tuple[str, list[str]] | None = None
    for line in body.splitlines():
        if line.startswith("## "):
            if current:
                sections.append(current)
            current = (line[3:].strip(), [])
        elif current and line.strip() and not line.strip() == "---":
            current[1].append(line.strip())
    if current:
        sections.append(current)
    _CONSTRAINTS_CACHE = sections
    return sections


def role_constraints(role: str, max_lines: int = 6) -> list[str]:
    """Live-parsed constraint lines for a role from AGENT_RULES.md §3."""
    role = canonical_role(role)
    heading = _RULES_HEADINGS.get(role, role.replace("-", " ").title())
    for h, lines in _parse_role_constraints():
        if h.lower() == heading.lower():
            return lines[:max_lines]
    return []


def gh_scopes_for(role: str) -> list[str]:
    """GitHub scopes for the role from BOT_SLOT_CREDENTIALS (names only)."""
    from scripts.agents.credential_manager import BOT_SLOT_CREDENTIALS

    cm_role = _CM_ROLE_KEYS.get(canonical_role(role), canonical_role(role))
    for cfg in BOT_SLOT_CREDENTIALS.values():
        if cfg.get("role") == cm_role:
            return list(cfg.get("scopes", []))
    return []


def get_role_contract(role: str) -> dict:
    """One per-role contract composed from the existing SSOTs (no secrets)."""
    role = canonical_role(role)
    from scripts.agents.credential_manager import TASK_SCOPED_ENV_KEYS

    cm_role = _CM_ROLE_KEYS.get(role, role)
    if cm_role not in TASK_SCOPED_ENV_KEYS:
        raise UnknownRoleError(f"no scoped-env contract for role '{role}'")
    return {
        "role": role,
        "authority": AUTHORITY_TIERS[role],
        "verification": VERIFICATION_REQUIREMENTS.get(role, "follow issue Verification Contract"),
        "allowed_env_keys": sorted(TASK_SCOPED_ENV_KEYS[cm_role]),
        "gh_scopes": gh_scopes_for(role),
        "constraints": role_constraints(role),
        "rules_source": "AGENT_RULES.md#3-role-policy-contracts",
    }


def build_dynamic_prompt(role: str, task: str) -> str:
    """Phase 2.2 Dynamic Prompt — composed per task, not a giant static prompt."""
    c = get_role_contract(role)
    lines = [
        f"ROLE: {c['role']} (authority: {c['authority']})",
        f"VERIFICATION REQUIRED: {c['verification']}",
        f"ALLOWED TOOLS/ENV KEYS: {', '.join(c['allowed_env_keys'])}",
    ]
    if c["gh_scopes"]:
        lines.append(f"GITHUB SCOPES: {', '.join(c['gh_scopes'])}")
    if c["constraints"]:
        lines.append("CONSTRAINTS (from AGENT_RULES.md §3):")
        lines += [f"  - {cl}" for cl in c["constraints"]]
    lines.append(f"TASK: {task.strip()}")
    lines.append(
        "BOUNDARY: deterministic gates outrank any AI preference "
        "(constitution §1.4) — AI consensus never overrides a deterministic gate."
    )
    return "\n".join(lines)


# ─────────────── Phase 6 (planning half): Rule B composition planner ───────────────

_SECURITY_HINTS = (
    "security", "vulnerab", "auth bypass", "injection", "xss", "csrf",
    "secret", "exploit", "credential", "privilege",
)
_LARGE_HINTS = (
    "architecture", "migration", "investigation", "overhaul",
    "redesign", "large refactor", "multi-layer",
)


def plan_task_execution(task_text: str, labels: list[str] | None = None) -> dict:
    """Rule B advisory planner: single agent, or decompose with rationale.

    Multi-agent ONLY when at least one real benefit exists (independent
    verification / specialization / large decomposition). Advisory output —
    the caller logs it into the task contract; execution authority unchanged.
    """
    text = (task_text or "").lower()
    label_set = {str(l).lower().lstrip("@") for l in (labels or [])}
    if any(h in text for h in _SECURITY_HINTS) or "security" in label_set:
        return {
            "mode": "multi",
            "agents": ["coder", "breaker"],
            "verification": "independent adversarial review (breaker) + pytest green",
            "rationale": "security-sensitive work benefits from adversarial verification (Rule B)",
        }
    if any(h in text for h in _LARGE_HINTS) or "large" in label_set:
        return {
            "mode": "multi_decompose",
            "agents": ["planner", "coder"],
            "verification": "synthesis review + tiered tests",
            "rationale": "large decomposition benefits from planning + specialist split (Rule B)",
        }
    return {
        "mode": "single",
        "agents": ["coder"],
        "verification": "issue Verification Contract (3-tier)",
        "rationale": "one reliable agent is the simplest sufficient solution (Rule A/B)",
    }


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) >= 2:
        print(json.dumps(get_role_contract(sys.argv[1]), indent=1))
    else:
        print("usage: role_registry.py <role>")
    sys.exit(0)
