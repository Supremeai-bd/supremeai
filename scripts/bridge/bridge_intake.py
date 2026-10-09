#!/usr/bin/env python3
"""bridge_intake.py — public→private work bridge (v1).

চুক্তি (contract): scripts/bridge/README.md

Public agents push patch branches (`bridge/<task-id>`) + Bridge Work Order issues
to the PUBLIC repo (paykaribazaronline/supremeai-open). This script — running
INSIDE the private repo — fail-closed validates each order and, if clean,
applies it as a gated private PR. Landing is decided ONLY by the constitutional
gate chain; agents never touch the private repo directly.

Fail-closed invariants:
- কোনো ধাপ অজানা বা ব্যর্থ হলে কাজ apply হয় না — reject/admin-review লেবেল + sanitized reason।
- Public কমেন্টে কখনো টোকেন/সিক্রেট যায় না (sanitize_public_comment + zero-print token discipline)।
- Forbidden paths (.github/*, ledger, key-plane) কখনো auto-apply হয় না — admin-review।

Usage:
  BRIDGE_TOKEN=... python scripts/bridge/bridge_intake.py intake
  BRIDGE_TOKEN=... python scripts/bridge/bridge_intake.py sync
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

OPEN_REPO = "paykaribazaronline/supremeai-open"
PRIVATE_REPO = "paykaribazaronline/supremeai"
PRIVATE_MAIN = "main"

LABEL_QUEUED = "bridge:queued"
LABEL_INGATES = "bridge:in-gates"
LABEL_LANDED = "bridge:landed"
LABEL_REJECTED = "bridge:rejected"
LABEL_ADMIN = "bridge:admin-review"
LABEL_PRIVATE_BRIDGE = "bridge"  # private intake issues carry this label

MARKER_FMT = "<!-- bridge-task: {tid} -->"

TASK_ID_RE = re.compile(r"^bridge-\d{8}-[a-z0-9][a-z0-9-]{2,60}$")
MAX_PATCH_BYTES = 200_000
MAX_FILES = 30

# এই prefix/প্যাটার্নগুলো auto-apply নিষিদ্ধ — owner সিদ্ধান্ত ছাড়া অসম্ভব (admin-review)।
ADMIN_REVIEW_PREFIXES = (".github/", "docs/ledger/", "docs/master_docs/", "prisma/")
ADMIN_REVIEW_SUBSTR = ("secrets_registry", "credential")
ADMIN_REVIEW_SUFFIXES = (".pem", ".key", ".p12")
ENV_PATH_RE = re.compile(r"(^|/)\.env")

# Secret-pattern scan — পরিবারের নাম public কমেন্টে যেতে পারে, মান কখনো নয়।
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("github-app-token", re.compile(r"ghs_[A-Za-z0-9_]{16,}")),
    ("github-classic-pat", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("github-fine-grained-pat", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("openai-style-key", re.compile(r"sk-[A-Za-z0-9_-]{20,}")),
    ("aws-access-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("slack-token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("google-api-key", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("private-key-block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY( BLOCK)?-----")),
    (
        "literal-client-secret",
        re.compile(r"(CLIENT_SECRET|CLIENT_KEY|API_KEY|PASSWORD)\s*[:=]\s*[\"']?[A-Za-z0-9+/=_-]{16,}[\"']?\s*$", re.M),
    ),
    ("credentialed-redis-url", re.compile(r"rediss?://[^@\s]{8,}@[^\s]+")),
]


class BridgeError(Exception):
    """Fail-honest bridge failure — বার্তা sanitized হয়ে জানানো হয়।"""


# ---------------------------------------------------------------------------
# GitHub REST (stdlib only — repo রীতি: ai_pr_evaluator.py-র মতো urllib)
# ---------------------------------------------------------------------------

def gh(method: str, path: str, token: str, payload: dict | None = None) -> tuple[int, dict]:
    url = path if path.startswith("http") else f"https://api.github.com{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "supremeai-bridge-intake",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except Exception:
            return exc.code, {"message": raw[:300]}


def gh_ok(method: str, path: str, token: str, payload: dict | None = None) -> dict:
    status, body = gh(method, path, token, payload)
    if status >= 300:
        raise BridgeError(f"github {method} {path} → HTTP {status}: {str(body.get('message', body))[:200]}")
    return body


# ---------------------------------------------------------------------------
# Work-order parsing + validators (pure — unit-tested)
# ---------------------------------------------------------------------------

def parse_work_order(body: str | None) -> dict:
    """GitHub issue-form rendering: `### Header` sections → field map।"""
    fields: dict[str, list[str]] = {}
    cur: str | None = None
    for line in (body or "").splitlines():
        m = re.match(r"^###\s+(.+?)\s*$", line)
        if m:
            cur = m.group(1)
            fields[cur] = []
            continue
        if cur is not None:
            fields[cur].append(line)
    out = {}
    for key, lines in fields.items():
        val = "\n".join(lines).strip()
        out[key] = "" if val == "_No response_" else val
    return out


def validate_task_id(task_id: str) -> bool:
    return bool(TASK_ID_RE.match(task_id or ""))


def classify_paths(filenames: list[str]) -> tuple[list[str], list[str]]:
    """Return (auto_ok, admin_review) path lists।"""
    ok: list[str] = []
    admin: list[str] = []
    for path in filenames:
        norm = (path or "").replace("\\", "/").lstrip("/")
        if (
            norm.startswith(ADMIN_REVIEW_PREFIXES)
            or any(s in norm.lower() for s in ADMIN_REVIEW_SUBSTR)
            or norm.endswith(ADMIN_REVIEW_SUFFIXES)
            or ENV_PATH_RE.search(norm)
        ):
            admin.append(path)
        else:
            ok.append(path)
    return ok, admin


def scan_secrets(diff_text: str) -> list[str]:
    return [family for family, rx in SECRET_PATTERNS if rx.search(diff_text)]


def sanitize_public_comment(text: str, token: str) -> str:
    """Defense-in-depth: token string + যেকোনো secret-pattern REDACT করা।"""
    if token:
        text = text.replace(token, "[REDACTED-TOKEN]")
    for family, rx in SECRET_PATTERNS:
        text = rx.sub(f"[REDACTED:{family}]", text)
    return text


# ---------------------------------------------------------------------------
# Body builders (gate-compliant: template chain doctrine)
# ---------------------------------------------------------------------------

def build_intake_issue_body(wo: dict, task_id: str, public_url: str, agent: str, files: list[str]) -> str:
    file_lines = "\n".join(f"- `{f}`" for f in files) or "- (none)"
    return "\n".join(
        [
            MARKER_FMT.format(tid=task_id),
            "",
            f"**Bridge source:** {public_url}",
            f"**Agent:** `{agent}`",
            "",
            "### Mission & Problem Statement",
            "External-agent bridge v1 work order — public agent submitted a patch for the",
            "private codebase. Intake validated fail-closed; this issue is the private",
            "audit-trail anchor for the gated landing.",
            "",
            "### Priority Tier",
            "P2-medium",
            "",
            "### Touching Files (Scope Gate Boundary)",
            file_lines,
            "",
            "### 3-Tier Verification Contract",
            "1. **Reflection Check:** work-order summary — " + (wo.get("Summary (what + why)") or "(unspecified)")[:400],
            "2. **Syntax/Boot:** bridge applied patch with `git apply` (clean apply = structural sanity).",
            "3. **Tests:** agent-declared evidence — " + (wo.get("Test Evidence (3-tier contract)") or "(unspecified)")[:600],
            "",
            "### Rollback Path",
            (wo.get("Rollback Path") or "git revert of the bridge-land commit")[:600],
        ]
    )


def build_pr_body(wo: dict, task_id: str, intake_issue: int, public_url: str, agent: str, files: list[str]) -> str:
    file_lines = "\n".join(f"- `{f}`" for f in files) or "- (none)"
    return "\n".join(
        [
            "## Summary",
            f"Bridge v1 import of external work order `{task_id}` (public issue: {public_url}).",
            "",
            (wo.get("Summary (what + why)") or "(no summary provided)")[:800],
            "",
            "## Linked Issue / Claim",
            f"Refs #{intake_issue}",
            "",
            "## Type of Change",
            "- [ ] `fix` — বাগ-ফিক্স",
            "- [x] `feat` — নতুন ক্যাপাবিলিটি (bridge import; adjust if wrong)",
            "- [ ] `chore` / `docs` / `refactor` / `test` / `perf` — সাপোর্টিং কাজ",
            "",
            "## Touching Files (Scope Gate Boundary)",
            file_lines,
            "",
            "## Test Evidence (3-Tier যাচাই-চুক্তি)",
            (wo.get("Test Evidence (3-tier contract)") or "(agent did not declare evidence — gates must judge)")[:1200],
            "",
            "## Rollback Path",
            "- [x] `git revert`-নিরাপদ (bridge-land commit is additive; no schema/data migration)",
            "",
            (wo.get("Rollback Path") or "")[:400],
            "",
            "## Reflection Evidence (why + alternatives_rejected)",
            f"- **why:** external agent contribution via public bridge; agent identity `{agent}`",
            "- **alternatives_rejected:** direct private-repo access (unavailable to public agents by design);"
            " manual owner copy-paste (no audit trail)",
        ]
    )


# ---------------------------------------------------------------------------
# Git plumbing (self-contained tmp clones — works locally AND in Actions)
# ---------------------------------------------------------------------------

def run(cmd: list[str], cwd: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise BridgeError(f"git {' '.join(cmd[:3])}… rc={proc.returncode}: {(proc.stderr or proc.stdout)[-300:]}")
    return proc


def auth_url(repo: str, token: str) -> str:
    return f"https://x-access-token:{token}@github.com/{repo}.git"


def clone(repo: str, token: str, dest: Path, depth: int = 50) -> str:
    run(["git", "clone", "--quiet", f"--depth={depth}", auth_url(repo, token), str(dest)])
    return str(dest)


def fetch_patch(public_dir: str, branch: str, token: str) -> tuple[str, list[str]]:
    """Branch প্রমাণ (ls-remote) → explicit refspec fetch → (diff, files)।

    বাংলা: `git fetch origin <branch>` FETCH_HEAD-এ রাখে, remote-tracking ref তৈরি করে না —
    তাই explicit refspec বাধ্যতামূলক (E2E-তে প্রমাণিত বাগ)।
    """
    ls = run(["git", "ls-remote", "origin", f"refs/heads/{branch}"], cwd=public_dir, check=False)
    if ls.returncode != 0 or not ls.stdout.strip():
        raise BridgeError(f"patch branch '{branch}' not found on {OPEN_REPO}")
    run(
        ["git", "fetch", "--quiet", "origin", f"refs/heads/{branch}:refs/remotes/origin/{branch}"],
        cwd=public_dir,
    )
    diff = run(["git", "diff", f"origin/main...origin/{branch}"], cwd=public_dir).stdout
    files_out = run(["git", "diff", "--name-only", f"origin/main...origin/{branch}"], cwd=public_dir).stdout
    files = [line.strip() for line in files_out.splitlines() if line.strip()]
    return diff, files


# ---------------------------------------------------------------------------
# Issue/label helpers
# ---------------------------------------------------------------------------

def ensure_label(repo: str, token: str, name: str, color: str, description: str) -> None:
    status, _ = gh("POST", f"/repos/{repo}/labels", token, {"name": name, "color": color, "description": description})
    if status not in (201, 422):  # 422 = already exists
        raise BridgeError(f"label create {name} → HTTP {status}")


def set_labels(repo: str, token: str, issue: int, labels: list[str]) -> None:
    gh_ok("PUT", f"/repos/{repo}/issues/{issue}/labels", token, {"labels": labels})


def comment_issue(repo: str, token: str, issue: int, body: str) -> None:
    gh_ok("POST", f"/repos/{repo}/issues/{issue}/comments", token, {"body": body})


def already_intaked(token: str, task_id: str) -> bool:
    """Private repo-তে marker-carrying intake issue আগেই আছে কি না (list API — fresh, search-lag মুক্ত)।"""
    status, issues = gh("GET", f"/repos/{PRIVATE_REPO}/issues?labels={LABEL_PRIVATE_BRIDGE}&state=all&per_page=100", token)
    if status != 200:
        return True  # fail-closed: state unknown → duplicate-ঝুঁকির চেয়ে না-apply ভালো
    marker = MARKER_FMT.format(tid=task_id)
    return any(marker in (i.get("body") or "") for i in issues)


# ---------------------------------------------------------------------------
# Core flows
# ---------------------------------------------------------------------------

def process_issue(issue: dict, token: str, work: Path, results: list[str]) -> None:
    num = issue["number"]
    public_url = issue.get("html_url", f"https://github.com/{OPEN_REPO}/issues/{num}")
    wo = parse_work_order(issue.get("body"))
    task_id = (wo.get("Task ID") or "").strip()
    branch = (wo.get("Patch Branch") or "").strip()
    agent = (wo.get("Agent Identity") or "unknown-agent").strip()[:120]

    def reject(reason: str, label: str = LABEL_REJECTED) -> None:
        body = sanitize_public_comment(
            "## 🌉 Bridge Intake — **" + label.split(":")[-1].upper() + "**\n\n"
            f"- task: `{task_id or '(unparseable)'}`\n"
            f"- reason: {reason}\n\n"
            "Fail-closed bridge v1 — কোনো patch private repo-তে apply হয়নি।",
            token,
        )
        comment_issue(OPEN_REPO, token, num, body)
        set_labels(OPEN_REPO, token, num, [label])
        results.append(f"#{num} → {label}: {reason[:80]}")

    if not validate_task_id(task_id):
        reject(f"invalid Task ID format (`{task_id or 'missing'}`) — need `bridge-YYYYMMDD-<slug>`")
        return
    if not branch:
        reject("missing Patch Branch field")
        return

    if already_intaked(token, task_id):
        set_labels(OPEN_REPO, token, num, [LABEL_INGATES])
        results.append(f"#{num} → skip (already intaked: {task_id})")
        return

    # Patch fetch + structural validation
    public_dir = str(work / f"open-{num}")
    clone(OPEN_REPO, token, Path(public_dir))
    try:
        diff, files = fetch_patch(public_dir, branch, token)
    except BridgeError as exc:
        reject(str(exc)[:300])
        return

    if len(diff.encode("utf-8", "replace")) > MAX_PATCH_BYTES:
        reject(f"patch too large ({len(diff)} bytes > {MAX_PATCH_BYTES})")
        return
    if len(files) > MAX_FILES:
        reject(f"too many files ({len(files)} > {MAX_FILES})")
        return

    ok_paths, admin_paths = classify_paths(files)
    if admin_paths:
        body = sanitize_public_comment(
            "## 🌉 Bridge Intake — **ADMIN-REVIEW**\n\n"
            f"- task: `{task_id}`\n"
            "- protected paths present (never auto-applied):\n"
            + "".join(f"  - `{p}`\n" for p in admin_paths[:15])
            + "\nOwner decision প্রয়োজন — manual review lane।",
            token,
        )
        comment_issue(OPEN_REPO, token, num, body)
        set_labels(OPEN_REPO, token, num, [LABEL_ADMIN])
        results.append(f"#{num} → admin-review ({len(admin_paths)} protected files)")
        return

    families = scan_secrets(diff)
    if families:
        reject("secret-pattern scan hit: " + ", ".join(families) + " — remove secrets and resubmit")
        return

    # Apply inside the private repo
    private_dir = str(work / f"priv-{num}")
    clone(PRIVATE_REPO, token, Path(private_dir))
    run(["git", "config", "user.name", "supremeai-bridge"], cwd=private_dir)
    run(["git", "config", "user.email", "bridge@supremeai.local"], cwd=private_dir)
    run(["git", "checkout", "--quiet", "-b", f"bridge-land/{task_id}", f"origin/{PRIVATE_MAIN}"], cwd=private_dir)
    patch_file = work / f"patch-{num}.diff"
    patch_file.write_text(diff, encoding="utf-8")
    applied = run(["git", "apply", "--whitespace=nowarn", str(patch_file)], cwd=private_dir, check=False)
    if applied.returncode != 0:
        reason = (applied.stderr or "patch does not apply to current main")[-250:]
        reject(f"patch failed to apply on current {PRIVATE_MAIN}: {reason}")
        return
    run(["git", "add", "-A"], cwd=private_dir)
    run(
        [
            "git", "commit", "--quiet", "-m",
            f"bridge({task_id}): external work order #{num}",
            "-m", f"Agent: {agent}\nBridge-Source: {public_url}\nApplied-by: bridge_intake.py v1 (fail-closed intake)",
        ],
        cwd=private_dir,
    )
    push = run(["git", "push", "--quiet", "origin", f"bridge-land/{task_id}"], cwd=private_dir, check=False)
    if push.returncode != 0:
        reject(f"private push rejected: {(push.stderr or 'unknown')[-200:]}")
        return
    head_sha = run(["git", "rev-parse", "HEAD"], cwd=private_dir).stdout.strip()

    # Private audit-trail issue + gated PR
    ensure_label(PRIVATE_REPO, token, LABEL_PRIVATE_BRIDGE, "5319E7", "bridge-intake external work order")
    intake_body = build_intake_issue_body(wo, task_id, public_url, agent, files)
    intake = gh_ok(
        "POST", f"/repos/{PRIVATE_REPO}/issues", token,
        {"title": f"feat(bridge): {task_id}", "body": intake_body, "labels": [LABEL_PRIVATE_BRIDGE]},
    )
    pr = gh_ok(
        "POST", f"/repos/{PRIVATE_REPO}/pulls", token,
        {
            "title": f"feat(bridge): {task_id} — external work order #{num}",
            "head": f"bridge-land/{task_id}",
            "base": PRIVATE_MAIN,
            "body": build_pr_body(wo, task_id, intake["number"], public_url, agent, files),
        },
    )
    report = sanitize_public_comment(
        "## 🌉 Bridge Intake — **APPLIED** (in gates now)\n\n"
        f"- task: `{task_id}`\n"
        f"- private PR: **#{pr['number']}** — full constitutional gate chain decides landing\n"
        f"- head: `{head_sha[:10]}`\n"
        f"- files: {len(files)}\n\n"
        "এরপর label-চেইন ফলো করুন: `bridge:in-gates → bridge:landed`।",
        token,
    )
    comment_issue(OPEN_REPO, token, num, report)
    set_labels(OPEN_REPO, token, num, [LABEL_INGATES])
    results.append(f"#{num} → applied, private PR #{pr['number']} ({task_id})")


def cmd_intake(token: str) -> int:
    status, issues = gh("GET", f"/repos/{OPEN_REPO}/issues?labels={LABEL_QUEUED}&state=open&per_page=30", token)
    if status != 200:
        raise BridgeError(f"queue fetch failed: HTTP {status}")
    workorders = [i for i in issues if "pull_request" not in i]
    results: list[str] = []
    with tempfile.TemporaryDirectory(prefix="bridge-") as tmp:
        work = Path(tmp)
        for issue in workorders:
            try:
                process_issue(issue, token, work, results)
            except BridgeError as exc:
                results.append(f"#{issue['number']} → ERROR (honest): {str(exc)[:120]}")
            except Exception as exc:  # noqa: BLE001 — fail-honest per-issue, loop continues
                results.append(f"#{issue['number']} → UNEXPECTED: {type(exc).__name__}: {str(exc)[:120]}")
    print("== bridge intake ==")
    for line in results or ["queue empty"]:
        print(" -", line)
    unexpected = [r for r in results if "UNEXPECTED" in r or "ERROR" in r]
    return 2 if unexpected else 0


def cmd_sync(token: str) -> int:
    """PR lifecycle → public issue reporting (landed / rejected)।"""
    results: list[str] = []
    status, pulls = gh("GET", f"/repos/{PRIVATE_REPO}/pulls?state=closed&sort=updated&per_page=40", token)
    if status != 200:
        raise BridgeError(f"PR fetch failed: HTTP {status}")
    # বাংলা (#65): list-pulls response-এ boolean "merged" ফিল্ড থাকে না (শুধু
    # single-GET-এ) — থাকে "merged_at"। p.get("merged") সবসময় None → merged PR-ও
    # rejected হত (লাইভ-প্রমাণিত: PR #40 landed হয়েও bridge:rejected পেয়েছিল)।
    landed = [p for p in pulls if (p.get("head") or {}).get("ref", "").startswith("bridge-land/") and p.get("merged_at")]
    rejected = [p for p in pulls if (p.get("head") or {}).get("ref", "").startswith("bridge-land/") and not p.get("merged_at")]

    status, open_issues = gh("GET", f"/repos/{OPEN_REPO}/issues?state=open&per_page=60", token)
    if status != 200:
        raise BridgeError(f"open issues fetch failed: HTTP {status}")
    open_issues = [i for i in open_issues if "pull_request" not in i]

    def find_issue(task_id: str) -> dict | None:
        # বাংলা: EXACT Task-ID match — substring-ম্যাচ v1/v2-prefix কনফিউশন তৈরি করে
        # (E2E-তে প্রমাণিত: "bridge-...-smoke" "bridge-...-smoke-v2"-র ভেতরে ম্যাচ করেছিল)।
        for issue in open_issues:
            wo_i = parse_work_order(issue.get("body"))
            if (wo_i.get("Task ID") or "").strip() == task_id:
                return issue
        return None

    def issue_labels(issue: dict) -> list[str]:
        return [l.get("name", "") for l in (issue.get("labels") or [])]

    for pr in landed:
        task_id = pr["head"]["ref"].replace("bridge-land/", "", 1)
        issue = find_issue(task_id)
        if not issue:
            continue
        body = sanitize_public_comment(
            "## ✅ Bridge — **LANDED**\n\n"
            f"- task: `{task_id}`\n"
            f"- merged private PR: **#{pr['number']}** @ `{(pr.get('merge_commit_sha') or '')[:10]}`\n\n"
            "কাজটি private codebase-এ merge হয়েছে (gates সব সবুজ)।",
            token,
        )
        comment_issue(OPEN_REPO, token, issue["number"], body)
        set_labels(OPEN_REPO, token, issue["number"], [LABEL_LANDED])
        gh("PATCH", f"/repos/{OPEN_REPO}/issues/{issue['number']}", token, {"state": "closed", "state_reason": "completed"})
        results.append(f"{task_id} → landed (PR #{pr['number']})")

    for pr in rejected[-10:]:
        task_id = pr["head"]["ref"].replace("bridge-land/", "", 1)
        issue = find_issue(task_id)
        if not issue:
            continue
        body = sanitize_public_comment(
            "## ❌ Bridge — **REJECTED**\n\n"
            f"- task: `{task_id}`\n"
            f"- private PR **#{pr['number']}** merged হয়নি (gates/owner সিদ্ধান্ত)।",
            token,
        )
        comment_issue(OPEN_REPO, token, issue["number"], body)
        set_labels(OPEN_REPO, token, issue["number"], [LABEL_REJECTED])
        results.append(f"{task_id} → rejected (PR #{pr['number']})")

    # Reconciliation: OPEN bridge PR → public issue অবশ্যই bridge:in-gates হবে
    # (stale লেবেল শুদ্ধ করে — E2E-তে প্রমাণিত কেস: ভুল rejected লেবেল আটকে ছিল)।
    status, open_pulls = gh("GET", f"/repos/{PRIVATE_REPO}/pulls?state=open&per_page=40", token)
    if status == 200:
        for pr in open_pulls:
            ref = (pr.get("head") or {}).get("ref", "")
            if not ref.startswith("bridge-land/"):
                continue
            task_id = ref.replace("bridge-land/", "", 1)
            issue = find_issue(task_id)
            if issue and LABEL_INGATES not in issue_labels(issue):
                set_labels(OPEN_REPO, token, issue["number"], [LABEL_INGATES])
                results.append(f"{task_id} → reconciled to in-gates (PR #{pr['number']} open)")

    print("== bridge sync ==")
    for line in results or ["nothing to sync"]:
        print(" -", line)
    return 0


def main() -> int:
    token = os.environ.get("BRIDGE_TOKEN", "")
    if not token:
        print("BRIDGE_TOKEN missing — fail-closed (no work done)", file=sys.stderr)
        return 2
    mode = sys.argv[1] if len(sys.argv) > 1 else "both"
    if mode not in ("intake", "sync", "both"):
        print(f"unknown mode: {mode}", file=sys.stderr)
        return 2
    try:
        rc = 0
        if mode in ("intake", "both"):
            rc = cmd_intake(token)
        if rc == 0 and mode in ("sync", "both"):
            rc = cmd_sync(token)
        return rc
    except BridgeError as exc:
        print(f"BRIDGE FAIL-HONEST: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
