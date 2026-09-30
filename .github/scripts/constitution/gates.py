"""Automated System Gates (Issue #2251 — Phase 5 governance flip).

বাংলা: AGENTS.md v2-এর "prose → gate" রূপান্তরের সক্রিয় gate:
  1. Verification Gate — PR description-এ Test Evidence (টেস্ট লগ) বাধ্যতামূলক।
  2. Scope Gate       — claim comment-এর "Touching files:" বাইরের ফাইল বদলালে BLOCK।
  3. Lease Gate       — bot PR-এর branch অবশ্যই লেখকের leased slot-এর ভেতরে হতে হবে।
  4. Claim Gate (#2644) — PR লেখকের linked issue-এ valid claim থাকতে হবে
     (claim-before-work: claim ছাড়া PR = BLOCK; এজেন্ট-লেখক কখনো exempt নয়)।

প্রতিটি gate-এর থ্রেশহোল্ড/পলিসি `.github/constitution/rules.yml`-এ থাকে
(machine-readable constitution) — এই মডিউল শুধু সেটা পড়ে enforce করে।

CLI:
    PYTHONPATH=.github/scripts python -m constitution.gates verification --pr 123
    PYTHONPATH=.github/scripts python -m constitution.gates scope --pr 123
    PYTHONPATH=.github/scripts python -m constitution.gates lease --pr 123
    PYTHONPATH=.github/scripts python -m constitution.gates claim --pr 123
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
import urllib.parse
import urllib.request
from pathlib import Path

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

# Claim Gate (#2644 — claim-before-work, "No Claim, No PR").
# বাংলা: এজেন্ট নিয়ম — claim সফল না হওয়া পর্যন্ত কাজ শুরু করা যাবে না;
# claim ছাড়া খোলা PR গেটেই BLOCK হবে। মানুষ (OWNER/MEMBER/COLLABORATOR)
# advisory পান, কিন্তু supremeai-* বট-লেখক কখনো advisory পান না —
# association যা-ই হোক (8-PRs-in-flight root cause: OWNER-associated app
# বট scope gate-এর advisory_authors দিয়ে ফাঁক গলে বেরিয়ে যেত)।
DEFAULT_CLAIM_POLICY = {
    "unclaimed_pr": "block",              # block | warn
    "missing_issue_ref": "block",         # PR body/title-এ issue pointer নেই
    "agent_author_prefixes": ["supremeai-", "app/supremeai-"],
    "advisory_authors": ["OWNER", "MEMBER", "COLLABORATOR"],  # humans only
    "exempt_authors": ["dependabot[bot]", "app/dependabot", "github-actions[bot]", "renovate[bot]"],
    "claim_comment_marker": "Atomic Claim",
    "agent_field_regex": r"\*\*Agent:\*\*\s*`([^`]+)`",
    "in_progress_label": "status:in-progress",
    "group_branch_prefix": "group/",
}

# Discovery Gate policy defaults (#2528 — Charter Rule #7 enforcement)
DEFAULT_DISCOVERY_POLICY = {
    "undisclosed_discovery": "block",  # block | warn — মার্কার আছে, রেফারেন্স নেই
}

# বাংলা মন্তব্য (#2745, 99.99/0.01 আইন): সংবেদনশীল ইস্যুর (gate:admin-approval)
# PR-মার্জের আগে অ্যাডমিন-অনুমোদনের রেকর্ড বাধ্যতামূলক — unapproved_sensitive_issue।
DEFAULT_ADMIN_APPROVAL_POLICY = {
    "gate_label": "gate:admin-approval",
    "approved_label": "approved-by:admin",
    "approve_comment_patterns": ["/approve", "approved-by:admin"],
    "admin_associations": ["OWNER", "MEMBER"],
    "unapproved_sensitive_issue": "block",  # block | warn
}

# বাংলা মন্তব্য (#2745, 99.99/0.01 আইন): সংবেদনশীল ইস্যুর (gate:admin-approval)
# PR-মার্জের আগে অ্যাডমিন-অনুমোদনের রেকর্ড বাধ্যতামূলক — unapproved_sensitive_issue।
DEFAULT_ADMIN_APPROVAL_POLICY = {
    "gate_label": "gate:admin-approval",
    "approved_label": "approved-by:admin",
    "approve_comment_patterns": ["/approve", "approved-by:admin"],
    "admin_associations": ["OWNER", "MEMBER"],
    "unapproved_sensitive_issue": "block",  # block | warn
}

DEFAULT_DOCS_GARBAGE_POLICY = {
    "non_allowlisted_new_docs": "block",
    "allowed_patterns": [
        "docs/master_docs/**",
        "docs/agents/**",
        "docs/architecture/**",
        "docs/governance/**",
        "docs/INDEX.md",
        "docs/ROADMAP.md",
        "docs/DOCUMENTATION_MASTER_INDEX.md",
        "docs/SECRETS_OPERATIONS.md",
        "docs/SKIPPED_TESTS.md",
        "docs/CAPABILITY_INVENTORY.md",
    ],
}


# ─────────────────────────── policy loading ───────────────────────────

def load_policies(rules_path: Path | None = None) -> dict:
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
            "claim_policy": dict(DEFAULT_CLAIM_POLICY),
            "discovery_policy": dict(DEFAULT_DISCOVERY_POLICY),
            "docs_garbage_policy": dict(DEFAULT_DOCS_GARBAGE_POLICY),
            "admin_approval_policy": dict(DEFAULT_ADMIN_APPROVAL_POLICY),
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
            "claim_policy": dict(DEFAULT_CLAIM_POLICY),
            "discovery_policy": dict(DEFAULT_DISCOVERY_POLICY),
            "docs_garbage_policy": dict(DEFAULT_DOCS_GARBAGE_POLICY),
            "admin_approval_policy": dict(DEFAULT_ADMIN_APPROVAL_POLICY),
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
        "claim_policy": {**DEFAULT_CLAIM_POLICY, **(data.get("claim_policy") or {})},
        "discovery_policy": {**DEFAULT_DISCOVERY_POLICY, **(data.get("discovery_policy") or {})},
        "docs_garbage_policy": {**DEFAULT_DOCS_GARBAGE_POLICY, **(data.get("docs_garbage_policy") or {})},
        "admin_approval_policy": {**DEFAULT_ADMIN_APPROVAL_POLICY, **(data.get("admin_approval_policy") or {})},
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


def gh_api(endpoint: str, token: str | None = None) -> object:
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
                # বাংলা মন্তব্য (#2450 scope-block root-cause fix): ডিরেক্টরি
                # ডিক্লারেশন ("docs/plans/") — trailing '/' সহ টোকেন path_re-এ
                # fullmatch হতো না (group-class-এ '/' নেই), তাই ডিরেক্টরি-স্কোপ
                # ডিক্লারেশন কখনোই declared-এ ঢুকতোই না; আবার strip("/") থাকলেও
                # find_undeclared_files()-এর subtree-চুক্তি (docstring: "ends with
                # /") slash ছাড়া কাজ করে না। দুই পাশই সংশোধন: slash-সহ fullmatch
                # চেষ্টা + slash-সংরক্ষণ।
                base = token.removesuffix("/") if token.endswith("/") else token
                if path_re.fullmatch(base) or re.fullmatch(r"[\w.@*-]+", base):
                    declared.add(token if token.endswith("/") else token.strip("/"))
            elif re.fullmatch(r"\w+", token):
                # বাংলা মন্তব্য (#2612): বর্ধন-বিহীন, slash-বিহীন রুট-ফাইল —
                # "Dockerfile", "Makefile", "Caddyfile" ক্লাস। আগের শর্তে
                # ('/' বা '.') এরা কখনোই ঢুকত না → রুট Dockerfile কোনোভাবেই
                # ডিক্লেয়ার অসম্ভব (লাইভ প্রমাণ PR #2671: ডিক্লেয়ার করা
                # সত্ত্বেও Scope Gate BLOCK)। এই লাইনটুকুই agent-এর নিজের
                # লেখা ডিক্লারেশন — টোকেনগুলো ডিক্লেয়ারই ধরা হোক।
                declared.add(token)

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


# ─────────────────────── Discovery Disclosure Gate (#2528) ───────────────────────

# Charter Rule #7: discovery পেলে issue ফাইল বাধ্যতামূলক। দুই-অংশের টাইট
# প্যাটার্ন — একা 'found'/'discovered' শব্দে prose false-positive হয় না।
DISCOVERY_MARKER_RE = re.compile(
    r"(?:discovered|found|পাওয়া গেছে|দেখা গেছে|gap in|গ্যাপ পাওয়া)[^\n]{0,160}?"
    r"(?:bug|vulnerability|root[- ]cause|regression|race|বাগ|দুর্বলতা)",
    re.IGNORECASE,
)
DISCOVERY_REF_RE = re.compile(r"discovery issue:?\s*#?(\d+)", re.IGNORECASE)


def run_discovery_gate(pr_body: str, policy: dict) -> int:
    """Discovery Disclosure Gate (#2528 — Charter Rule #7-এর flywheel প্লাগইন)।

    scripts/agents/create_discovery_issue.py full-featured (severity, dedup,
    dry-run) ছিল কিন্তু শূন্য caller — নিয়ম ছিল, enforcement ছিল না; discovery
    গুলো PR comment-এই মরে যেত। চুক্তি: PR body-তে discovery-মার্কার থাকলে
    'Discovery issue: #N' রেফারেন্স বাধ্যতামূলক (স্ক্রিপ্ট ফাইল করে লাইনটি
    প্রিন্ট করে দেয়)। মার্কার না থাকলে কিছু চাই না।
    """
    body = pr_body or ""
    markers = DISCOVERY_MARKER_RE.findall(body)
    if not markers:
        print("[PASSED] Discovery Gate: no discovery markers in PR body")
        return 0
    refs = DISCOVERY_REF_RE.findall(body)
    if refs:
        shown = ", #".join(refs[:5])
        print(
            f"[PASSED] Discovery Gate: {len(markers)} marker(s), disclosed as "
            f"Discovery issue #{shown} (Charter Rule #7)"
        )
        return 0
    msg = (
        f"{len(markers)} discovery marker(s) in PR body but no 'Discovery issue: #N' "
        "reference. Charter Rule #7: file it via `python scripts/agents/"
        "create_discovery_issue.py --parent-issue <N> --title ... --body ...` "
        "(the script prints the paste-ready line), then add the "
        "'Discovery issue: #N' line to the PR body."
    )
    return gate_result("Discovery Gate", False, msg)


# ─────────────────────── Zero-Garbage Docs Gate (#2450) ───────────────────────

def run_docs_garbage_gate(pr_number: int, policy: dict) -> int:
    """Zero-Garbage Docs Gate — issue #2450 থেকে স্থায়ী হলো (2026-09-28 prune-এর পর)।

    # বাংলা মন্তব্য: 'GitHub Issues as Live Operational Truth' দর্শন বজায় রাখতে
    # docs/ স্প্রল আর জমতে দেওয়া হবে না। PR-এ docs/ এর ভেতরে নতুন .md যোগ হলে
    # allowlist প্যাটার্নের (rules.yml → docs_garbage_policy.allowed_patterns) ভেতরে
    # হতে হবে — বাইরে হলে BLOCK। 'modified/changed' ফাইল (আপডেট) আউট-অব-স্কোপ:
    # শুধু নতুন ফাইল (added/copied) গার্ড হয়। API down হলে advisory pass (CI
    # uptime-এর উপর hard-depend নিষিদ্ধ — test gate-এর মতোই)।
    """
    try:
        files = gh_api(f"repos/{_repo()}/pulls/{pr_number}/files?per_page=100") or []
    except Exception as err:  # noqa: BLE001 — CI cannot hard-depend on API uptime
        print(f"::warning::docs garbage check unavailable ({err}) — advisory pass")
        return gate_result("Docs Garbage Guard", True, "advisory pass (API unavailable)")

    if policy.get("wired") is False:
        return gate_result("Docs Garbage Guard", True, "wired=false — advisory mode")

    patterns = policy.get("allowed_patterns") or []
    offenders: list[str] = []
    added_md = 0
    for f in files:
        fn = f.get("filename", "")
        if f.get("status") not in ("added", "copied"):
            continue
        if not fn.startswith("docs/") or not fn.endswith(".md"):
            continue
        added_md += 1
        if not path_matches_any(fn, patterns):
            offenders.append(fn)
            if len(offenders) >= 5:
                break
    if offenders and policy.get("non_allowlisted_new_docs", "block") == "block":
        return gate_result(
            "Docs Garbage Guard", False,
            "নতুন docs/*.md allowlist-বাহির্ভূত (docs/INDEX.md হালনাগাদ করো বা master_docs/ ব্যবহার করো): "
            + ", ".join(offenders),
        )
    return gate_result("Docs Garbage Guard", True, f"{added_md} new docs/*.md, all allowlisted")


# ─────────────────────── Admin-Approval Gate (#2745) ───────────────────────

def run_admin_approval_gate(pr_number: int, title: str, body: str, policy: dict, api=None) -> int:
    """#2745 (99.99/0.01 আইন): সংবেদনশীল ইস্যুর PR-মার্জের আগে অ্যাডমিন-অনুমোদন যাচাই।

    বাংলা মন্তব্য: লিংকড ইস্যুতে ``gate:admin-approval`` লেবেল থাকলে —
    (a) ``approved-by:admin`` লেবেল, বা (b) OWNER/MEMBER-অ্যাসোসিয়েশন কমেন্টারের
    ``/approve`` / ``approved-by:admin`` কমেন্ট — যেকোনো একটির রেকর্ড থাকতে হবে।
    না থাকলে BLOCK (fail-closed): অ্যাডমিনের ০.০১% শাসন-স্তর এজেন্ট বাইপাস করতে
    পারবে না। গেট-না-থাকা সাধারণ ইস্যুতে কোনো প্রভাব নেই। API-down হলেও
    fail-closed — নিরাপত্তা-গেট অনুমোদন-বাইপাসের অজুহাত হতে পারে না।
    """
    if not pr_number:
        return gate_result("Admin-Approval Gate", True, "no PR context — advisory pass")
    api = api or gh_api

    nums = find_linked_issue_numbers(title, body)
    if not nums:
        return gate_result("Admin-Approval Gate", True, "no linked issue — not a sensitive-issue PR")

    gate_label = str(policy.get("gate_label") or "gate:admin-approval")
    approved_label = str(policy.get("approved_label") or "approved-by:admin")
    approve_patterns = [
        p.lower() for p in (policy.get("approve_comment_patterns") or ["/approve"])
    ]
    admin_assocs = set(policy.get("admin_associations") or ["OWNER", "MEMBER"])

    for num in nums[:3]:
        try:
            issue = api(f"repos/{_repo()}/issues/{num}") or {}
        except Exception as err:  # noqa: BLE001 — security gate: fail-closed
            return gate_result(
                "Admin-Approval Gate", False,
                f"issue #{num} lookup failed ({err}) — sensitive-issue gate stays closed (fail-closed)",
            )
        labels = [str(l.get("name", "")) for l in (issue.get("labels") or [])]
        if gate_label not in labels:
            continue  # এই ইস্যু গেটেড নয় — পরের লিংকড ইস্যু দেখো
        if approved_label in labels:
            continue  # লেবেল-অনুমোদন রেকর্ডেড
        # অ্যাডমিন-কমেন্ট অনুমোদন খোঁজো
        try:
            comments = api(f"repos/{_repo()}/issues/{num}/comments?per_page=100") or []
        except Exception as err:  # noqa: BLE001
            return gate_result(
                "Admin-Approval Gate", False,
                f"issue #{num} comments lookup failed ({err}) — fail-closed",
            )
        for c in comments:
            author_assoc = str(c.get("author_association") or "").upper()
            body_c = str(c.get("body") or "").lower()
            if author_assoc in admin_assocs and any(p in body_c for p in approve_patterns):
                break  # অ্যাডমিন-অনুমোদন কমেন্ট পাওয়া গেছে
        else:
            if policy.get("unapproved_sensitive_issue", "block") == "block":
                return gate_result(
                    "Admin-Approval Gate", False,
                    f"sensitive issue #{num} carries `{gate_label}` but no admin approval "
                    f"recorded (`{approved_label}` label or admin /approve comment required) "
                    "— 99.99/0.01 law: merge blocked until admin approves",
                )
            print(f"::warning::sensitive issue #{num} unapproved (advisory mode)")
    return gate_result(
        "Admin-Approval Gate", True, "no unapproved sensitive linked issue",
    )


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
    labels: list | None = None,
    policy: dict | None = None,
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


# ─────────────────────── Claim Gate (#2644 — claim-before-work) ───────────────────────

def author_identities(author: str) -> set:
    """Normalize a login/agent-name into its full claim-identity set.

    # বাংলা মন্তব্য: PR author আর claim comment-এর Agent নাম একই সত্তা হতে
    # পারে অনেকগুলো রূপে — ``app/supremeai-planner`` / ``supremeai-planner``,
    # ``supremeai-coder-1-bot[bot]`` / ``supremeai-coder-1-bot`` / ``coder-1``।
    # দুই পাশকেই একই normalization দিয়ে identity-set বানিয়ে intersection
    # মেলানো হয় — exact-match only (substring নয়, যাতে planner-2-কে
    # planner সাবস্ট্রিং দিয়ে ফাঁকি দেওয়া না যায়)।
    """
    ident: set = set()
    a = (author or "").strip()
    if not a:
        return ident
    ident.add(a)
    no_bot = a.removesuffix("[bot]")
    ident.add(no_bot)
    if a.startswith("app/"):
        bare = a[len("app/"):]
        ident.add(bare)
        ident.add(bare.removesuffix("[bot]"))
    m = re.match(r"^supremeai-([a-z0-9]+)-(\d+)(?:-bot)?$", no_bot.removeprefix("app/"))
    if m:
        ident.add(f"{m.group(1)}-{m.group(2)}")
    return {x for x in ident if x}


def extract_claim_agents(comments: list, policy: dict | None = None) -> set:
    """Agent names recorded in 'Atomic Claim' comments on an issue.

    Parses the ``**Agent:** `NAME` `` field posted by atomic_claim.sh (the
    canonical claim audit trail). Comment format drift is tolerated at the
    marker level, but the agent name itself must come from the parsed field —
    never a raw substring of the whole body (spoofable).
    """
    pol = policy or DEFAULT_CLAIM_POLICY
    marker = pol.get("claim_comment_marker", "Atomic Claim")
    agent_re = re.compile(pol.get("agent_field_regex", DEFAULT_CLAIM_POLICY["agent_field_regex"]))
    names: set = set()
    for c in comments or []:
        body = c.get("body", "") if isinstance(c, dict) else str(c)
        if marker not in (body or ""):
            continue
        for m in agent_re.finditer(body):
            name = m.group(1).strip()
            if name:
                names.add(name)
    return names


def claim_matches(author: str, claimer_names: set) -> bool:
    """True iff any claimer name normalizes to the same identity as the author."""
    ids = author_identities(author)
    if not ids:
        return False
    return any(ids & author_identities(name) for name in (claimer_names or set()))


def evaluate_claim(
    author: str,
    association: str,
    linked: list,
    policy: dict,
) -> tuple[bool, str]:
    """Pure evaluation of the claim-before-work rule (#2644).

    ``linked``: list of evidence dicts, one per issue the PR references —
    ``{"number": N, "assignees": [logins], "claim_agents": {names},
    "group_peers": {names}}`` (group_peers: claims on sibling group:<name>
    issues count for group work, #2378).
    """
    author = (author or "").strip()
    exempt = set(policy.get("exempt_authors") or [])
    if author in exempt:
        return True, f"author '{author}' is exempt from claim gate"

    if not linked:
        action = str(policy.get("missing_issue_ref", "block"))
        return (action != "block"), (
            "no linked issue found in PR title/body — a claim cannot be verified "
            "(add '(#N)' to the title or a 'Refs/Closes/Fixes #N' line, Rule #16)"
        )

    for entry in linked or []:
        claimers = set(entry.get("assignees") or [])
        claimers |= set(entry.get("claim_agents") or [])
        claimers |= set(entry.get("group_peers") or [])
        if claim_matches(author, claimers):
            who = ", ".join(sorted(claimers)[:5])
            return True, (
                f"claim verified: '{author}' holds a claim on issue "
                f"#{entry.get('number')} (claimants: {who})"
            )

    nums = [e.get("number") for e in linked]
    prefixes = tuple(p for p in (policy.get("agent_author_prefixes") or []) if p)
    is_agent = bool(author.startswith(prefixes)) if prefixes else False
    advisory = set(policy.get("advisory_authors") or [])

    if is_agent:
        # #2644: এজেন্ট-লেখক কখনো advisory পায় না — OWNER/MEMBER association
        # বট-অ্যাকাউন্টকে claim নিয়মের বাইরে নিতে পারে না (8-PRs-in-flight
        # root cause: scope gate-এর advisory_authors ফাঁক গলে বেরিয়ে গিয়েছিল)।
        return False, (
            f"agent author '{author}' has NO claim on linked issue(s) {nums} — "
            "claim-before-work violated. Run scripts/ci/atomic_claim.sh and WIN "
            "the claim BEFORE opening a PR (No Claim, No PR — #2644). If another "
            "agent already claimed it, pick a different issue."
        )
    if association in advisory:
        print(
            f"::warning::[advisory:{association}] human author '{author}' has no claim "
            f"on issue(s) {nums} — claim-before-work recommended, not enforced for maintainers"
        )
        return True, f"advisory: human author '{author}' ({association}) unclaimed — warn only"
    action = str(policy.get("unclaimed_pr", "block"))
    return (action != "block"), (
        f"author '{author}' has no claim on linked issue(s) {nums} — No Claim, No PR "
        "(Rule 2/20, #2644). Claim the issue first via scripts/ci/atomic_claim.sh."
    )


def _group_claim_peers(api, group_name: str) -> set:
    """Claimer identities across ALL open issues labelled group:<name> (#2378).

    Group PRs reference the closeout issue while members claimed sibling
    issues of the same group — participation anywhere in the group counts.
    Best-effort: API hiccups return an empty set (linked-issue evidence still
    applies).
    """
    peers: set = set()
    try:
        query = (
            "repos/" + _repo() + "/issues?labels="
            + urllib.parse.quote(f"group:{group_name}") + "&state=open&per_page=50"
        )
        issues = api(query) or []
    except Exception:  # noqa: BLE001 — group peer fetch is best-effort
        return peers
    for iss in issues[:10]:
        peers |= {
            (a or {}).get("login", "") for a in iss.get("assignees") or []
        }
        num = iss.get("number")
        try:
            comments = api(f"repos/{_repo()}/issues/{num}/comments?per_page=50") or []
        except Exception:  # noqa: BLE001
            continue
        peers |= extract_claim_agents(comments)
    return {p for p in peers if p}


def run_claim_gate(
    pr_number: int,
    author: str,
    title: str,
    body: str,
    association: str,
    policy: dict,
    api=None,
) -> int:
    """Claim Gate — PR author must hold a valid claim on the linked issue.

    Evidence hierarchy per linked issue (any match counts):
      1. assignees (human-mode atomic claims)
      2. 'Atomic Claim' comment agent names (bot-mode claims — the canonical
         lock per AGENTS.md §3, since App bots 403 on /assignees)
      3. group:<name> sibling claims (group work, #2378)
    Agents (supremeai-* authors) are ALWAYS enforced; humans in
    advisory_authors get warn-only; CI never hard-depends on API uptime.
    """
    api = api or gh_api
    try:
        nums = find_linked_issue_numbers(title or "", body or "")
        if not nums:
            ok, reason = evaluate_claim(author, association, [], policy)
            return gate_result("Claim Gate", ok, reason)

        linked: list = []
        for num in nums[:3]:
            try:
                issue = api(f"repos/{_repo()}/issues/{num}") or {}
                comments = api(f"repos/{_repo()}/issues/{num}/comments?per_page=100") or []
            except Exception as err:  # noqa: BLE001 — per-issue fetch is best-effort
                print(f"::warning::could not fetch issue #{num} ({err}) — evidence skipped")
                continue
            assignees = [
                (a or {}).get("login", "") for a in issue.get("assignees") or []
            ]
            entry = {
                "number": num,
                "assignees": [a for a in assignees if a],
                "claim_agents": extract_claim_agents(comments, policy),
                "group_peers": set(),
            }
            labels = [
                l.get("name", "") for l in issue.get("labels") or [] if isinstance(l, dict)
            ]
            group = next((l[len("group:"):] for l in labels if l.startswith("group:")), "")
            if group:
                entry["group_peers"] = _group_claim_peers(api, group)
            linked.append(entry)

        if not linked:
            # Every linked-issue fetch failed — advisory pass (CI never
            # hard-depends on API uptime; house rule, same as self-merge gate).
            return gate_result("Claim Gate", True, "advisory pass (issue API unavailable)")

        ok, reason = evaluate_claim(author, association, linked, policy)
        return gate_result("Claim Gate", ok, reason)
    except Exception as err:  # noqa: BLE001 — CI cannot hard-depend on API uptime
        print(f"::warning::claim gate check unavailable ({err}) — advisory pass")
        return gate_result("Claim Gate", True, "advisory pass (API unavailable)")


# ─────────────────────────────── CLI ───────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="SupremeAI Automated System Gates")
    parser.add_argument(
        "gate",
        choices=["verification", "scope", "lease", "self_merge", "test_guard", "predecessor", "claim", "discovery", "docs_garbage", "admin_approval", "all"],
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
    needs_ctx = args.gate in ("verification", "all", "scope", "claim", "self_merge", "test_guard", "predecessor", "admin_approval") or (
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

    if args.gate in ("claim", "all"):
        # #2644 claim-before-work: PR author must hold a claim on the linked
        # issue (agents always enforced — association buys no exemption).
        rc = run_claim_gate(
            args.pr, author=author, title=title, body=body,
            association=assoc, policy=policies.get("claim_policy") or {},
        )
        if rc:
            failures.append("claim")

    if args.gate in ("discovery", "all"):
        # #2528 Charter Rule #7 flywheel: discovery-মার্কার থাকলে
        # 'Discovery issue: #N' ডিসক্লোজার বাধ্যতামূলক — স্ক্রিপ্টটি ছিল
        # full-featured কিন্তু শূন্য caller; এখন gate-ই caller-টার চুক্তি এনফোর্স করে।
        rc = run_discovery_gate(body, policies.get("discovery_policy") or {})
        if rc:
            failures.append("discovery")

    if args.gate in ("docs_garbage", "all"):
        rc = run_docs_garbage_gate(args.pr, policies.get("docs_garbage_policy") or {})
        if rc:
            failures.append("docs_garbage")

    if args.gate in ("admin_approval", "all"):
        # #2745 (99.99/0.01 আইন): সংবেদনশীল ইস্যুর PR — অ্যাডমিন-অনুমোদন ছাড়া মার্জ নিষিদ্ধ।
        rc = run_admin_approval_gate(
            args.pr, title=title, body=body,
            policy=policies.get("admin_approval_policy") or {},
        )
        if rc:
            failures.append("admin_approval")

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
