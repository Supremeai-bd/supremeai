#!/usr/bin/env python3
"""MCP access-policy deny-matrix guard (offline, static, fail-closed).

Pins the Single-Door SSOT declared in
``infrastructure/mcp-control-plane/src/policy/mcp-access.ts`` so the
zero-credential exposure class witnessed live in issue #1843 can never
re-enter through a source edit.

Background (#1843, probed live 2026-10-28T00:20-00:35Z): the DEPLOYED tower
executed five secret/internal-class tools for anonymous public_viewer callers
(``github_list_secrets``, ``supabase_read_table``, ``redis_read_key``,
``memory_read_graph``, ``tenant_list``) while the in-repo mirror correctly
denies them. The in-repo file is the SSOT; the deployed build drifted. The
deployment-side reconciliation is admin-lane. THIS guard pins the source side
so no future edit can silently widen the public surface:

  1. public_viewer early-return requires the CONJUNCTION
     access "safe" AND dataClassification "public" (default-deny core).
  2. Rank ladder, pinned SEMANTICALLY (see _check_rank_ladder): the secret
     threshold must be at least the rank of `admin` and the restricted
     threshold at least the rank of `agent`, both read from ROLE_RANK in
     auth.context.ts. The ladder was consolidated from six tiers to four
     0-based ranks (#110/#474) and the numbers moved; pinning literals made the
     guard report a security regression that did not exist, so the guard now
     pins the RELATIONSHIP between the thresholds and the declared ranks.
  3. classifyToolCapability's default fallback stays
     access "restricted" + dataClassification "internal" (unknown/dynamic
     tools deny public_viewer by construction).
  4. The five #1843 over-exposure tools are never classified safe/public and
     never appear in publicSafeCapabilities; github_list_secrets stays pinned
     in an explicit restricted+secret (R4) block.
  5. Every publicSafeCapabilities entry carries access "safe" AND
     dataClassification "public" (array purity = advertised manifest honesty).

ADMIN RECIPE (deployment-side reconciliation - not bridge-able, .github/ and
live infra are admin-owned; apply after landing this guard):

  1. Rebuild + redeploy the MCP Control Tower from this SSOT
     (infrastructure/mcp-control-plane). The running build predates the
     current classifyToolCapability and executes the five #1843 tools
     anonymously; the rebuilt gate must return
     "Forbidden: tool '<name>' requires ... (default-deny RBAC)" for each.
  2. Verify with an anonymous (zero-Bearer) deny-matrix probe:
     every non-public capability => Forbidden; the documented self-serve set
     (system_summary/system_health/status, bridge_*, work_claim,
     supabase_schema_inspect, agent_status/agent_heartbeat) still reachable.
     Audit honesty note from #1843: zod schema-validation denials are NOT
     RBAC denials - probe with schema-valid args or the probe lies to you.
  3. render_get_env_vars (secret/R4) held correctly live - use its denial as
     the reference shape when diffing post-redeploy behavior.
  4. If secret-NAME inventory disclosure matters operationally, rotate/
     reshuffle the 13 disclosed GitHub Actions secret names
     (e.g. BRIDGE_DISPATCH_TOKEN) after redeploy.

Honest-degradation is deliberately NOT implemented here: a missing or
restructured SSOT is itself a red condition (fail-closed, exit 1 with
evidence). Never guess around an unreadable policy file.

Usage:
  python scripts/ci/mcp_access_policy_guard.py            # check real SSOT
  python scripts/ci/mcp_access_policy_guard.py --check
  python scripts/ci/mcp_access_policy_guard.py --policy <path>
  python scripts/ci/mcp_access_policy_guard.py --self-test

Exit codes: 0 = all invariants hold; 1 = violation/missing/unparseable SSOT;
2 = self-test harness misuse.
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = REPO_ROOT / "infrastructure" / "mcp-control-plane" / "src" / "policy" / "mcp-access.ts"

# The five tools witnessed executing anonymously against the deployed tower
# (#1843). Each must remain denied to public_viewer in the SSOT.
OVEREXPOSED_TOOLS = [
    "github_list_secrets",
    "supabase_read_table",
    "redis_read_key",
    "memory_read_graph",
    "tenant_list",
]

# Tools that must stay explicitly pinned in a restricted+secret (R4) block.
SECRET_FAMILY_EXPLICIT = ["github_list_secrets"]


def _function_body(source: str, signature: str) -> str | None:
    """Return the body of the top-level function starting with *signature*."""
    idx = source.find(signature)
    if idx == -1:
        return None
    end = source.find("\n}", idx)
    return source[idx:end if end != -1 else len(source)]


def _return_object_block_after(source: str, anchor: str) -> str | None:
    """Return the first ``return { ... }`` object-literal block following *anchor*."""
    idx = source.find(anchor)
    if idx == -1:
        return None
    ret = source.find("return {", idx)
    if ret == -1:
        return None
    end = source.find("};", ret)
    if end == -1:
        return None
    return source[ret:end]


def _check_public_viewer_predicate(source: str) -> list[str]:
    violations: list[str] = []
    # The public_viewer branch returns a boolean EXPRESSION (not an object
    # literal), so extract the if-block body directly.
    m = re.search(r'if \((?:context\.)?mode === "public_viewer"\) \{\s*\n(.*?)\n\s*\}', source, re.DOTALL)
    if not m:
        violations.append('public_viewer early-return branch not found (SSOT restructured - update guard, do not weaken)')
        return violations
    branch = m.group(1)
    # Pin the CONJUNCTION: weakening && to || still contains both conjuncts
    # but widens the public surface - the paired form is the invariant.
    if not re.search(r'access === "safe"\s*&&\s*(?:capability\.)?dataClassification === "public"', branch):
        violations.append('public_viewer gate is not the conjunction access==="safe" && dataClassification==="public" (default-deny core weakened)')
    return violations


def parse_role_rank(text: str) -> dict[str, int]:
    """Extract the `ROLE_RANK` ladder (`viewer: 0, agent: 1, ...`) from a source."""
    block = re.search(r"ROLE_RANK[^=]*=\s*\{(.*?)\}\s*as const", text, re.DOTALL)
    if block is None:
        block = re.search(r"ROLE_RANK[^=]*=\s*\{(.*?)\}", text, re.DOTALL)
    if block is None:
        return {}
    return {
        role: int(value)
        for role, value in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(\d+)", block.group(1))
    }


def load_role_rank(policy_path: Path) -> tuple[dict[str, int], str | None]:
    """Read the RBAC ladder from auth.context.ts (sibling) or the policy file."""
    for candidate in (policy_path.parent / "auth.context.ts", policy_path):
        if not candidate.is_file():
            continue
        try:
            ranks = parse_role_rank(candidate.read_text(encoding="utf-8"))
        except OSError as exc:
            return {}, f"ROLE_RANK unreadable in {candidate.name} ({exc})"
        if ranks:
            return ranks, None
    return (), (
        "ROLE_RANK ladder not found next to the SSOT (auth.context.ts) - fail-closed: "
        "the rank thresholds below cannot be verified without it"
    )


def _check_rank_ladder(source: str, ranks: dict[str, int]) -> list[str]:
    """Pin the ladder SEMANTICALLY: thresholds vs the declared role ranks.

    Literal numbers are not an invariant — the ladder was renumbered from six
    1-based tiers to four 0-based ranks (#110/#474, `ROLE_RANK` in
    auth.context.ts) while the policy meaning stayed identical. Pinning `>= 4`
    made this guard report an admin-only leak that did not exist; pinning the
    relationship cannot be fooled by a renumber, and still catches a real
    weakening (secret opened up to `agent`, restricted opened up to `viewer`).
    """
    violations: list[str] = []
    body = _function_body(source, "export function canAccessCapability")
    if body is None:
        return ["canAccessCapability not found in SSOT (fail-closed)"]
    for missing in ("admin", "agent", "viewer"):
        if missing not in ranks:
            return [f"ROLE_RANK has no `{missing}` rank - fail-closed (cannot verify the ladder)"]

    secret = re.search(r'dataClassification === "secret"\s*\)\s*return rank >= (\d+)', body)
    restricted = re.search(r'access === "restricted"\s*\)\s*return rank >= (\d+)', body)
    if secret is None:
        violations.append(
            'secret classification no longer maps to a rank threshold in canAccessCapability'
        )
    elif int(secret.group(1)) < ranks["admin"]:
        violations.append(
            f"secret classification is reachable below `admin` in canAccessCapability "
            f"(threshold {secret.group(1)} < admin rank {ranks['admin']}) - admin-only data "
            "must not reach a lower role"
        )
    if restricted is None:
        violations.append(
            'restricted access no longer maps to a rank threshold in canAccessCapability'
        )
    elif int(restricted.group(1)) < ranks["agent"]:
        violations.append(
            f"restricted access is reachable below `agent` in canAccessCapability "
            f"(threshold {restricted.group(1)} < agent rank {ranks['agent']})"
        )
    for label, match in (("secret", secret), ("restricted", restricted)):
        if match is not None and int(match.group(1)) <= ranks["viewer"]:
            violations.append(
                f"{label} threshold {match.group(1)} is at or below the `viewer` rank "
                f"{ranks['viewer']} - anonymous surface widened"
            )
    return violations


def _check_default_deny_fallback(source: str) -> list[str]:
    violations: list[str] = []
    body = _function_body(source, "export function classifyToolCapability")
    if body is None:
        return ["classifyToolCapability not found in SSOT (fail-closed)"]
    last_return = body.rfind("return {")
    if last_return == -1:
        return ["classifyToolCapability has no default return (fail-closed default missing)"]
    fallback = body[last_return:]
    if 'access: "restricted"' not in fallback:
        violations.append('classifyToolCapability default fallback is not access: "restricted" (default-deny broken)')
    if 'dataClassification: "internal"' not in fallback:
        violations.append('classifyToolCapability default fallback is not dataClassification: "internal" (default-deny broken)')
    return violations


def _public_safe_array(source: str) -> str:
    start = source.find("publicSafeCapabilities")
    if start == -1:
        return ""
    arr_start = source.find("= [", start)
    arr_end = source.find("\n];", arr_start)
    if arr_start == -1 or arr_end == -1:
        return ""
    return source[arr_start:arr_end]


def _check_overexposed_tools(source: str, array_body: str) -> list[str]:
    violations: list[str] = []
    for tool in OVEREXPOSED_TOOLS:
        if f'name: "{tool}"' in array_body:
            violations.append(f'{tool} appears in publicSafeCapabilities (public manifest must not advertise #1843 over-exposure class)')
        # any explicit classification branch granting safe/public?
        for m in re.finditer(re.escape(f'"{tool}"'), source):
            ret = source.find("return {", m.end())
            if ret == -1:
                continue
            end = source.find("};", ret)
            block = source[ret:end if end != -1 else ret + 400]
            if 'access: "safe"' in block or 'dataClassification: "public"' in block:
                violations.append(f'{tool} is explicitly classified safe/public in classifyToolCapability (must stay denied to public_viewer)')
                break
    # github_list_secrets must keep its explicit secret/R4 pin
    block = _return_object_block_after(source, 'name === "github_list_secrets"')
    if block is None:
        violations.append('github_list_secrets explicit classification block not found (secret/R4 pin lost)')
    else:
        if 'access: "restricted"' not in block or 'dataClassification: "secret"' not in block:
            violations.append('github_list_secrets no longer classified restricted+secret (R4 pin lost)')
    return violations


def _check_public_safe_array_purity(array_body: str) -> list[str]:
    violations: list[str] = []
    if not array_body:
        return ["publicSafeCapabilities array not found or unparseable (SSOT restructured)"]
    for entry in re.finditer(r"\{[^{}]*\}", array_body):
        text = entry.group(0)
        if 'kind: "tool"' not in text and 'kind: "resource"' not in text:
            continue
        if 'access: "safe"' not in text:
            violations.append(f'publicSafeCapabilities entry without access safe: {text.strip()[:80]}')
        if 'dataClassification: "public"' not in text:
            violations.append(f'publicSafeCapabilities entry without public classification: {text.strip()[:80]}')
    return violations


def run_checks(policy_path: Path) -> list[str]:
    """Execute every invariant against *policy_path*. Fail-closed on absence."""
    if not policy_path.is_file():
        return [f"policy SSOT missing: {policy_path} (fail-closed; never guess around an unreadable policy file)"]
    try:
        source = policy_path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"policy SSOT unreadable: {policy_path} ({exc})"]

    violations: list[str] = []
    violations += _check_public_viewer_predicate(source)
    ranks, rank_error = load_role_rank(policy_path)
    if rank_error:
        violations.append(rank_error)
    else:
        violations += _check_rank_ladder(source, ranks)
    violations += _check_default_deny_fallback(source)
    array_body = _public_safe_array(source)
    violations += _check_overexposed_tools(source, array_body)
    violations += _check_public_safe_array_purity(array_body)
    return violations


# ---------------------------------------------------------------------------
# Self-test: hermetic fixture matrix (no network, no live tower dependence).
# ---------------------------------------------------------------------------

def _fixture_base() -> str:
    """Minimal synthetic mcp-access.ts carrying every structure the guard pins."""
    return '''import type { UserRole } from "./auth.context.js";

export const publicSafeCapabilities: readonly McpCapabilityMetadata[] = [
  { name: "system.health", kind: "tool", access: "safe", requiredScope: "health:read", riskLevel: "R0", dataClassification: "public", approvalRequired: false },
  { name: "status", kind: "tool", access: "safe", riskLevel: "R0", dataClassification: "public", approvalRequired: false },
  { name: "bridge_work", kind: "tool", access: "safe", riskLevel: "R0", dataClassification: "public", approvalRequired: false },
];

export function canAccessCapability(context: McpAccessContext, capability: McpCapabilityMetadata): boolean {
  if (context.mode === "public_viewer") {
    return capability.access === "safe" && capability.dataClassification === "public";
  }
  const rank = roleRank(context.mode as UserRole);
  if (capability.dataClassification === "secret") return rank >= 2;
  if (capability.access === "restricted") return rank >= 1;
  if (capability.requiredScope && !context.scopes.includes("*") && !context.scopes.includes(capability.requiredScope)) return false;
  return true;
}

export function classifyToolCapability(name: string): McpCapabilityMetadata {
  if (name === "system_summary" || name === "system_health" || name === "status") {
    return {
      name,
      kind: "tool",
      access: "safe",
      requiredScope: name === "system_health" ? "health:read" : "system:read",
      riskLevel: "R0",
      dataClassification: "public",
      approvalRequired: false,
    };
  }
  if (
    name.startsWith("infisical_") ||
    name === "github_list_secrets" ||
    name === "render_get_env_vars" ||
    name === "render_get_env_var_keys"
  ) {
    return {
      name,
      kind: "tool",
      access: "restricted",
      requiredScope: undefined,
      riskLevel: "R4",
      dataClassification: "secret",
      approvalRequired: false,
    };
  }
  return {
    name,
    kind: "tool",
    access: "restricted",
    requiredScope: undefined,
    riskLevel: "R2",
    dataClassification: "internal",
    approvalRequired: false,
  };
}
'''


ROLE_RANK_FIXTURE = """export type UserRole = "supremeadmin" | "admin" | "agent" | "viewer";

