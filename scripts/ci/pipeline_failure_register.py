#!/usr/bin/env python3
"""Pipeline Failure Register (#2928) — সব pipeline-ব্যর্থতা এক গ্রুপে + স্মার্ট রাউটিং।

# বাংলা মন্তব্য: লাইভ ঘটনা — PR #2926-এর দুটি pipeline ব্যর্থ হয়েও কোনো issue
# জন্মায়নি, কারণ ৩টি পথই ভাঙা ছিল:
#   ১) ci-failure-handler: workflow_run-এ main checkout → ভুল issue-linkage +
#      `grep -c || echo 0` দ্বৈত-আউটপুট → নীরব মৃত্যু;
#   ২) check_ci_failures.py: GITHUB_TOKEN পড়ে কিন্তু workflow GH_TOKEN দেয় → 401;
#   ৩) smart-fallback: চির-open লেজার-ইস্যুর কারণে মৃত-কোড।
#
# এই স্ক্রিপ্ট = single funnel (একক পথ): যেকোনো pipeline-ব্যর্থতা
# (main + PR-branch + Branch Guard) → একটিই canonical register-issue।
#
# Poka-yoke নকশা-নীতি:
#   - প্রতি-ব্যর্থতায় ছড়ানো blocker-issue নয় — fingerprint-dedup (workflow @ branch)
#   - main-red হলে অন্ধভাবে "main আগে ঠিক করো" নয় — আগে খোলা PR-ক্যান্ডিডেট
#     খোঁজা (diff-overlap + গেট-সবুজ) → PR-ই main ঠিক করলে merge-first,
#     ডুপ্লিকেট fix-issue জন্মানো হয় না
#   - ব্যর্থতা সেরে গেলে সারি auto-resolve (হীল) — register-body-ই state
#
# Smart routing ladder (সস্তার-প্রথম):
#   merge-first > new-fix > pr-rebuild > enforced > watching
#
# Usage:
#   python scripts/ci/pipeline_failure_register.py --scan           # পূর্ণ রি-স্ক্যান
#   python scripts/ci/pipeline_failure_register.py --event          # workflow_run-handler পথ
#   python scripts/ci/pipeline_failure_register.py --dry-run        # নেটওয়ার্ক-লেখা শূন্য
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

REPO = os.environ.get("GH_REPO", "SaifulHaqueNiloy/supremeai")
RULES_PATH = Path(__file__).resolve().parents[2] / ".github" / "constitution" / "rules.yml"

# ── Policy SSOT (rules.yml pipeline_failure_policy) + DEFAULT fallback ───────
# বাংলা মন্তব্য: gates.py-প্যাটার্ন — rules.yml প্রথম, ফাইল/কী না থাকলে DEFAULT।
DEFAULT_POLICY: dict[str, Any] = {
    "enabled": True,
    "register_title_prefix": "🚨 [PIPELINE-FAILURE-REGISTER]",
    "register_labels": ["pipeline-failure", "type:ledger", "area:ci"],
    "fix_labels": ["P1-high", "area:ci", "type:bug", "ci-failure"],
    "comment_marker_prefix": "<!-- pfr:fp:",
    "merge_first_marker_prefix": "<!-- pfr-merge-first:",
    "fix_marker_prefix": "<!-- pfr-fix:",
    "state_marker": "<!-- pfr-state",
    "scan_window_runs": 15,
    "max_log_bytes": 60000,
    "max_pr_files": 120,
    "merge_first": True,
    # বাংলা মন্তব্য: কোন workflow-গুলো register-এর নজরদারিতে — Branch Guard-সহ
    # (আগে guard-violation চিরকাল অদৃশ্য থাকত)।
    "workflows_watched": [
        "PR Gate (Unified Pipeline)",
        "Main CI/CD",
        "🌿 Branch Creation Guard",
    ],
}

GUARD_WORKFLOW = "🌿 Branch Creation Guard"

# ফাইল-পাথ নিষ্কাশন: repo-relative পথ দেখতে হবে (runner-পথ নয়)।
FILE_PATH_RE = re.compile(r"(?<![\w/.-])((?:[\w.-]+/){1,6}[\w.-]+\.(?:py|ts|tsx|js|mjs|yml|yaml|json|toml|sql|sh|cfg|ini))\b")
RUNNER_NOISE_RE = re.compile(r"/home/runner|/usr/lib|/opt/hostedtoolcache|site-packages|_temp/")

HEADING = "# 🚨 Pipeline Failure Register — সব pipeline-ব্যর্থতা এক গ্রুপে (auto-maintained)"

ROUTE_LABELS = {
    "merge-first": "🎯 merge-first",
    "new-fix": "🆕 new-fix",
    "already-tracked": "♻️ tracked",
    "pr-rebuild": "🔧 pr-rebuild",
    "enforced": "🛡️ enforced",
    "watching": "👀 watching",
}

ROUTE_ACTIONS = {
    "merge-first": "এই PR-টি merge করলেই main সবুজ হবে — ডুপ্লিকেট fix-issue নয়",
    "new-fix": "নতুন fix-issue তৈরি হয়েছে — ফ্লিট এটি তুলবে",
    "already-tracked": "আগের fix-issue-ই চলছে — নতুন জন্মানো হয়নি",
    "pr-rebuild": "gate-কমেন্টই পথ দেখাচ্ছে — PR-এর author claim+template ঠিক করবে",
    "enforced": "guard-ই ব্যবস্থা নিয়েছে (comment/delete) — দৃশ্যমানতা-সারি",
    "watching": "branch-এ open PR নেই — নজরে রাখা হচ্ছে",
}


def load_policy(rules_path: Path = RULES_PATH) -> dict[str, Any]:
    """rules.yml → pipeline_failure_policy (DEFAULT-merge)। ফাইল না থাকলে DEFAULT।"""
    pol = dict(DEFAULT_POLICY)
    try:
        import yaml  # noqa: PLC0415 — lazy: CI-রানারে সবসময় থাকে, লোকালে ছাড় না

        data = yaml.safe_load(Path(rules_path).read_text(encoding="utf-8")) or {}
        override = data.get("pipeline_failure_policy") or {}
        for key, val in override.items():
            if key in pol:
                pol[key] = val
    except Exception:  # noqa: BLE001 — policy-লোড ব্যর্থতা স্ক্যান থামাবে না
        pass
    return pol


def fingerprint(name: str, branch: str) -> str:
    """workflow @ branch → স্থিতিশীল hash (নতুন push-এও একই ব্যর্থতা-ইনস্ট্যান্স)।"""
    return hashlib.md5(f"{name} @ {branch}".encode()).hexdigest()[:12]  # noqa: S324 — dedup-key, নিরাপত্তা নয়


def now_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# ── ইনজেক্টেবল GitHub-স্তর (tests: FakeApi/FakeGh) ────────────────────────────

def real_api(endpoint: str, method: str = "GET", payload: dict | None = None) -> Any:
    """REST কল — token সর্বদা GH_TOKEN প্রথম (workflow-চুক্তি), GITHUB_TOKEN fallback।

    # বাংলা মন্তব্য: #2928-এর মূল bug-গুলোর একটি ছিল check_ci_failures শুধু
    # GITHUB_TOKEN পড়ত — workflow কিন্তু GH_TOKEN দেয় → খালি token → 401।
    """
    token = (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
    req = urllib.request.Request(  # noqa: S310 — github.com API-ই কল-হয়
        f"https://api.github.com/{endpoint.lstrip('/')}",
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        raw = resp.read().decode()
    return json.loads(raw) if raw.strip() else None


def real_gh(*args: str) -> str:
    """gh CLI র‍্যাপার — stdout স্ট্রিং ফেরত (run-list/pr-view/log-failed)।"""
    res = subprocess.run(
        ["gh", *args], capture_output=True, text=True, timeout=60, check=False
    )
    if res.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:3])}… failed: {res.stderr[:200]}")
    return res.stdout


Api = Callable[..., Any]
Gh = Callable[..., str]


# ── রান-স্ক্যান ──────────────────────────────────────────────────────────────

def list_failed_runs(gh: Gh, pol: dict, limit: int | None = None) -> list[dict]:
    """সাম্প্রতিক ব্যর্থ রান (সব branch — main-only স্কোপ bug-এর প্রতিকার)।"""
    out = gh(
        "run", "list", "--repo", REPO, "--status", "failure",
        "--limit", str(limit or pol["scan_window_runs"]), "--json",
        "databaseId,name,headBranch,headSha,event,createdAt,url,conclusion",
    )
    runs = json.loads(out or "[]")
    return [r for r in runs if r.get("name") in pol["workflows_watched"]]


def latest_conclusion(gh: Gh, workflow: str, branch: str) -> str | None:
    """ওই workflow+branch-এর সর্বশেষ রানের ফলাফল (হীলিং-সনাক্তকরণ)।"""
    try:
        out = gh(
            "run", "list", "--repo", REPO, "--workflow", workflow,
            "--branch", branch, "--limit", "1", "--json", "conclusion",
        )
        rows = json.loads(out or "[]")
        return rows[0].get("conclusion") if rows else None
    except Exception:  # noqa: BLE001 — API-down হলে হীল দাবি করা অন্যায়
        return None


# ── PR-স্তর ──────────────────────────────────────────────────────────────────

def list_open_prs(api: Api) -> list[dict]:
    return api(f"repos/{REPO}/pulls?state=open&per_page=50") or []


def find_open_pr(api: Api, branch: str) -> dict | None:
    owner = REPO.split("/")[0]
    prs = api(f"repos/{REPO}/pulls?head={owner}:{branch}&state=open") or []
    return prs[0] if prs else None


def pr_files(api: Api, pr_number: int, pol: dict) -> set[str]:
    try:
        files = api(f"repos/{REPO}/pulls/{pr_number}/files?per_page={pol['max_pr_files']}") or []
        return {f.get("filename", "") for f in files if f.get("filename")}
    except Exception:  # noqa: BLE001
        return set()


def pr_checks_green(gh: Gh, pr_number: int) -> bool:
    """PR-এর সর্বশেষ চেক-রোলআপ: সবুজ ও সম্পূর্ণ (in-progress → ক্যান্ডিডেট নয়)।"""
    try:
        out = gh("pr", "view", str(pr_number), "--repo", REPO, "--json", "statusCheckRollup")
        checks = (json.loads(out or "{}")).get("statusCheckRollup") or []
        if not checks:
            return False
        # বাংলা মন্তব্য: চলমান (conclusion খালি) চেক থাকলে রায় স্থগিত — ক্যান্ডিডেট নয়।
        if any(not c.get("conclusion") for c in checks):
            return False
        ok = {"SUCCESS", "SKIPPED", "NEUTRAL"}
        has_success = any(c.get("conclusion") == "SUCCESS" for c in checks)
        return has_success and all(c.get("conclusion") in ok for c in checks)
    except Exception:  # noqa: BLE001
        return False


def extract_failed_files(gh: Gh, run_id: int, pol: dict) -> set[str]:
    """ব্যর্থ-লগ থেকে repo-relative ফাইল-সংকেত (ক্যাপড — লগ বিশাল হতে পারে)।"""
    try:
        raw = gh("run", "view", str(run_id), "--repo", REPO, "--log-failed")
    except Exception:  # noqa: BLE001 — লগ মুছে গেলে/বিশাল হলে সৎ-খালি
        return set()
    raw = raw[: pol["max_log_bytes"]]
    files: set[str] = set()
    for line in raw.splitlines():
        if RUNNER_NOISE_RE.search(line):
            continue
        files.update(FILE_PATH_RE.findall(line))
    return files


# ── স্মার্ট রাউটিং (blind main-first নয়) ─────────────────────────────────────

def merge_first_candidates(
    api: Api, gh: Gh, run: dict, pol: dict, dry_run: bool = False
) -> list[int]:
    """main-red-এর সস্তা সমাধান: diff ব্যর্থ-ফাইল ছুঁয়েছে + প্রার্থীর গেট সবুজ।

    # বাংলা মন্তব্য: অ্যাডমিন-নীতি — "always fixing main first" বুদ্ধিমান নয়;
    # নতুন PR-ই main ঠিক করতে পারে — তখন merge-first-ই উত্তর।
    """
    if not pol.get("merge_first"):
        return []
    fail_files = extract_failed_files(gh, int(run["databaseId"]), pol)
    if not fail_files:
        return []
    cands: list[int] = []
    for pr in list_open_prs(api):
        num = int(pr["number"])
        if pr_files(api, num, pol) & fail_files and pr_checks_green(gh, num):
            cands.append(num)
    return sorted(cands)


def find_existing_fix_issue(api: Api, fp: str, pol: dict) -> int | None:
    """একই ব্যর্থতার fix-issue আগে থেকেই খোলা? (duplicate-জন্ম রোধ)"""
    issues = api(f"repos/{REPO}/issues?state=open&labels=ci-failure&per_page=50") or []
    marker = f"{pol['fix_marker_prefix']}{fp}-->"
    for issue in issues:
        if marker in (issue.get("body") or ""):
            return int(issue["number"])
    return None


def create_fix_issue(api: Api, run: dict, fp: str, pol: dict, suspects: set[str]) -> int:
    """টেমপ্লেট-সম্মত fix-issue (Mission/Touching Files/Verification + P1 টোকেন)।"""
    name = run.get("name", "unknown")
    branch = run.get("headBranch", "?")
    sha = (run.get("headSha") or "")[:12]
    run_id = run.get("databaseId", "?")
    url = run.get("url", "")
    # বাংলা মন্তব্য: সন্দেহভাজন ফাইল = ব্যর্থ-লগের সংকেত — claimer-এর শুরু-বিন্দু।
    suspects_line = ", ".join(sorted(suspects)[:5]) if suspects else "TBD (root-cause করে claimer ঘোষণা করবে)"
    title = f"fix(ci): [ci-fail:{fp}] {name} RED on {branch} ({sha}) — auto-filed"
    body = (
        f"{pol['fix_marker_prefix']}{fp}-->\n"
        f"## Mission\n\n"
        f"**{name}** workflow লাল — branch `{branch}` (commit `{sha}`)।\n\n"
        f"| Field | Value |\n|---|---|\n| Workflow | `{name}` |\n| Branch | `{branch}` |\n"
        f"| Run | [{run_id}]({url}) |\n\n"
        f"### Reproduction\n```bash\ngh run view {run_id} --repo {REPO} --log-failed\n```\n\n"
        f"## Touching Files\n\n"
        f"```text\nTouching files: {suspects_line}\n```\n"
        f"(ব্যর্থ-লগের সন্দেহভাজন ফাইল — চূড়ান্ত ঘোষণা claim-কমেন্টে করতে হবে)\n\n"
        f"## Verification\n\n"
        f"1. `gh run view {run_id} --log-failed` → root-cause\n"
        f"2. লোকাল রিপ্রো + ফিক্স\n"
        f"3. PR-এ গেট-সবুজ প্রমাণ (Test Evidence)\n\n"
        f"**Priority:** P1-high\n"
    )
    issue = api(
        f"repos/{REPO}/issues", method="POST",
        payload={"title": title, "body": body, "labels": pol["fix_labels"]},
    )
    return int(issue["number"])


def route_failure(api: Api, gh: Gh, run: dict, pol: dict, dry_run: bool = False) -> dict:
    """একটি ব্যর্থ রানের সস্তা-সমাধান-পথ নির্ণয়।"""
    name = run.get("name", "unknown")
    branch = run.get("headBranch", "?")
    fp = fingerprint(name, branch)
    row: dict[str, Any] = {
        "fp": fp, "workflow": name, "branch": branch,
        "run_id": run.get("databaseId"), "url": run.get("url", ""),
        "pr": None, "fix": None, "route": "watching", "detail": "",
    }

    pr = find_open_pr(api, branch)
    if pr:
        row["pr"] = int(pr["number"])

    if branch in ("main", "master"):
        # ── main-red: প্রথমে merge-first সন্ধান — নতুন PR-ই main ঠিক করতে পারে
        cands = merge_first_candidates(api, gh, run, pol, dry_run=dry_run)
        if cands:
            row["route"] = "merge-first"
            row["detail"] = f"PR #{cands[0]}" + (f" (+{len(cands)-1}টি)" if len(cands) > 1 else "")
            return row
        suspects = extract_failed_files(gh, int(run.get("databaseId", 0)), pol)
        existing = find_existing_fix_issue(api, fp, pol)
        if existing:
            row["route"] = "already-tracked"
            row["fix"] = existing
            return row
        if dry_run:
            row["route"] = "new-fix"
            row["detail"] = "dry-run: issue তৈরি হতো"
            return row
        num = create_fix_issue(api, run, fp, pol, suspects)
        row["route"] = "new-fix"
        row["fix"] = num
        return row

    if name == GUARD_WORKFLOW:
        # ── guard-violation: guard-ই ব্যবস্থা নিয়েছে — দৃশ্যমানতা-সারি
        row["route"] = "enforced"
        row["detail"] = f"open PR #{row['pr']}" if row["pr"] else "branch handled by guard"
        return row

    if row["pr"]:
        # ── PR-branch ব্যর্থতা: gate-কমেন্টই শেখায় — নতুন issue নয়
        row["route"] = "pr-rebuild"
        return row

    # ── PR নেই এমন branch-এর ব্যর্থতা — নজরে রাখো
    row["route"] = "watching"
    return row


# ── Register-issue (একটিই গ্রুপ) ────────────────────────────────────────────

def find_register(api: Api, pol: dict) -> dict | None:
    issues = api(f"repos/{REPO}/issues?state=open&labels={pol['register_labels'][0]}&per_page=20") or []
    for issue in issues:
        if str(issue.get("title", "")).startswith(pol["register_title_prefix"]):
            return issue
    return None


def create_register(api: Api, pol: dict) -> dict:
    body = render_body([], [], pol)
    return api(
        f"repos/{REPO}/issues", method="POST",
        payload={
            "title": f"{pol['register_title_prefix']} লাইভ pipeline-ব্যর্থতা বোর্ড — auto-maintained",
            "body": body,
            "labels": pol["register_labels"],
        },
    )


def parse_state(body: str, pol: dict) -> dict[str, dict]:
    """register-body-র machine-ব্লক (<!-- pfr-state … -->) → আগের সারি-স্টেট।"""
    state: dict[str, dict] = {}
    if pol["state_marker"] not in body:
        return state
    block = body.split(pol["state_marker"], 1)[1]
    block = block.split("-->", 1)[0]
    for line in block.strip().splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        fp, _, rest = line.partition(":")
        # বাংলা মন্তব্য: প্রতিটি অংশ strip — নইলে " Main CI/CD"-এর মতো
        # স্পেস-সহ মান healing-সনাক্তকরণে workflow-ম্যাচ ভেঙে দেয়।
        parts = [p.strip() for p in rest.split("|")]
        if len(parts) < 6 or not parts[0]:
            continue
        state[fp.strip()] = {
            "workflow": parts[0], "branch": parts[1], "route": parts[2],
            "count": int(parts[3]) if parts[3].isdigit() else 1,
            "first": parts[4], "last": parts[5],
            "pr": int(parts[6]) if len(parts) > 6 and parts[6].isdigit() else None,
            "fix": int(parts[7]) if len(parts) > 7 and parts[7].isdigit() else None,
        }
    return state


def render_state(active: list[dict]) -> str:
    lines = ["<!-- pfr-state"]
    for r in active:
        lines.append(
            f"{r['fp']}: {r['workflow']}|{r['branch']}|{r['route']}|{r.get('count', 1)}|"
            f"{r.get('first', '')}|{r.get('last', '')}|{r.get('pr') or ''}|{r.get('fix') or ''}"
        )
    lines.append("-->")
    return "\n".join(lines)


def render_body(active: list[dict], healed: list[dict], pol: dict) -> str:
    """register-body — machine-state ব্লক + মানব-পাঠযোগ্য টেবিল।"""
    parts = [HEADING, ""]
    parts.append(
        "> **একটি গ্রুপে সব pipeline-ব্যর্থতা** (fingerprint-dedup, auto-heal)। "
        "মেশিন-মেইনটেইনড — হাতে সম্পাদনা নিষিদ্ধ (`pipeline_failure_register.py`)।\n"
    )
    parts.append(f"সর্বশেষ হালনাগাদ: **{now_utc()}**\n")
    if active:
        parts.append("## 🔴 Active — smart-routed\n")
        parts.append("| Route | Workflow | Branch | PR | Fix issue | Count | Last seen | পরবর্তী পদক্ষেপ |")
        parts.append("|---|---|---|---|---|---|---|---|")
        for r in active:
            label = ROUTE_LABELS.get(r["route"], r["route"])
            pr_cell = f"[#{r['pr']}](https://github.com/{REPO}/pull/{r['pr']})" if r.get("pr") else "—"
            fix_cell = f"#{r['fix']}" if r.get("fix") else "—"
            action = ROUTE_ACTIONS.get(r["route"], "")
            if r["route"] == "merge-first" and r.get("detail"):
                action = f"merge {r['detail']} — main-ও সবুজ হবে"
            parts.append(
                f"| {label} | `{r['workflow']}` | `{r['branch']}` | {pr_cell} | {fix_cell} | "
                f"{r.get('count', 1)} | {r.get('last', '')} | {action} |"
            )
        parts.append("")
    else:
        parts.append("## ✅ সব pipeline সবুজ — কোনো সক্রিয় ব্যর্থতা নেই\n")
    if healed:
        parts.append("## ✅ Recently healed\n")
        parts.append("| Workflow | Branch | Healed |")
        parts.append("|---|---|---|")
        for r in healed[-8:]:
            parts.append(f"| `{r['workflow']}` | `{r['branch']}` | {r.get('healed_at', '')} |")
        parts.append("")
    parts.append(
        "---\n"
        "**স্মার্ট রাউটিং-নীতি (blind main-first নয়):**\n"
        "1. 🎯 **merge-first** — main-red হলে আগে খোলা PR-ক্যান্ডিডেট (diff-overlap + গেট-সবুজ) খোঁজা হয়; PR-ই main ঠিক করে — ডুপ্লিকেট fix-issue জন্মায় না\n"
        "2. 🆕 **new-fix** — ক্যান্ডিডেট শূন্য হলেই কেবল একটি fix-issue\n"
        "3. 🔧 **pr-rebuild** — PR-branch ব্যর্থতা: gate-কমেন্টই পথ দেখায়\n"
        "4. 🛡️ **enforced** — Branch Guard ইতোমধ্যে ব্যবস্থা নিয়েছে\n"
        "5. 👀 **watching** — open PR-হীন branch-ব্যর্থতা নজরে\n"
        "\n_একক-ফানেল #2928: `pipeline_failure_register.py` (workflow_run-handler + ৩০-মিনিট লুপ-চেক উভয় পথ এখানেই মেশে)_"
    )
    return "\n".join(parts) + "\n" + render_state(active)


def already_commented(api: Api, register_number: int, fp: str, pol: dict) -> bool:
    marker = f"{pol['comment_marker_prefix']}{fp}-->"
    comments = api(f"repos/{REPO}/issues/{register_number}/comments?per_page=100") or []
    return any(marker in (c.get("body") or "") for c in comments)


def comment_failure(api: Api, register_number: int, row: dict, pol: dict) -> None:
    """নতুন fingerprint-এ একবারই কমেন্ট (dedup-marker) — প্রতি-স্ক্যান স্প্যাম নয়।"""
    label = ROUTE_LABELS.get(row["route"], row["route"])
    links = []
    if row.get("run_id"):
        links.append(f"[run {row['run_id']}]({row['url']})")
    if row.get("pr"):
        links.append(f"PR #{row['pr']}")
    if row.get("fix"):
        links.append(f"fix #{row['fix']}")
    body = (
        f"{pol['comment_marker_prefix']}{row['fp']}-->\n"
        f"## {label} — `{row['workflow']}` লাল @ `{row['branch']}`\n\n"
        f"{' · '.join(links)}\n\n"
        f"**পরবর্তী পদক্ষেপ:** {ROUTE_ACTIONS.get(row['route'], '')}\n"
        + (f"**ক্যান্ডিডেট:** {row['detail']}\n" if row.get("detail") else "")
        + "\n_স্মার্ট-রাউটিং #2928 — বিস্তারিত টেবিল উপরে_"
    )
    api(f"repos/{REPO}/issues/{register_number}/comments", method="POST", payload={"body": body})


def comment_merge_first(api: Api, pr_number: int, row: dict, pol: dict) -> None:
    """ক্যান্ডিডেট PR-তে একবারই নির্দেশনা — merge-first পথ।"""
    marker = f"{pol['merge_first_marker_prefix']}{row['fp']}-->"
    try:
        comments = api(f"repos/{REPO}/issues/{pr_number}/comments?per_page=100") or []
        if any(marker in (c.get("body") or "") for c in comments):
            return
    except Exception:  # noqa: BLE001 — dedup-চেক ব্যর্থ হলে কমেন্ট এড়িয়ে যাও (স্প্যাম-নিরাপদ)
        return
    body = (
        f"{marker}\n"
        f"## 🎯 merge-first নির্দেশনা (#2928)\n\n"
        f"এই PR-এর diff main-এর বর্তমান লাল `{row['workflow']}`-এর ব্যর্থ-ফাইলগুলো ছুঁয়েছে এবং গেট সবুজ — "
        f"**এই PR মার্জ করলেই main সম্ভবত সবুজ হবে।** নতুন ডুপ্লিকেট fix-issue জন্মানো হয়নি।\n\n"
        f"রেজিস্টার-সারি: `{row['branch']}` · [run {row['run_id']}]({row['url']})\n"
    )
    api(f"repos/{REPO}/issues/{pr_number}/comments", method="POST", payload={"body": body})


# ── মূল স্ক্যান ──────────────────────────────────────────────────────────────

def scan(
    api: Api = real_api,
    gh: Gh = real_gh,
    pol: dict | None = None,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    """পূর্ণ রি-স্ক্যান → register হালনাগাদ। রিটার্ন: summary (active/healed/created)।"""
    pol = pol or load_policy()
    if not pol.get("enabled", True):
        return {"skipped": "policy disabled"}

    failed = list_failed_runs(gh, pol, limit)
    by_fp: dict[str, list[dict]] = {}
    for run in failed:
        by_fp.setdefault(fingerprint(run.get("name", "?"), run.get("headBranch", "?")), []).append(run)

    # register খোঁজো/জন্ম দাও (একটিই গ্রুপ)
    register = find_register(api, pol)
    register_created = False
    if register is None:
        if dry_run:
            register = {"number": -1, "body": ""}
        else:
            register = create_register(api, pol)
            register_created = True

    prev = parse_state(register.get("body") or "", pol)

    active: list[dict] = []
    healed: list[dict] = []
    created_fixes: list[int] = []
    for fp, runs in by_fp.items():
        newest = max(runs, key=lambda r: r.get("createdAt", ""))
        row = route_failure(api, gh, newest, pol, dry_run=dry_run)
        old = prev.get(fp) or {}
        # বাংলা মন্তব্য: কাউন্ট বাড়ে নতুন run-id-এ (প্রতি-স্ক্যান ফোলাবে না)।
        same_run = str(old.get("last_run_id")) == str(newest.get("databaseId"))
        row["count"] = (old.get("count", 0) if same_run else old.get("count", 0) + 1) or 1
        row["first"] = old.get("first") or newest.get("createdAt", "")[:16]
        row["last"] = newest.get("createdAt", "")[:16]
        row["last_run_id"] = newest.get("databaseId")
        active.append(row)
        if row["route"] == "new-fix" and row.get("fix"):
            created_fixes.append(row["fix"])

    # হীলিং: আগে ট্র্যাক করা, এখন উইন্ডো-বাইরে — সর্বশেষ রান সবুজ হলে resolved
    active_fps = {r["fp"] for r in active}
    for fp, old in prev.items():
        if fp in active_fps:
            continue
        verdict = latest_conclusion(gh, old.get("workflow", ""), old.get("branch", ""))
        if verdict == "success":
            healed.append({**old, "fp": fp, "healed_at": now_utc()})
        elif verdict == "failure":
            # উইন্ডো-বাইরে কিন্তু এখনো লাল — সক্রিয় সারিই থাকবে
            active.append({**old, "fp": fp, "count": old.get("count", 1), "last": old.get("last", "")})

    order = {"merge-first": 0, "new-fix": 1, "already-tracked": 2, "pr-rebuild": 3, "enforced": 4, "watching": 5}
    active.sort(key=lambda r: order.get(r["route"], 9))

    if not dry_run:
        body = render_body(active, healed, pol)
        api(f"repos/{REPO}/issues/{register['number']}", method="PATCH", payload={"body": body})
        for row in active:
            if not already_commented(api, int(register["number"]), row["fp"], pol):
                comment_failure(api, int(register["number"]), row, pol)
            if row["route"] == "merge-first" and row.get("pr"):
                comment_merge_first(api, int(row["pr"]), row, pol)

    return {
        "register": register.get("number"),
        "register_created": register_created,
        "active": len(active),
        "healed": len(healed),
        "created_fixes": created_fixes,
        "routes": {r["fp"]: r["route"] for r in active},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline Failure Register (#2928)")
    parser.add_argument("--scan", action="store_true", help="পূর্ণ রি-স্ক্যান (default)")
    parser.add_argument(
        "--event", action="store_true",
        help="workflow_run-handler পথ — প্রেক্ষাপট-env (FAILED_*) লগ-এ ব্যবহৃত, পথ একটিই",
    )
    parser.add_argument("--dry-run", action="store_true", help="নেটওয়ার্ক-লেখা শূন্য")
    parser.add_argument("--limit", type=int, default=None, help="স্ক্যান-উইন্ডো override")
    args = parser.parse_args()

    if args.event:
        print(
            f"📋 Registering pipeline failure: "
            f"{os.environ.get('FAILED_WORKFLOW', '?')} @ "
            f"{os.environ.get('FAILED_BRANCH', '?')} "
            f"(run {os.environ.get('FAILED_RUN_ID', '?')})"
        )
    summary = scan(dry_run=args.dry_run, limit=args.limit)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    # বাংলা মন্তব্য: বুককিপিং-সফলতা = exit 0 — ব্যর্থতা রেজিস্টার-হওয়াই এই জব-এর কাজ।
    return 0


if __name__ == "__main__":
    sys.exit(main())
