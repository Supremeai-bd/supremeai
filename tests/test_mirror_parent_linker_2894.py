"""#2894 চুক্তি-টেস্ট: mirror-claim issue → parent has-pr linking (duplicate-PR race prevention)।

ফরেনসিক প্রেক্ষাপট (issue #2894-এর নিজস্ব প্রমাণ-কেস):
- #2756 → title `fix(backend): root-cause #2718 — ... (#2718)`, body `Root-cause fix for #2718.`
- #2775 → title `fix(frontend): root-cause #2735 — ... (#2735)`, body `Root-cause fix for #2735.`
- ফলে mirror-marker = **`root-cause #N` / `root-cause fix for #N`** (title/body)।
  জেনেরিক `Refs/Fixes/Closes #N` নয় — সেগুলো dependency-ref (false-positive: #2925-এর
  `Refs #2919` হলো নির্ভরতা, mirror নয়); group-predecessor (`পূর্ববর্তী ইস্যু: #N`)-ও নয়।

নিয়ম (repo প্যাটার্ন, #2901 প্রেসিডেন্ট): core লজিক pure + runner-injectable —
I/O subprocess (`gh`) fake runner দিয়ে মক, তাই স্যান্ডবক্সে gh ছাড়াই চুক্তি চলে।
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

from mirror_parent_linker import (
    MIRROR_REF_RE,
    extract_parent_ref,
    find_open_mirror_issues,
    maybe_link_created_mirror,
)

# ── extract_parent_ref ────────────────────────────────────────────────────


def test_extract_from_title_root_cause_pattern():
    """প্রমাণ-কেস #2756: title-এ `root-cause #2718` → parent 2718।"""
    title = "fix(backend): root-cause #2718 — unbounded memory accumulator (3 sites) (#2718)"
    body = "## Task\n\nRoot-cause fix for #2718.\n"
    assert extract_parent_ref(title, body) == 2718


def test_extract_from_body_root_cause_fix_for():
    """প্রমাণ-কেস #2775: title ছাড়া body-তে `Root-cause fix for #2735` → 2735।"""
    assert extract_parent_ref("fix(frontend): useListResource race guard", "Root-cause fix for #2735.") == 2735


def test_extract_case_insensitive_and_punctuation():
    assert extract_parent_ref("", "root-cause fix for #42.") == 42
    assert extract_parent_ref("ROOT-CAUSE #7 fallback", "") == 7


def test_extract_negative_generic_refs_are_not_mirrors():
    """জেনেরিক ref (Refs/Fixes/Closes) + group-predecessor → None (false-positive ব্লক)।"""
    assert extract_parent_ref("feat: Smart Dispatcher", "Refs #2919 #2923") is None
    assert extract_parent_ref("fix(x): t", "Closes #123") is None
    assert extract_parent_ref("refactor: y", "Fixes #45") is None
    assert extract_parent_ref("refactor: [Step-silent.2] t", "পূর্ববর্তী ইস্যু: #2277") is None
    assert extract_parent_ref("", "") is None


def test_mirror_regex_is_conservative_single_compiled_pattern():
    """চুক্তি: একটিই compiled প্যাটার্ন — bash/CLI স্ক্যান ও python একই ব্যবহার করে।"""
    assert MIRROR_REF_RE.search("root-cause #12")
    assert MIRROR_REF_RE.search("root-cause fix for #12")
    assert not MIRROR_REF_RE.search("related to #12")


# ── find_open_mirror_issues ───────────────────────────────────────────────


class _FakeProc:
    def __init__(self, stdout: str):
        self.stdout = stdout
        self.returncode = 0


def test_find_open_mirrors_filters_loose_search_matches():
    """gh search আলগা হতে পারে — python-সাইড রি-ফিল্টার চুক্তি: শুধু সত্যিক mirror, self বাদ।"""
    issues = [
        {"number": 2756, "title": "fix: root-cause #2718 — x", "body": "Root-cause fix for #2718."},
        {"number": 2800, "title": "feat: unrelated", "body": "Refs #2718"},  # loose match — বাদ
        {"number": 2718, "title": "root-cause #2718 self", "body": ""},  # self — বাদ
        {"number": 2900, "title": "fix: root-cause #999 — other parent", "body": ""},  # ভিন্ন parent — বাদ
    ]
    seen_cmds = []

    def fake_runner(cmd, **kw):
        seen_cmds.append(cmd)
        return _FakeProc(json.dumps(issues))

    mirrors = find_open_mirror_issues(2718, runner=fake_runner, repo="o/r")
    assert mirrors == [2756]
    cmd = seen_cmds[0]
    assert cmd[0] == "gh" and "issue" in cmd and "list" in cmd
    assert any("root-cause #2718" in str(a) for a in cmd)
    assert "--state" in cmd and "open" in cmd