export const ROLE_RANK: Readonly<Record<UserRole, number>> = {
  viewer: 0,
  restricted_viewer: 0,
  repo_viewer: 0,
  agent: 1,
  admin: 2,
  supremeadmin: 3,
} as const;

export function roleRank(role: UserRole | undefined | null): number {
  return role ? (ROLE_RANK[role] ?? 0) : 0;
}
"""


def _write_fixture(fixture_dir: Path, content: str, ladder: str | None = None) -> Path:
    """Write the policy fixture plus its sibling RBAC ladder (auth.context.ts)."""
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / "auth.context.ts").write_text(ladder or ROLE_RANK_FIXTURE, encoding="utf-8")
    path = fixture_dir / "mcp-access.ts"
    path.write_text(content, encoding="utf-8")
    return path


def run_self_test() -> int:
    cases = 0
    failed = 0

    def expect(name: str, content: str | None, want_violation: bool) -> None:
        nonlocal cases, failed
        cases += 1
        with tempfile.TemporaryDirectory() as td:
            if content is None:
                policy = Path(td) / "absent" / "mcp-access.ts"
            else:
                policy = _write_fixture(Path(td) / "policy", content)
            violations = run_checks(policy)
        ok = bool(violations) == want_violation
        status = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        detail = "clean" if not violations else f"{len(violations)} violation(s): {violations[0][:70]}"
        print(f"  [{status}] {name} ({detail})")

    base = _fixture_base()

    expect("clean fixture passes", base, want_violation=False)
    expect("missing SSOT fails closed", None, want_violation=True)

    tampered = base.replace('name === "github_list_secrets"', 'name === "github_list_secrets_RENAMED_AWAY"')
    expect("github_list_secrets secret/R4 pin removed", tampered, want_violation=True)

    tampered = base.replace(
        'if (capability.dataClassification === "secret") return rank >= 2;',
        'if (capability.dataClassification === "secret") return rank >= 1;',
    )
    expect("secret ladder widened to `agent`", tampered, want_violation=True)

    tampered = base.replace(
        'if (capability.access === "restricted") return rank >= 1;',
        'if (capability.access === "restricted") return rank >= 0;',
    )
    expect("restricted ladder widened to `viewer`", tampered, want_violation=True)

    # Renumbering the ladder while keeping the same policy meaning must PASS:
    # this is the regression that made the guard cried wolf on 2026-11-19.
    renumbered_ladder = ROLE_RANK_FIXTURE.replace("viewer: 0", "viewer: 10").replace(
        "restricted_viewer: 0", "restricted_viewer: 10"
    ).replace("repo_viewer: 0", "repo_viewer: 10").replace(
        "agent: 1,", "agent: 20,"
    ).replace("admin: 2,", "admin: 30,").replace("supremeadmin: 3,", "supremeadmin: 40,")
    renumbered = base.replace("rank >= 2", "rank >= 30").replace("rank >= 1", "rank >= 20")
    with tempfile.TemporaryDirectory() as td:
        cases += 1
        policy = _write_fixture(Path(td) / "policy", renumbered, ladder=renumbered_ladder)
        violations = run_checks(policy)
        ok = not violations
        if not ok:
            failed += 1
        print(f"  [{'PASS' if ok else 'FAIL'}] renumbered ladder keeps the same policy"
              f" ({'clean' if not violations else violations[0][:70]})")

    # A ladder that disagrees with the thresholds must still fail.
    strict_ladder = ROLE_RANK_FIXTURE.replace("admin: 2,", "admin: 3,")
    with tempfile.TemporaryDirectory() as td:
        cases += 1
        policy = _write_fixture(Path(td) / "policy", base, ladder=strict_ladder)
        violations = run_checks(policy)
        ok = bool(violations)
        if not ok:
            failed += 1
        print(f"  [{'PASS' if ok else 'FAIL'}] threshold below the declared admin rank"
              f" ({'clean' if not violations else violations[0][:70]})")

    tampered = base.replace(
        'return capability.access === "safe" && capability.dataClassification === "public";',
        'return capability.access === "safe";',
    )
    expect("public_viewer public-conjunct removed", tampered, want_violation=True)

    tampered = base.replace(
        '    access: "restricted",\n    requiredScope: undefined,\n    riskLevel: "R2",\n    dataClassification: "internal",',
        '    access: "safe",\n    requiredScope: undefined,\n    riskLevel: "R2",\n    dataClassification: "public",',
    )
    expect("default fallback flipped to safe/public", tampered, want_violation=True)

    tampered = base.replace(
        '{ name: "bridge_work", kind: "tool", access: "safe", riskLevel: "R0", dataClassification: "public", approvalRequired: false },',
        '{ name: "bridge_work", kind: "tool", access: "safe", riskLevel: "R0", dataClassification: "public", approvalRequired: false },\n  { name: "supabase_read_table", kind: "tool", access: "safe", riskLevel: "R0", dataClassification: "public", approvalRequired: false },',
    )
    expect("over-exposed tool added to public manifest", tampered, want_violation=True)

    print(f"self-test: {cases - failed}/{cases} cases passed")
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="MCP access-policy deny-matrix guard (#1843 class)")
    parser.add_argument("--check", action="store_true", help="check the real SSOT (default action)")
    parser.add_argument("--policy", type=str, default=None, help="override policy file path (tests/fixtures)")
    parser.add_argument("--self-test", action="store_true", help="run hermetic fixture matrix")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    policy = Path(args.policy) if args.policy else DEFAULT_POLICY
    violations = run_checks(policy)
    if violations:
        print(f"mcp-access deny-matrix guard: FAIL ({policy})")
        for v in violations:
            print(f"  - {v}")
        return 1
    print(f"mcp-access deny-matrix guard: OK ({policy})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
