#!/usr/bin/env python3
"""Branch Creation Guard (#2907) — no-branch-without-claim, branch-টাইম enforcement.

Founder directive: "agents can't create branch without creating or claiming issue
… any agent cannot make mistakes by mistake."

PR-টাইম Claim Gate (#2644) ভুল ধরে কিন্তু **দেরিতে** (branch → কাজ → PR → তারপর ব্লক)।
এই guard `on: create` ওয়ার্কফ্লোতে branch-এর জন্মমুহূর্তেই যাচাই করে — violation হলে
branch **delete** + issue-তে বাংলা ব্যাখ্যা-কমেন্ট (self-heal): ভুল branch থেকে কখনো
PR-ই খোলা যাবে না।

যাচাই-চেইন (policy SSOT: rules.yml → branch_creation_policy):
  1. tag → skip (workflow-level; এখানেও ref_type guard)
  2. exempt-প্যাটার্ন (main/group/*/docs/*/dependabot/*…)
  3. slot-registry branch (AGENT_SLOT_REGISTRY.yaml-তালিকাভুক্ত স্লট-ব্রাঞ্চ) → sanctioned
  4. মানুষ (non-agent actor) → advisory-allow (এজেন্ট-পুলিশিং; মানুষ = গভর্নেন্স)
  5. branch-নামে issue-number (≥২ ডিজিট) → না পেলে VIOLATION ("branch without issue")
  6. issue open? → না পেলে/বন্ধ হলে VIOLATION
  7. actor-এর claim ওই issue-তে? (gates.py-র extract_claim_agents + claim_matches
     রিইউজ — #2891 identity-fix সহ) → না পেলে VIOLATION ("no claim, no branch")
     Multi-issue branch (fix/2829-2833-…): যেকোনো একটির claim-ই যথেষ্ট।

Design notes:
  - বিদ্যমান branch-গুলো grandfathered — guard শুধু create-event-এ চলে।
  - API-down → advisory-skip (false-delete নয় — fail-open, কারণ এটা নিরাপত্তা-নয়
    শৃঙ্খলা-গার্ড; PR-টাইম Claim Gate fail-closed থাকে সেতো)।
  - injectable api (session-5 শিক্ষা: টেস্ট-ইনজেকশনে injectable-api প্যারামিটার লাগবেই)।
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gates import claim_matches, extract_claim_agents  # noqa: E402 — same-dir import

RULES_PATH = Path(__file__).resolve().parents[3] / ".github" / "constitution" / "rules.yml"

# বাংলা মন্তব্য: DEFAULT policy — rules.yml-এ branch_creation_policy থাকলে সেটিই জেতে
# (SSOT); এটি শুধু fallback, যাতে rules.yml পাওয়া না গেলেও guard সৎভাবে চলে।
DEFAULT_BRANCH_CREATION_POLICY: dict = {
    "enabled": True,
    "exempt_branch_patterns": [
        "main", "master", "develop",
        "group/*",        # গ্রুপ-গভর্নেন্স lease-gate-এ আলাদা (#2378)
        "docs/*",         # lease-parity: docs_branch_prefix docs/ sanctioned
        "dependabot/*", "renovate/*", "gh-readonly-queue/*",
        "backport/*", "release/*",
    ],
    "slot_registry_path": "docs/master_docs/AGENT_SLOT_REGISTRY.yaml",
    "issue_number_min_digits": 2,   # coder-1-2891-x → 2891; slot-সংখ্যা "1" বাদ
    "require_open_issue": True,
    "require_claim": True,
    "delete_violating_branch": True,
    "skip_delete_if_open_pr": True,
    "comment_on_issue": True,
}


def load_branch_policy(rules_path: Path = RULES_PATH) -> dict:
    """rules.yml → branch_creation_policy (DEFAULT fallback-মার্জ)।

    agent_author_prefixes না থাকলে claim_policy থেকে ওঠে (একই SSOT-সংজ্ঞা)।
    """
    pol = dict(DEFAULT_BRANCH_CREATION_POLICY)
    pol["agent_author_prefixes"] = ["supremeai-", "app/supremeai-"]
    try:
        import yaml

        data = yaml.safe_load(Path(rules_path).read_text(encoding="utf-8")) or {}
        cfg = data.get("branch_creation_policy")
        if isinstance(cfg, dict):
            pol.update(cfg)
        if "agent_author_prefixes" not in (cfg or {}):
            cp = data.get("claim_policy") or {}
            if isinstance(cp, dict) and cp.get("agent_author_prefixes"):
                pol["agent_author_prefixes"] = cp["agent_author_prefixes"]
    except Exception as exc:  # noqa: BLE001 — সৎ fallback, নীরবে মরা নয়
        print(f"⚠️ rules.yml load failed ({exc}) — DEFAULT branch policy fallback")
    return pol


def is_agent_actor(actor: str, policy: dict) -> bool:
    """Actor কি supremeai-* এজেন্ট-আইডেন্টিটি? (মানুষ → advisory-allow)।"""
    a = (actor or "").strip()
    if not a:
        return False
    prefixes = policy.get("agent_author_prefixes") or ["supremeai-", "app/supremeai-"]
    return any(a.startswith(p) for p in prefixes)


def is_exempt_branch(branch: str, patterns) -> bool:
    return any(fnmatch.fnmatch(branch or "", str(p)) for p in (patterns or []))


def slot_registry_branches(registry_path: str | Path) -> set:
    """AGENT_SLOT_REGISTRY.yaml-এ তালিকাভুক্ত slot-branch নাম (sanctioned acquisition)।

    ফাইল না পেলে/পার্স-ব্যর্থ → খালি সেট (fail-open — ভুল exemption নয়)।
    """
    try:
        import yaml

        data = yaml.safe_load(Path(registry_path).read_text(encoding="utf-8")) or {}
    except Exception:
        return set()
    out: set = set()
    for s in data.get("slots") or []:
        if isinstance(s, dict) and s.get("branch"):
            out.add(str(s["branch"]))
    return out


def parse_issue_numbers(branch: str, min_digits: int = 2) -> list:
    """Branch-নামের সব issue-number-প্রার্থী (≥ min_digits ডিজিট, বাম থেকে ডান)।

    coder-1-2891-slug → [2891] (slot "1" = ১-ডিজিট, বাদ) · fix/2829-2833-x → [2829, 2833]
    plan-2841-pr2-x → [2841] ("2" বাদ) · agent-8 → [] (কোনো ২-ডিজিট নম্বর নেই)।
    """
    min_len = max(2, int(min_digits or 2))
    return [int(m.group(0)) for m in re.finditer(r"\d+", branch or "") if len(m.group(0)) >= min_len]


def gh_api(endpoint: str, method: str = "GET", payload: dict | None = None, token: str | None = None):
    """REST call — gh CLI প্রথমে, urllib fallback (gates.gh_api-এর GET-only সংস্করণ থেকে বিস্তৃত)।"""
    try:
        cmd = ["gh", "api", endpoint]
        if method != "GET":
            cmd = ["gh", "api", "-X", method, endpoint]
            if payload is not None:
                cmd += ["--input", "-"]
        res = subprocess.run(
            cmd, input=json.dumps(payload) if (payload is not None and method != "GET") else None,
            capture_output=True, encoding="utf-8", errors="replace", timeout=30, check=True,
        )
        return json.loads(res.stdout) if res.stdout.strip() else {}
    except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError):
        pass
    tok = token or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not tok:
        raise RuntimeError(f"no gh CLI and no token for API call: {endpoint}")
    url = f"https://api.github.com/{endpoint.lstrip('/')}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {tok}")
    req.add_header("Accept", "application/vnd.github+json")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body) if body.strip() else {}


def check_branch(branch: str, actor: str, policy: dict, api=None, repo: str = "") -> tuple:
    """মূল যাচাই। Return (verdict, reason, issue_num) — verdict ∈ {ALLOW, VIOLATION, SKIP}।"""
    api = api or gh_api
    branch = (branch or "").strip()
    actor = (actor or "").strip()

    if not policy.get("enabled", True):
        return "SKIP", "policy disabled — no-op", None
    if not branch:
        return "SKIP", "empty branch name (tag/edge event) — skip", None
    if is_exempt_branch(branch, policy.get("exempt_branch_patterns")):
        return "ALLOW", "exempt branch pattern", None

    registry_path = policy.get("slot_registry_path") or DEFAULT_BRANCH_CREATION_POLICY["slot_registry_path"]
    if branch in slot_registry_branches(registry_path):
        return "ALLOW", "slot-registry branch (sanctioned acquisition)", None

    if not is_agent_actor(actor, policy):
        return "ALLOW", f"actor '{actor}' is human — advisory only", None

    issue_nums = parse_issue_numbers(branch, policy.get("issue_number_min_digits", 2))
    if not issue_nums:
        return "VIOLATION", "branch name carries no issue number — issue ছাড়া branch নিষিদ্ধ", None

    # বাংলা মন্তব্য: multi-issue branch (fix/2829-2833-x) — প্রথম ম্যাচ-হওয়া
    # issue-ই যথেষ্ট; কোনোটিতেই claim না মিললে তবেই violation।
    # 404 = সত্যিকারের not-found (violation-কারণ); অন্য API-error = fail-open skip।
    last_reason = ""
    for num in issue_nums:
        try:
            issue = api(f"repos/{repo}/issues/{num}")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                last_reason = f"issue #{num} not found (404)"
                continue
            return "SKIP", f"issue #{num} lookup failed (HTTP {exc.code}) — advisory skip", num
        except Exception as exc:  # noqa: BLE001 — API-down = সৎ fail-open
            return "SKIP", f"issue #{num} lookup failed (API error: {exc}) — advisory skip", num
        if not isinstance(issue, dict) or issue.get("number") is None:
            last_reason = f"issue #{num} not found"
            continue
        if policy.get("require_open_issue", True) and issue.get("state") != "open":
            last_reason = f"issue #{num} is {issue.get('state')}"
            continue
        if not policy.get("require_claim", True):
            return "ALLOW", f"claim check disabled — issue #{num} open", num
        # claim-evidence: assignee-login অথবা Atomic Claim comment (gates.py reuse)
        assignees = {a.get("login") for a in (issue.get("assignees") or []) if a.get("login")}
        if claim_matches(actor, assignees):
            return "ALLOW", f"assignee-claim verified on #{num}", num
        try:
            comments = api(f"repos/{repo}/issues/{num}/comments?per_page=100")
        except Exception as exc:  # noqa: BLE001
            return "SKIP", f"claim comments fetch failed (API error: {exc}) — advisory skip", num
        claimers = extract_claim_agents(comments if isinstance(comments, list) else [])
        if claim_matches(actor, claimers):
            return "ALLOW", f"Atomic-Claim verified on #{num}", num
        last_reason = f"no claim by '{actor}' on #{num}"
    return "VIOLATION", last_reason or "no claimable issue matched", (issue_nums[0] if issue_nums else None)


VIOLATION_COMMENT = """## 🌿 Branch Creation Guard — branch মুছে ফেলা হয়েছে (`{branch}`)