def test_find_open_mirrors_empty_and_garbage_tolerant():
    def empty_runner(cmd, **kw):
        return _FakeProc("[]")

    assert find_open_mirror_issues(5, runner=empty_runner, repo="o/r") == []

    def bad_runner(cmd, **kw):
        return _FakeProc("not-json")

    assert find_open_mirror_issues(5, runner=bad_runner, repo="o/r") == []


# ── link_mirror_to_parent (idempotent, injectable) ────────────────────────


def test_link_adds_has_pr_and_posts_bengali_notice():
    """parent-এ has-pr নেই + কোনো marker-কমেন্ট নেই → দুটোই করা হয় (spec acceptance ১+৩)।"""
    calls: list[tuple] = []

    def runner(cmd, **kw):
        calls.append(tuple(cmd))
        joined = " ".join(cmd)
        if "issues/2718/comments" in joined:
            return _FakeProc(json.dumps([]))
        if "issues/2718" in joined:
            return _FakeProc(json.dumps({"labels": [{"name": "P0-critical"}, {"name": "bug"}]}))
        return _FakeProc("{}")

    from mirror_parent_linker import link_mirror_to_parent

    report = link_mirror_to_parent(mirror_issue=2756, parent_issue=2718, agent_name="planner", runner=runner, repo="o/r")
    assert report["label_added"] is True
    assert report["comment_posted"] is True
    # label command shape
    label_cmds = [c for c in calls if "edit" in c and "has-pr" in c]
    assert any("2718" in c for c in label_cmds)
    # comment contains marker + mirror number + agent
    comment_cmds = [c for c in calls if "-f" in c or "-F" in c or "comment" in " ".join(c)]
    assert comment_cmds, "comment must be posted via gh"
    blob = json.dumps(comment_cmds, ensure_ascii=False)
    assert "2756" in blob and "planner" in blob


def test_link_is_idempotent_when_already_guarded():
    """has-pr আগেই আছে + marker-কমেন্ট আগেই আছে → দ্বিতীয়বার কিছুই না (idempotent)।"""
    calls: list[tuple] = []

    def runner(cmd, **kw):
        calls.append(tuple(cmd))
        joined = " ".join(cmd)
        if "issues/2718/comments" in joined:
            return _FakeProc(json.dumps([{"body": "🪪 Mirror claim issue #2756 created by planner — parent guarded."}]))
        if "issues/2718" in joined:
            return _FakeProc(json.dumps({"labels": [{"name": "has-pr"}]}))
        return _FakeProc("{}")

    from mirror_parent_linker import link_mirror_to_parent

    report = link_mirror_to_parent(mirror_issue=2756, parent_issue=2718, agent_name="planner", runner=runner, repo="o/r")
    assert report == {"label_added": False, "comment_posted": False}
    assert not any("edit" in c or "comment" in c for c in calls), "no mutation on idempotent re-run"


# ── create_group_issue.py wiring ──────────────────────────────────────────


def test_maybe_link_created_mirror_links_root_cause_body():
    """create_group_issue wiring: root-cause body হলে parent link হয়; সাধারণ group body হলে না।"""
    seen: list[tuple] = []

    def runner(cmd, **kw):
        seen.append(tuple(cmd))
        joined = " ".join(cmd)
        if "labels" in joined:
            return _FakeProc(json.dumps({"labels": []}))
        if "comments" in joined:
            return _FakeProc(json.dumps([]))
        return _FakeProc("{}")

    # mirror-স্টাইল body → link হবে
    n1 = maybe_link_created_mirror(
        url="https://github.com/o/r/issues/3001",
        title="fix(backend): root-cause #2718 — x",
        body="Root-cause fix for #2718.",
        agent_name="create_group_issue",
        runner=runner,
        repo="o/r",
    )
    assert n1 == 2718

    # সাধারণ group-issue body (predecessor সহ) → link হবে না
    seen.clear()
    n2 = maybe_link_created_mirror(
        url="https://github.com/o/r/issues/3002",
        title="refactor(core): [Step-silent.1] eliminate silent exception handlers",
        body="পূর্ববর্তী ইস্যু: #2277 · Refs #2277",
        agent_name="create_group_issue",
        runner=runner,
        repo="o/r",
    )
    assert n2 is None
    assert seen == [], "no gh calls for non-mirror issues"
