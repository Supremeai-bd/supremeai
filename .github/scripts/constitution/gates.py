"""Automated System Gates (Issue #2251 — Phase 5 governance flip).

বাংলা: AGENTS.md v2-এর "prose → gate" রূপান্তরের তিনটি সক্রিয় gate:
  1. Verification Gate — PR description-এ Test Evidence (টেস্ট লগ) বাধ্যতামূলক।
  2. Scope Gate       — claim comment-এর "Touching files:" বাইরের ফাইল বদলালে BLOCK।
  3. Lease Gate       — bot PR-এর branch অবশ্যই লেখকের leased slot-এর ভেতরে হতে হবে।

প্রতিটি gate-এর থ্রেশহোল্ড/পলিসি `.github/constitution/rules.yml`-এ থাকে
(machine-readable constitution) — এই মডিউল শুধু সেটা পড়ে enforce করে।

CLI:
    PYTHONPATH=.github/scripts python -m constitution.gates verification --pr 123
    PYTHONPATH=.github/scripts python -m constitution.gates scope --pr 123
    PYTHONPATH=.github/scripts python -m constitution.gates lease --pr 123
    PYTHONPATH=.github/scripts python -m constitution.gates all --pr 123

Exit code: 0 = pass, 1 = BLOCK, 2 = config/arg error.
SYSTEM_GATES_MODE=warn env দিলে BLOCK-এর বদলে শুধু সতর্কতা (rollout soft-launch)।
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
RULES_PATH = REPO_ROOT / ".github" / "constitution" / "rules.yml"

DEFAULT_SCOPE_POLICY = {
    "declaration_marker": "Touching files:",
    "undeclared_files": "block",
    "missing_declaration": "block",
    "advisory_authors": ["OWNER", "MEMBER", "COLLABORATOR"],
    "allowlist": ["docs/generated/**"],
}
DEFAULT_VERIFICATION_POLICY = {
    "min_evidence_chars": 40,
    "section_names": ["Test Evidence", "Tests", "পরীক্ষা", "টেস্ট এভিডেন্স"],
    "output_markers": ["passed", "pytest", "unittest", "bun test", "vitest"],
}
DEFAULT_LEASE_POLICY = {
    "bot_author_regex": r"^supremeai-([a-z0-9]+)-([0-9]+)-bot(\[bot\])?$",
    "bot_branch_regex": r"^([a-z0-9]+)-([0-9]+)([-_.].+)?$",
    "exempt_authors": ["dependabot[bot]", "app/dependabot", "github-actions[bot]", "renovate[bot]"],
    "docs_branch_prefix": "docs/",
    "group_branch_prefix": "group/",
    "mesh_advisory_env": "SUPREME_MESH_URL",
}
DEFAULT_SELF_MERGE_POLICY = {
    "block_self_approval": True,
    "block_self_merge": True,
}
DEFAULT_TEST_GUARD_POLICY = {
    "deleted_test_files": "block",
    "added_skip_markers": "block",
    "allow_deleted_paths": [],
}
DEFAULT_PREDECESSOR_POLICY = {
    "group_dependencies": {
        "foundation-closeout": "pipeline-governance",
    },
    "hold_label": "queue:hold",
    "group_branch_prefix": "group/",
}


# ─────────────────────────── policy loading ───────────────────────────

def load_policies(rules_path: Optional[Path] = None) -> dict:
    """Load gate policies from the machine-readable constitution (rules.yml)."""
    path = Path(rules_path) if rules_path else RULES_PATH
    try:
        import yaml
    except ImportError:
        print("::warning::PyYAML unavailable — falling back to built-in gate defaults")
        return {
            "scope_policy": dict(DEFAULT_SCOPE_POLICY),
            "verification_policy": dict(DEFAULT_VERIFICATION_POLICY),
            "lease_policy": dict(DEFAULT_LEASE_POLICY),
            "self_merge_policy": dict(DEFAULT_SELF_MERGE_POLICY),
            "test_guard_policy": dict(DEFAULT_TEST_GUARD_POLICY),
            "predecessor_policy": dict(DEFAULT_PREDECESSOR_POLICY),
        }
    if not path.exists():
        print(f"::warning::{path} not found — falling back to built-in gate defaults")
        return {
            "scope_policy": dict(DEFAULT_SCOPE_POLICY),
            "verification_policy": dict(DEFAULT_VERIFICATION_POLICY),
            "lease_policy": dict(DEFAULT_LEASE_POLICY),
            "self_merge_policy": dict(DEFAULT_SELF_MERGE_POLICY),
            "test_guard_policy": dict(DEFAULT_TEST_GUARD_POLICY),
            "predecessor_policy": dict(DEFAULT_PREDECESSOR_POLICY),
        }
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return {
        "scope_policy": {**DEFAULT_SCOPE_POLICY, **(data.get("scope_policy") or {})},
        "verification_policy": {**DEFAULT_VERIFICATION_POLICY, **(data.get("verification_policy") or {})},
        "lease_policy": {**DEFAULT_LEASE_POLICY, **(data.get("lease_policy") or {})},
        "self_merge_policy": {**DEFAULT_SELF_MERGE_POLICY, **(data.get("self_merge_policy") or {})},
        "test_guard_policy": {**DEFAULT_TEST_GUARD_POLICY, **(data.get("test_guard_policy") or {})},
        "predecessor_policy": {**DEFAULT_PREDECESSOR_POLICY, **(data.get("predecessor_policy") or {})},
    }


# ─────────────────────────── shared helpers ───────────────────────────

def path_matches(path: str, pattern: str) -> bool:
    """fnmatch-style matcher that also honours trailing `/**` directory globs."""
    path = path.lstrip("./")
    pattern = pattern.lstrip("./")
    if fnmatch.fnmatch(path, pattern):
        return True
    if pattern.endswith("/**"):
        base = pattern[:-3]
        return path == base or path.startswith(base + "/")
    return False


def path_matches_any(path: str, patterns: list) -> bool:
    return any(path_matches(path, p) for p in patterns)


def is_truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "warn"}


def gh_api(endpoint: str, token: Optional[str] = None) -> object:
    """Minimal GitHub REST GET via gh CLI first, then urllib fallback."""
    try:
        res = subprocess.run(
            ["gh", "api", endpoint],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=True,
        )
        return json.loads(res.stdout)
    except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError):
        pass
    tok = token or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not tok:
        raise RuntimeError(f"no gh CLI and no token for API call: {endpoint}")
    url = f"https://api.github.com/{endpoint.lstrip('/')}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {tok}",
        "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def gate_result(name: str, ok: bool, message: str) -> int:
    """Print gate verdict consistently and return the process exit code for it."""
    mode = os.environ.get("SYSTEM_GATES_MODE", "strict").strip().lower()
    if ok:
        print(f"[PASSED] {name}: {message}")
        return 0
    if mode == "warn":
        print(f"::warning::[WARN-MODE] {name}: {message}")
        print(f"[WARNED] {name} ran in warn mode (SYSTEM_GATES_MODE=warn) — not blocking.")
        return 0
    print(f"::error::{name} BLOCK: {message}")
    return 1


# ─────────────────────── Verification Gate (test logs required) ───────────────────────

def _cut_before_next_heading(text: str) -> str:
    """Truncate before the next markdown heading — fence-aware (#2397).

    # বাংলা মন্তব্য: কোড-ফেন্সের (``` বা ~~~) ভেতরের '#' লাইন কমেন্ট/লগ —
    # heading নয়। পুরোনো fence-blind cutter Test Evidence-এর প্রথম কমেন্ট-লাইনেই
    # কেটে সেকশন ৩ অক্ষরে নামিয়ে দিত — বাস্তব evidence থাকতেও BLOCK (PR #2401-এর
    # CI-তে প্রমাণিত)। তাই ফেন্স-সচেতন স্ক্যান: ফেন্সের ভেতরে heading হবে না।
    """
    fence = None
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        fence_m = re.match(r"^(`{3,}|~{3,})", stripped)
        if fence_m:
            tok = fence_m.group(1)
            if fence is None:
                fence = tok[0]
            elif stripped.startswith(fence):
                fence = None
            offset += len(line)
            continue
        if fence is None and re.match(r"^#{1,6}\s+\S", line):
            return text[:offset]
        offset += len(line)
    return text


def extract_test_evidence(body: str, policy: dict) -> tuple[bool, str]:
    """Return (has_evidence, reason). Body must contain a Test Evidence section
    whose content is non-trivial and looks like test output / commands."""
    if not body or not body.strip():
        return False, "PR body is empty — no Test Evidence section"
    names = policy.get("section_names") or DEFAULT_VERIFICATION_POLICY["section_names"]
    min_chars = int(policy.get("min_evidence_chars", 40))
    markers = policy.get("output_markers") or DEFAULT_VERIFICATION_POLICY["output_markers"]

    section = None
    for name in names:
        pattern = re.compile(
            rf"^#+\s*(?:.*)?{re.escape(name)}.*$",
            re.IGNORECASE | re.MULTILINE,
        )
        m = pattern.search(body)
        if m:
            section = _cut_before_next_heading(body[m.end():])
            break
    if section is None:
        return False, (
            "No Test Evidence section found in PR body "
            f"(expected any of: {', '.join(names)}). "
            "Add a '## Test Evidence' section with the actual test log/commands."
        )
    text = section.strip()
    if len(text) < min_chars:
        return False, (
            f"Test Evidence section too short ({len(text)} < {min_chars} chars) — "
            "paste the real test command + result summary"
        )
    lowered = text.lower()
    if any(marker.lower() in lowered for marker in markers):
        return True, f"Test Evidence found ({len(text)} chars, contains test-output markers)"
    return False, (
        "Test Evidence section has no recognizable test output marker "
        f"(looking for any of: {', '.join(map(str, markers[:8]))}...)"
    )


def run_verification_gate(pr_body: str, policy: dict) -> int:
    ok, reason = extract_test_evidence(pr_body or "", policy)
    return gate_result("Verification Gate", ok, reason)


# ─────────────────── Scope Gate (claim declaration vs changed files) ───────────────────

def parse_declared_files(comments: list) -> set:
    """Extract declared paths from claim comments containing 'Touching files:'.

    Supports both formats used by agents:
      - `**Touching files:**` followed by a bullet/backtick list (multi-line)
      - `Touching files: a.py, b.py` inline
    Annotations like `(delete — ...)`, `(new — ...)` are stripped.
    """
    marker = "Touching files:"
    declared: set = set()
    path_re = re.compile(r"[\w./@-]+\.[A-Za-z0-9]{1,12}|[\w./@-]+(?:/[\w.@*-]+)+")

    def harvest(segment: str) -> None:
        segment = re.sub(r"\([^)]*\)", " ", segment)  # strip annotations
        segment = segment.replace("**", " ").replace("`", " ")
        for token in re.split(r"[,\s]+", segment):
            token = token.strip().strip("`").strip("*").strip(",").strip("-")
            if not token:
                continue
            if "/" in token or "." in token.split("/")[-1]:
                if path_re.fullmatch(token):
                    declared.add(token.strip("/"))

    for body in comments or []:
        if not body or marker not in body:
            continue
        lines = body.splitlines()
        for idx, line in enumerate(lines):
            if marker not in line:
                continue
            harvest(line.split(marker, 1)[1])
            # multi-line block: consume following bullet/backtick lines until a
            # non-list line (heading, prose paragraph, blank+prose) appears.
            for follow in lines[idx + 1 :]:
                stripped = follow.strip()
                if not stripped:
                    continue  # blank line — keep scanning (lists often have gaps)
                if stripped.startswith(("#", ">")) and marker not in stripped:
                    break  # new heading/quote — declaration block ended
                if stripped.startswith(("-", "*", "`")):
                    harvest(stripped)
                    continue
                # prose line — only treat as part of declaration if it looks path-y
                if "/" in stripped or "`" in stripped:
                    harvest(stripped)
                    continue
                break
    return declared


def find_linked_issue_numbers(title: str, body: str) -> list:
    """Issue reference from PR title suffix '(#N)' (repo convention) or closing keywords."""
    nums: list = []
    m = re.search(r"\(#(\d+)\)\s*$", (title or "").strip())
    if m:
        nums.append(int(m.group(1)))
    for m in re.finditer(
        r"(?:\b(?:closes?|fixes?|resolves?)\s+#(\d+))", (body or ""), re.IGNORECASE
    ):
        if int(m.group(1)) not in nums:
            nums.append(int(m.group(1)))
    return nums


def find_undeclared_files(changed: list, declared: set, allowlist: list) -> list:
    """Files changed by the PR that are neither declared in the claim nor allowlisted.

    Declaration semantics: an exact path matches itself; a declaration that ends
    with `/` (or is a known directory prefix) matches its whole subtree — agents
    commonly declare directories like `.github/scripts/`.
    """
    out = []
    dir_decls = {d.rstrip("/") for d in declared or [] if d.endswith("/")}
    file_decls = {d for d in declared or [] if not d.endswith("/")}
    for path in changed or []:
        if path in file_decls:
            continue
        if any(path == d or path.startswith(d + "/") for d in dir_decls):
            continue
        if path_matches_any(path, allowlist or []):
            continue
        out.append(path)
    return sorted(out)


def run_scope_gate(pr_number: int, pr_author_association: str, pr_title: str,
                   pr_body: str, policy: dict, api=None) -> int:
    api = api or gh_api
    allowlist = policy.get("allowlist") or []
    advisory_authors = policy.get("advisory_authors") or []
    undeclared_action = policy.get("undeclared_files", "block")
    missing_action = policy.get("missing_declaration", "block")

    files_payload = api(f"repos/{_repo()}/pulls/{pr_number}/files?per_page=100")
    changed = [f["filename"] for f in files_payload or []]

    issue_nums = find_linked_issue_numbers(pr_title, pr_body)
    comments: list = []
    if issue_nums:
        for num in issue_nums[:3]:
            try:
                comments.extend(api(f"repos/{_repo()}/issues/{num}/comments?per_page=100") or [])
            except Exception as err:  # noqa: BLE001 — gate must not crash on API hiccup
                print(f"::warning::could not fetch issue #{num} comments: {err}")
    bodies = [c.get("body", "") for c in comments if isinstance(c, dict)]
    declared = parse_declared_files(bodies)

    if not declared:
        msg = (
            "No 'Touching files:' declaration found on the linked claim issue "
            f"(linked: {issue_nums or 'none'}). Rule 2/20: No Claim, No Code — "
            "post the claim comment with declared files, then re-run."
        )
        if pr_author_association in advisory_authors:
            print(f"::warning::[advisory:{pr_author_association}] {msg}")
            print("[PASSED] Scope Gate (advisory author — warn only)")
            return 0
        return gate_result("Scope Gate", missing_action != "block", msg)

    undeclared = find_undeclared_files(changed, declared, allowlist)
    if not undeclared:
        print(f"[PASSED] Scope Gate: {len(changed)} changed files, all declared or allowlisted")
        return 0
    listing = ", ".join(undeclared[:20]) + (" …" if len(undeclared) > 20 else "")
    msg = (
        f"{len(undeclared)} file(s) changed outside the declared 'Touching files:' set: {listing}. "
        "Fix: update the claim comment on the issue (or drop the undeclared changes)."
    )
    if pr_author_association in advisory_authors:
        print(f"::warning::[advisory:{pr_author_association}] {msg}")
        return 0
    return gate_result("Scope Gate", undeclared_action != "block", msg)


def _repo() -> str:
    env = os.environ.get("GH_REPO") or os.environ.get("GITHUB_REPOSITORY")
    if env:
        return env
    res = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True)
    m = re.search(r"github\.com[/:]([\w.-]+/[\w.-]+?)(?:\.git)?$", res.stdout.strip())
    if not m:
        raise RuntimeError("cannot determine GH repo (set GH_REPO)")
    return m.group(1)


# ─────────────────────────── Lease Gate (slot identity) ───────────────────────────

def check_lease(author: str, branch: str, policy: dict) -> tuple[bool, str]:
    """Bot authors may only push from their leased slot branch (or docs/).

    Returns (ok, reason). Humans and exempt bots always pass.
    """
    author = (author or "").strip()
    branch = (branch or "").strip()
    exempt = set(policy.get("exempt_authors") or [])
    # বাংলা মন্তব্য: dependabot বা অন্যান্য exempt bot-কে lease check থেকে অব্যাহতি দেওয়া হয়েছে
    if author in exempt or "dependabot" in author or (author.endswith("[bot]") and "supremeai-" not in author):
        return True, f"author '{author}' is exempt from lease gate"
    m = re.match(policy.get("bot_author_regex", DEFAULT_LEASE_POLICY["bot_author_regex"]), author)
    if not m:
        return True, f"author '{author}' is not a slot bot — lease gate advisory only"
    lane, slot = m.group(1), m.group(2)
    docs_prefix = policy.get("docs_branch_prefix", "docs/")
    if branch.startswith(docs_prefix):
        return True, f"docs branch '{branch}' allowed for slot {lane}-{slot}"
    # Flexible Group Branching (#2378): group/* branches lease by group
    # participation, not slot pattern — the PR author must have a claim comment
    # (active or completed) on an open issue carrying the matching
    # `group:<name>` label. Historical participation is accepted because the
    # group PR stays open after each member's claim is released.
    group_prefix = policy.get("group_branch_prefix", DEFAULT_LEASE_POLICY["group_branch_prefix"])
    if branch.startswith(group_prefix):
        return _group_lease_check(author, lane, slot, branch[len(group_prefix):].strip("/"))
    bm = re.match(policy.get("bot_branch_regex", DEFAULT_LEASE_POLICY["bot_branch_regex"]), branch)
    if not bm:
        return False, (
            f"branch '{branch}' does not match slot pattern <lane>-<N> for author '{author}' "
            f"(leased slot: {lane}-{slot})"
        )
    if (bm.group(1), bm.group(2)) != (lane, slot):
        return False, (
            f"cross-slot push: author '{author}' leases {lane}-{slot} "
            f"but branch '{branch}' belongs to {bm.group(1)}-{bm.group(2)}"
        )
    ok, reason = _mesh_lease_advisory(policy)
    if not ok:
        return False, reason
    return True, f"branch '{branch}' matches leased slot {lane}-{slot}"


def _group_lease_check(author: str, lane: str, slot: str, group_name: str) -> tuple[bool, str]:
    """Group-branch lease (#2378 Flexible Group Branching Protocol).

    # বাংলা মন্তব্য: Connected Work মডেলে একাধিক bot একই group/<name> ব্রাঞ্চে
    # কাজ করে এবং গ্রুপ PR সদস্যের claim release হওয়ার পরেও খোলা থাকে — তাই
    # যাচাই হয় গ্রুপ-অংশগ্রহণ: PR author-এর slot-identity সংশ্লিষ্ট group:<name>
    # লেবেলযুক্ত কোনো খোলা ইস্যুর claim comment-এ থাকতে হবে (সক্রিয় বা সম্পন্ন —
    # দুটোই গণ্য)। API না চললে advisory pass (mesh-advisory pattern — CI
    # কখনো API uptime-এর ওপর hard-depend করে না)।
    """
    identities = {author, author.removesuffix("-bot"), f"{lane}-{slot}"}
    label = f"group:{group_name}"
    try:
        query = f"repos/{_repo()}/issues?labels={urllib.parse.quote(label)}&state=open&per_page=50"
        issues = gh_api(query) or []
        for iss in issues[:10]:
            num = iss.get("number")
            try:
                comments = gh_api(f"repos/{_repo()}/issues/{num}/comments?per_page=50") or []
            except Exception:  # noqa: BLE001 — per-issue comment fetch is best-effort
                continue
            for c in comments:
                text = c.get("body") or ""
                if any(ident and ident in text for ident in identities):
                    return True, (
                        f"group branch 'group/{group_name}' allowed: claim participation found "
                        f"on #{num} for '{author}' (slot {lane}-{slot})"
                    )
        if not issues:
            return False, (
                f"group branch 'group/{group_name}' has no open '{label}' issue — group lease "
                f"unverifiable; open/claim a group issue before pushing (#2378)"
            )
        return False, (
            f"author '{author}' (slot {lane}-{slot}) has no claim participation on any "
            f"'{label}' issue — run atomic_claim.sh on a group issue before pushing "
            f"to 'group/{group_name}' (#2378)"
        )
    except Exception as err:  # noqa: BLE001 — CI cannot hard-depend on API uptime
        print(f"::warning::group lease check unavailable ({err}) — advisory pass for 'group/{group_name}'")
        return True, f"group branch 'group/{group_name}' allowed (advisory: API unavailable)"


def _mesh_lease_advisory(policy: dict) -> tuple[bool, str]:
    """Best-effort mesh lease freshness check (only when SUPREME_MESH_URL is set)."""
    env_key = policy.get("mesh_advisory_env", "SUPREME_MESH_URL")
    base = os.environ.get(env_key, "").strip().rstrip("/")
    if not base:
        return True, "mesh registry not configured — slot-pattern check stands"
    try:
        req = urllib.request.Request(f"{base}/api/v1/nodes", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            nodes = (json.loads(resp.read().decode("utf-8")) or {}).get("nodes", [])
        stale = [n.get("node_id") for n in nodes if n.get("lease_active") is False]
        return True, f"mesh reachable ({len(nodes)} nodes, {len(stale)} idle) — lease advisory OK"
    except Exception as err:  # noqa: BLE001 — CI cannot hard-depend on mesh uptime
        print(f"::warning::mesh registry unreachable ({err}) — lease gate falls back to slot-pattern only")
        return True, "mesh unreachable — fallback check used"


def run_lease_gate(pr_author: str, pr_branch: str, policy: dict) -> int:
    ok, reason = check_lease(pr_author or "", pr_branch or "", policy)
    return gate_result("Lease Gate", ok, reason)


# ─────────────────────── Self-Merge Gate (#2397 wiring) ───────────────────────

def run_self_merge_gate(pr_number: int, policy: dict) -> int:
    """Self-Merge Gate — constitution registry wired by #2397 (was wired=false).

    # বাংলা মন্তব্য: নিজের PR নিজে approve করা (self-approval) বা নিজের হাতে
    # merge করা (merged_by == author, মার্জ-পরবর্তী অডিটে ধরা হয়) — দুটোই BLOCK।
    # API অনুপলব্ধ হলে advisory pass — CI কখনো API uptime-এ hard-depend করে না।
    """
    try:
        pr = gh_api(f"repos/{_repo()}/pulls/{pr_number}")
        author = (pr.get("user") or {}).get("login", "")
        merged_by = ((pr.get("merged_by") or {}).get("login", "")) if pr.get("merged") else ""
        reviews = gh_api(f"repos/{_repo()}/pulls/{pr_number}/reviews?per_page=50") or []
        self_approvals = [
            r for r in reviews
            if (r.get("user") or {}).get("login", "") == author and r.get("state") == "APPROVED"
        ]
        if self_approvals and policy.get("block_self_approval", True):
            return gate_result(
                "Self-Merge Gate", False,
                f"self-approval detected: author '{author}' approved their own PR",
            )
        if merged_by and merged_by == author and policy.get("block_self_merge", True):
            return gate_result(
                "Self-Merge Gate", False,
                f"self-merge detected: PR was merged by its own author '{author}'",
            )
        return gate_result(
            "Self-Merge Gate", True,
            f"no self-approval/self-merge for '{author}' ({len(reviews)} review(s) audited)",
        )
    except Exception as err:  # noqa: BLE001 — CI cannot hard-depend on API uptime
        print(f"::warning::self-merge gate check unavailable ({err}) — advisory pass")
        return gate_result("Self-Merge Gate", True, "advisory pass (API unavailable)")


# ─────────────────────── Test Guard Gate (#2397 wiring) ───────────────────────

TEST_PATH_RE = re.compile(
    r"(?:^|/)(?:tests?/|[^/]*_test\.py$|test_[^/]*\.py$|[^/]*\.test\.[jt]sx?$|[^/]*\.spec\.[jt]sx?$)",
    re.IGNORECASE,
)
SKIP_MARKER_RE = re.compile(
    r"^\+.*(pytest\.skip\(|pytest\.mark\.skip|@pytest\.mark\.xfail|unittest\.skip|it\.skip\(|describe\.skip\()",
    re.IGNORECASE,
)


def run_test_guard_gate(pr_number: int, policy: dict) -> int:
    """Test Guard — constitution registry wired by #2397 (was wired=false).

    # বাংলা মন্তব্য: টেস্ট-ম্যানিপুলেশন ধরা: (১) টেস্ট ফাইল ডিলিট (allowlist-বাহিরে),
    # (২) diff-এ নতুন skip/xfail marker যোগ। টেস্ট থ্রেশহোল্ড কমানো পরবর্তী
    # hardening-এ (follow-up)। allow_deleted_paths policy-তে স্বীকৃত ব্যতিক্রম।
    """
    try:
        files = gh_api(f"repos/{_repo()}/pulls/{pr_number}/files?per_page=100") or []
    except Exception as err:  # noqa: BLE001 — CI cannot hard-depend on API uptime
        print(f"::warning::test guard check unavailable ({err}) — advisory pass")
        return gate_result("Test Guard", True, "advisory pass (API unavailable)")

    allow = set(policy.get("allow_deleted_paths") or [])
    deleted_tests = [
        f["filename"] for f in files
        if f.get("status") == "removed" and TEST_PATH_RE.search(f.get("filename", ""))
        and f["filename"] not in allow
    ]
    if deleted_tests and policy.get("deleted_test_files", "block") == "block":
        return gate_result(
            "Test Guard", False,
            "test file(s) deleted: " + ", ".join(deleted_tests[:5]),
        )

    skip_added = []
    for f in files:
        fn = f.get("filename", "")
        if f.get("status") == "removed" or not TEST_PATH_RE.search(fn):
            continue
        for line in (f.get("patch") or "").splitlines():
            if SKIP_MARKER_RE.match(line):
                skip_added.append(f"{fn}: {line[1:].strip()[:60]}")
                if len(skip_added) >= 5:
                    break
        if len(skip_added) >= 5:
            break
    if skip_added and policy.get("added_skip_markers", "block") == "block":
        return gate_result(
            "Test Guard", False,
            "skip/xfail marker(s) added to tests: " + "; ".join(skip_added[:3]),
        )
    touched = sum(1 for f in files if TEST_PATH_RE.search(f.get("filename", "")))
    return gate_result("Test Guard", True, f"{touched} test file(s) touched, none manipulated")


# ─────────────────────── Predecessor Group Merge Hold Gate (#2408) ───────────────────────

def check_predecessor_hold(
    group_name: str,
    has_hold_label: bool,
    pred_unmerged: bool,
    policy: dict,
) -> tuple[bool, str]:
    """Pure evaluation of predecessor group merge hold rule (#2408).

    # বাংলা মন্তব্য: Predecessor Group Merge Hold Law:
    # যদি কোনো PR-এর গ্রুপ অন্য কোনো পূর্ববর্তী গ্রুপের ওপর নির্ভরশীল হয়
    # এবং সেই পূর্ববর্তী গ্রুপ এখনো সম্পূর্ণ না হয়ে থাকে (unmerged),
    # তবে এই PR-এ অবশ্যই 'queue:hold' লেবেল থাকতে হবে।
    """
    if not group_name:
        return True, "PR does not belong to a group sequence"

    deps = policy.get("group_dependencies") or DEFAULT_PREDECESSOR_POLICY["group_dependencies"]
    pred = deps.get(group_name)
    if not pred:
        return True, f"group '{group_name}' has no predecessor dependencies"

    hold_label = policy.get("hold_label", "queue:hold")
    if pred_unmerged:
        if has_hold_label:
            return True, f"predecessor group '{pred}' in-flight; PR correctly held by '{hold_label}'"
        return False, f"predecessor group '{pred}' not yet merged to main — PR must carry '{hold_label}' label"

    return True, f"predecessor group '{pred}' is merged; PR cleared for closeout/merge train"


def run_predecessor_gate(
    pr_number: int,
    branch: str = "",
    labels: Optional[list] = None,
    policy: Optional[dict] = None,
    api=None,
) -> int:
    """Predecessor Group Merge Hold Gate (#2408)."""
    api = api or gh_api
    pol = policy or DEFAULT_PREDECESSOR_POLICY
    group_name = ""

    # 1. Extract group from branch
    group_prefix = pol.get("group_branch_prefix", "group/")
    if branch and branch.startswith(group_prefix):
        group_name = branch[len(group_prefix):].split("/")[0].strip()

    # 2. Extract group from supplied labels
    lbl_names = [l.get("name", "") if isinstance(l, dict) else str(l) for l in (labels or [])]
    if not group_name:
        for l in lbl_names:
            if l.startswith("group:"):
                group_name = l[len("group:"):].strip()
                break

    # 3. If missing context and pr_number is present, query GitHub API
    if pr_number and (not group_name or not lbl_names):
        try:
            pr = api(f"repos/{_repo()}/pulls/{pr_number}")
            ref = (pr.get("head") or {}).get("ref", "")
            if not group_name and ref.startswith(group_prefix):
                group_name = ref[len(group_prefix):].split("/")[0].strip()
            pr_labels = [l.get("name", "") for l in pr.get("labels", []) if isinstance(l, dict)]
            lbl_names.extend(pr_labels)
            if not group_name:
                for l in pr_labels:
                    if l.startswith("group:"):
                        group_name = l[len("group:"):].strip()
                        break
        except Exception as err:
            print(f"::warning::API fetch failed ({err}) — advisory pass")
            return gate_result("Predecessor Gate", True, "advisory pass (API unavailable)")

    deps = pol.get("group_dependencies") or DEFAULT_PREDECESSOR_POLICY["group_dependencies"]
    pred = deps.get(group_name)
    if not pred:
        return gate_result("Predecessor Gate", True, f"group '{group_name or 'none'}' has no predecessor constraint")

    hold_label = pol.get("hold_label", "queue:hold")
    has_hold = hold_label in lbl_names

    # Check if predecessor group is unmerged
    pred_unmerged = False
    try:
        open_prs = api(f"repos/{_repo()}/pulls?state=open&per_page=100") or []
        for p in open_prs:
            h_ref = (p.get("head") or {}).get("ref", "")
            if h_ref == f"group/{pred}":
                pred_unmerged = True
                break
        if not pred_unmerged:
            open_issues = api(f"repos/{_repo()}/issues?state=open&labels=group:{pred}&per_page=100") or []
            if open_issues:
                pred_unmerged = True
    except Exception as err:
        print(f"::warning::could not check predecessor group status ({err}) — assuming in-flight")
        pred_unmerged = True

    ok, msg = check_predecessor_hold(group_name, has_hold, pred_unmerged, pol)
    return gate_result("Predecessor Gate", ok, msg)


# ─────────────────────────────── CLI ───────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="SupremeAI Automated System Gates")
    parser.add_argument(
        "gate",
        choices=["verification", "scope", "lease", "self_merge", "test_guard", "predecessor", "all"],
    )
    parser.add_argument("--pr", type=int, default=0, help="PR number (for scope gate)")
    parser.add_argument("--title", default="", help="PR title (else fetched via API)")
    parser.add_argument("--body", default="", help="PR body (else fetched via API)")
    parser.add_argument("--author", default="", help="PR author login (else fetched)")
    parser.add_argument("--branch", default="", help="PR head branch (else fetched)")
    parser.add_argument("--author-association", default="", help="PR author association")
    parser.add_argument("--rules", default=str(RULES_PATH), help="path to rules.yml")
    args = parser.parse_args()

    policies = load_policies(Path(args.rules))
    failures: list = []
    needs_ctx = args.gate in ("verification", "all", "scope", "self_merge", "test_guard", "predecessor") or (
        args.gate == "lease" and not (args.author and args.branch)
    )
    if needs_ctx and args.pr:
        title, body, author, branch, assoc = _resolve_pr_context(args)
    else:
        title, body, author, branch, assoc = (
            args.title, args.body, args.author, args.branch, args.author_association,
        )

    if args.gate in ("verification", "all"):
        rc = run_verification_gate(body, policies["verification_policy"])
        if rc:
            failures.append("verification")

    if args.gate in ("lease", "all"):
        rc = run_lease_gate(author, branch, policies["lease_policy"])
        if rc:
            failures.append("lease")

    if args.gate in ("scope", "all"):
        rc = run_scope_gate(args.pr, assoc or "NONE", title, body, policies["scope_policy"])
        if rc:
            failures.append("scope")

    if args.gate in ("self_merge", "all"):
        rc = run_self_merge_gate(args.pr, policies.get("self_merge_policy") or {})
        if rc:
            failures.append("self_merge")

    if args.gate in ("test_guard", "all"):
        rc = run_test_guard_gate(args.pr, policies.get("test_guard_policy") or {})
        if rc:
            failures.append("test_guard")

    if args.gate in ("predecessor", "all"):
        rc = run_predecessor_gate(
            args.pr, branch=branch, labels=[], policy=policies.get("predecessor_policy") or {}
        )
        if rc:
            failures.append("predecessor")

    if failures:
        print(f"[FAILED] System gates failed: {', '.join(failures)}")
        return 1
    print("[PASSED] System gates: all requested gates green.")
    return 0


def _resolve_pr_context(args) -> tuple:
    """Fetch PR metadata from API when not supplied via flags."""
    if args.pr and os.environ.get("SYSTEM_GATES_SKIP_API") != "1":
        try:
            pr = gh_api(f"repos/{_repo()}/pulls/{args.pr}")
            return (
                pr.get("title", ""),
                pr.get("body") or "",
                (pr.get("user") or {}).get("login", ""),
                (pr.get("head") or {}).get("ref", ""),
                pr.get("author_association", "NONE"),
            )
        except Exception as err:  # noqa: BLE001
            print(f"::warning::API fetch failed ({err}) — using supplied flags")
    return args.title, args.body, args.author, args.branch, args.author_association


if __name__ == "__main__":
    raise SystemExit(main())