**Invariant (#2907): issue claim ছাড়া কোনো এজেন্ট branch তৈরি করতে পারবে না।**

- **Actor:** `{actor}`
- **কারণ:** {reason}
- **সময়:** {ts} UTC

### সঠিক পথ (২ ধাপ)
```bash
# ১) আগে claim — atomic, ফাইল-ঘোষণাসহ:
scripts/ci/atomic_claim.sh {issue_num} <agent-name> --skip-assign --files "<ফাইল-তালিকা>"
# ২) তারপর branch — নামে issue-number-সহ (coder-1-{issue_num}-<slug> প্যাটার্ন):
git checkout -b <lane>-<slot>-{issue_num}-<slug>
```

Claim Gate (#2644) PR-এ একই চেক করে — এখন থেকে branch-জন্মেই ধরা পড়বে। 🙏
"""


def enforce(branch: str, actor: str, verdict: str, reason: str, issue_num, policy: dict,
            api=None, repo: str = "") -> list:
    """Violation-অ্যাকশন: issue-কমেন্ট + branch-delete। Return নেওয়া action-তালিকা।"""
    api = api or gh_api
    actions: list = []
    if verdict != "VIOLATION":
        return actions

    if issue_num and policy.get("comment_on_issue", True):
        import datetime

        body = VIOLATION_COMMENT.format(
            branch=branch, actor=actor, reason=reason, issue_num=issue_num,
            ts=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        )
        try:
            api(f"repos/{repo}/issues/{issue_num}/comments", method="POST", payload={"body": body})
            actions.append(f"commented on #{issue_num}")
        except Exception as exc:  # noqa: BLE001
            actions.append(f"comment on #{issue_num} FAILED ({exc})")

    if policy.get("delete_violating_branch", True):
        skip = False
        if policy.get("skip_delete_if_open_pr", True):
            try:
                owner = repo.split("/")[0]
                prs = api(f"repos/{repo}/pulls?head={owner}:{branch}&state=open")
                if prs:
                    skip = True
                    actions.append(f"delete skipped — open PR from '{branch}' (PR-gate দায়ী)")
            except Exception:
                skip = True  # অনিশ্চিত হলে delete করা নিরাপদ নয়
                actions.append("delete skipped — open-PR check failed (conservative)")
        if not skip:
            try:
                api(f"repos/{repo}/git/refs/heads/{branch}", method="DELETE")
                actions.append(f"branch '{branch}' deleted")
            except Exception as exc:  # noqa: BLE001
                actions.append(f"branch delete FAILED ({exc})")
    return actions


def main() -> int:
    ref_type = (os.environ.get("GUARD_REF_TYPE") or "branch").strip().lower()
    if ref_type == "tag":
        print("[SKIP] tag creation — branch guard applies to branches only")
        return 0
    branch = (os.environ.get("GUARD_BRANCH") or os.environ.get("GITHUB_REF") or "").strip()
    branch = branch.removeprefix("refs/heads/")
    actor = (os.environ.get("GUARD_ACTOR") or os.environ.get("GITHUB_ACTOR") or "").strip()
    repo = (os.environ.get("GITHUB_REPOSITORY") or os.environ.get("GUARD_REPO") or "").strip()
    if not branch or not repo:
        print("[SKIP] missing GUARD_BRANCH/GITHUB_REPOSITORY context")
        return 0

    policy = load_branch_policy()
    verdict, reason, issue_num = check_branch(branch, actor, policy, repo=repo)
    actions = enforce(branch, actor, verdict, reason, issue_num, policy, repo=repo)

    line = f"Branch Creation Guard: {verdict} — branch='{branch}' actor='{actor}' :: {reason}"
    print(line)
    for a in actions:
        print(f"  ↳ action: {a}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"### 🌿 Branch Creation Guard\n\n- {line}\n")
            for a in actions:
                fh.write(f"- {a}\n")
    # VIOLATION → exit 1 (Actions-এ লাল দৃশ্যমানতা); SKIP/ALLOW → 0
    return 1 if verdict == "VIOLATION" else 0


if __name__ == "__main__":
    sys.exit(main())
