"""Tests for scripts/ci/pipeline_failure_register.py (#2928).

# বাংলা মন্তব্য: FakeApi/FakeGh ইনজেকশন — কোনো নেটওয়ার্ক কল নেই।
# চুক্তি-কভারেজ: এক-গ্রুপ register, fingerprint-dedup, স্মার্ট রাউটিং
# (merge-first > new-fix > pr-rebuild > enforced > watching), হীলিং,
# কমেন্ট-dedup, টেমপ্লেট-সম্মত fix-issue।
"""

from __future__ import annotations

import json

import scripts.ci.pipeline_failure_register as pfr
from scripts.ci.pipeline_failure_register import (
    DEFAULT_POLICY,
    extract_failed_files,
    fingerprint,
    load_policy,
    merge_first_candidates,
    parse_state,
    pr_checks_green,
    render_body,
    render_state,
    route_failure,
    scan,
)

REPO = pfr.REPO


# ── Fakes ────────────────────────────────────────────────────────────────────

class FakeApi:
    """in-memory GitHub REST — issues/comments/pulls এন্ডপয়েন্ট।"""

    def __init__(self, *, open_prs=None, pr_files_map=None, register_body="",
                 existing_fix_issues=None, checks_map=None):
        self.issues: list[dict] = []          # created via POST
        self.register_body = register_body
        self.register_number: int | None = None   # POST-এ জন্ম নিলে সেট
        self.existing_fix_issues = existing_fix_issues or []
        self.comments: dict[int, list[dict]] = {}
        self.open_prs = open_prs or []
        self.pr_files_map = pr_files_map or {}
        self.checks_map = checks_map or {}
        self.patched: list[dict] = []
        self.calls: list = []

    def __call__(self, endpoint, method="GET", payload=None):
        self.calls.append((method, endpoint, payload))
        if method == "GET":
            if "pulls?state=open" in endpoint:
                return self.open_prs
            if "pulls?head=" in endpoint:
                # repos/X/pulls?head=owner:branch&state=open → branch-অংশ
                branch = endpoint.split(":", 1)[1].split("&")[0]
                for pr in self.open_prs:
                    if pr.get("head", {}).get("ref") == branch:
                        return [pr]
                return []
            if "/files" in endpoint:
                num = int(endpoint.split("/pulls/")[1].split("/files")[0])
                return [{"filename": f} for f in self.pr_files_map.get(num, [])]
            if "comments" in endpoint:
                num = int(endpoint.split("/issues/")[1].split("/comments")[0])
                return self.comments.get(num, [])
            if "issues?state=open&labels=ci-failure" in endpoint:
                return self.existing_fix_issues
            if "issues?state=open&labels=pipeline-failure" in endpoint:
                if self.register_body:
                    return [{"number": self.register_number or 900, "title": f"{DEFAULT_POLICY['register_title_prefix']} x", "body": self.register_body}]
                return []
            raise AssertionError(f"unexpected GET {endpoint}")
        if method == "POST":
            if endpoint.endswith("/comments"):
                num = int(endpoint.split("/issues/")[1].split("/comments")[0])
                self.comments.setdefault(num, []).append({"body": payload["body"]})
                return {}
            if endpoint.endswith("/issues"):
                self.issues.append(payload)
                num = 950 + len(self.issues)
                # রেজিস্টার-পেলোড চিনে নিই (labels-এ pipeline-failure)
                labels = payload.get("labels") or []
                if "pipeline-failure" in labels:
                    self.register_number = num
                    self.register_body = payload.get("body", self.register_body)
                return {"number": num, **payload}
        if method == "PATCH":
            self.patched.append(payload)
            self.register_body = payload["body"]
            return {}
        raise AssertionError(f"unexpected {method} {endpoint}")


class FakeGh:
    """gh CLI ফেক — run-list / pr-view / run-view-log-failed।"""

    def __init__(self, *, failed_runs=None, latest=None, log_text="", green_prs=None):
        self.failed_runs = failed_runs or []
        self.latest = latest or {}       # (workflow, branch) → conclusion
        self.log_text = log_text
        self.green_prs = green_prs or set()

    def __call__(self, *args):
        if args[0] == "run" and "list" in args:
            if "--workflow" in args:
                wf = args[args.index("--workflow") + 1]
                br = args[args.index("--branch") + 1]
                return json.dumps([{"conclusion": self.latest.get((wf, br))}])
            return json.dumps(self.failed_runs)
        if args[0] == "pr" and "view" in args:
            num = int(args[args.index("view") + 1])
            if num in self.green_prs:
                rollup = [
                    {"name": "Gate A", "conclusion": "SUCCESS"},
                    {"name": "Gate B", "conclusion": "SKIPPED"},
                ]
            else:
                rollup = [
                    {"name": "Gate A", "conclusion": "SUCCESS"},
                    {"name": "Gate B", "conclusion": "FAILURE"},
                ]
            return json.dumps({"statusCheckRollup": rollup})
        if args[0] == "run" and "view" in args:
            return self.log_text
        raise AssertionError(f"unexpected gh {args}")


def _run(name, branch, run_id=111, created="2026-10-01T21:00:00Z"):
    return {
        "databaseId": run_id, "name": name, "headBranch": branch,
        "headSha": "abcd1234", "event": "push", "createdAt": created,
        "url": f"https://github.com/{REPO}/actions/runs/{run_id}",
        "conclusion": "failure",
    }


def _pr(num, branch, files):
    return {
        "number": num, "title": f"PR #{num}",
        "head": {"ref": branch}, "base": {"ref": "main"},
        "_files": files,
    }


# ── Policy + fingerprint ─────────────────────────────────────────────────────

class TestPolicy:
    def test_load_policy_merges_rules_yml(self):
        pol = load_policy()
        # rules.yml-এ pipeline_failure_policy আছে — SSOT থেকেই আসছে
        assert pol["register_title_prefix"].startswith("🚨 [PIPELINE")
        assert "🌿 Branch Creation Guard" in pol["workflows_watched"]
        assert pol["merge_first"] is True

    def test_fingerprint_stable(self):
        assert fingerprint("A", "b") == fingerprint("A", "b")
        assert fingerprint("A", "b") != fingerprint("A", "c")


# ── স্মার্ট রাউটিং ────────────────────────────────────────────────────────────

class TestRouteFailure:
    def test_main_red_with_green_pr_candidate_is_merge_first(self):
        api = FakeApi(
            open_prs=[_pr(55, "fix/77-x", ["backend/core/engine.py"])],
            pr_files_map={55: ["backend/core/engine.py"]},
        )
        gh = FakeGh(
            log_text="FAILED backend/core/engine.py::test_x",
            green_prs={55},
        )
        row = route_failure(api, gh, _run("Main CI/CD", "main"), DEFAULT_POLICY)
        assert row["route"] == "merge-first"
        assert "55" in row["detail"]
        # ডুপ্লিকেট fix-issue জন্মায়নি
        assert not api.issues

    def test_main_red_without_candidate_creates_template_compliant_fix(self):
        api = FakeApi()
        gh = FakeGh(log_text="no recognizable files here")
        row = route_failure(api, gh, _run("Main CI/CD", "main"), DEFAULT_POLICY)
        assert row["route"] == "new-fix"
        assert row["fix"] is not None
        fix = api.issues[0]
        # টাইটেল-রেজেক্স: ^(feat|fix|…)\(…\): …
        assert fix["title"].startswith("fix(ci): [ci-fail:")
        # টেমপ্লেট-সেকশন + P1 টোকেন (template_gate চুক্তি)
        body = fix["body"]
        for section in ("Mission", "Touching Files", "Verification"):
            assert section in body, f"missing section {section}"
        assert "P1-high" in body
        assert DEFAULT_POLICY["fix_marker_prefix"] in body

    def test_main_red_with_existing_fix_is_already_tracked(self):
        fp = fingerprint("Main CI/CD", "main")
        api = FakeApi(
            existing_fix_issues=[{"number": 42, "body": f"{DEFAULT_POLICY['fix_marker_prefix']}{fp}--> fix"}],
        )
        gh = FakeGh(log_text="nothing")
        row = route_failure(api, gh, _run("Main CI/CD", "main"), DEFAULT_POLICY)
        assert row["route"] == "already-tracked"
        assert row["fix"] == 42
        assert not api.issues  # নতুন জন্মায়নি

    def test_pr_branch_failure_is_pr_rebuild(self):
        api = FakeApi(open_prs=[_pr(66, "fix/2925-x", ["scripts/a.py"])])
        gh = FakeGh()
        row = route_failure(api, gh, _run("PR Gate (Unified Pipeline)", "fix/2925-x"), DEFAULT_POLICY)
        assert row["route"] == "pr-rebuild"
        assert row["pr"] == 66
        assert not api.issues

    def test_guard_violation_is_enforced(self):
        api = FakeApi()
        gh = FakeGh()
        row = route_failure(api, gh, _run("🌿 Branch Creation Guard", "fix/2999-y"), DEFAULT_POLICY)
        assert row["route"] == "enforced"
        assert not api.issues

    def test_branch_failure_without_pr_is_watching(self):
        api = FakeApi()
        gh = FakeGh()
        row = route_failure(api, gh, _run("PR Gate (Unified Pipeline)", "fix/no-pr-z"), DEFAULT_POLICY)
        assert row["route"] == "watching"


# ── ফাইল-নিষ্কাশন + গেট-সবুজ ────────────────────────────────────────────────

class TestExtraction:
    def test_extract_failed_files_ignores_runner_noise(self):
        gh = FakeGh(log_text=(
            "E   AssertionError in backend/core/engine.py line 4\n"
            "    /home/runner/work/_temp/x.sh noise\n"
            "    scripts/ci/helper.py touched too"
        ))
        files = extract_failed_files(gh, 111, DEFAULT_POLICY)
        assert "backend/core/engine.py" in files
        assert "scripts/ci/helper.py" in files
        assert not any("runner" in f for f in files)

    def test_pr_checks_green_requires_all_complete(self):
        gh = FakeGh(green_prs={5})
        assert pr_checks_green(gh, 5) is True
        assert pr_checks_green(gh, 6) is False

    def test_merge_first_requires_file_overlap(self):
        api = FakeApi(
            open_prs=[_pr(55, "fix/77-x", ["backend/other.py"])],
            pr_files_map={55: ["backend/other.py"]},
        )
        gh = FakeGh(log_text="FAILED backend/core/engine.py", green_prs={55})
        cands = merge_first_candidates(api, gh, _run("Main CI/CD", "main"), DEFAULT_POLICY)
        assert cands == []  # overlap নেই → ক্যান্ডিডেট নয়


# ── State roundtrip + render ─────────────────────────────────────────────────

class TestStateRender:
    def test_state_roundtrip(self):
        rows = [{
            "fp": "abc123", "workflow": "Main CI/CD", "branch": "main",
            "route": "new-fix", "count": 2, "first": "2026-10-01 20:00",
            "last": "2026-10-01 21:00", "pr": None, "fix": 33,
        }]
        state = parse_state(render_state(rows), DEFAULT_POLICY)
        assert state["abc123"]["count"] == 2
        assert state["abc123"]["fix"] == 33

    def test_render_body_has_table_and_marker(self):
        body = render_body(
            [{"fp": "x", "workflow": "W", "branch": "main", "route": "merge-first",
              "count": 1, "last": "now", "pr": 5, "fix": None, "detail": "PR #5"}],
            [{"workflow": "W", "branch": "b", "healed_at": "now"}],
            DEFAULT_POLICY,
        )
        assert "🎯 merge-first" in body
        assert "Recently healed" in body
        assert DEFAULT_POLICY["state_marker"] in body


# ── Full scan ────────────────────────────────────────────────────────────────

class TestScan:
    def test_scan_creates_register_and_dedup_comments(self):
        gh = FakeGh(failed_runs=[
            _run("PR Gate (Unified Pipeline)", "fix/2925-priority-merge-queue-system", run_id=1),
        ])
        api = FakeApi()
        summary = scan(api=api, gh=gh, pol=DEFAULT_POLICY)
        assert summary["register_created"] is True
        assert summary["active"] == 1
        reg_num = api.register_number
        # register issue জন্মেছে + body PATCH হয়েছে + একটি কমেন্ট গেছে
        assert any(p.get("labels") == DEFAULT_POLICY["register_labels"] for p in api.issues)
        assert api.patched
        assert len(api.comments.get(reg_num, [])) == 1

        # দ্বিতীয় স্ক্যান: একই ব্যর্থতা → নতুন কমেন্ট নয় (dedup)
        api2 = FakeApi(register_body=api.register_body, )
        api2.register_number = reg_num
        api2.comments[reg_num] = api.comments[reg_num]
        gh2 = FakeGh(failed_runs=[
            _run("PR Gate (Unified Pipeline)", "fix/2925-priority-merge-queue-system", run_id=1),
        ])
        summary2 = scan(api=api2, gh=gh2, pol=DEFAULT_POLICY)
        assert summary2["register_created"] is False
        assert len(api2.comments.get(reg_num, [])) == 1  # dedup ✅
        assert summary2["active"] == 1

    def test_scan_heals_resolved_failure(self):
        # প্রথম স্ক্যান: main-red
        gh = FakeGh(failed_runs=[_run("Main CI/CD", "main", run_id=7)])
        api = FakeApi()
        scan(api=api, gh=gh, pol=DEFAULT_POLICY)
        reg_num = api.register_number

        # দ্বিতীয় স্ক্যান: failure উইন্ডো-বাইরে, সর্বশেষ রান সবুজ → healed
        gh2 = FakeGh(failed_runs=[], latest={("Main CI/CD", "main"): "success"})
        api2 = FakeApi(register_body=api.register_body)
        api2.register_number = reg_num
        api2.comments[reg_num] = api.comments.get(reg_num, [])
        summary = scan(api=api2, gh=gh2, pol=DEFAULT_POLICY)
        assert summary["active"] == 0
        assert summary["healed"] == 1
        assert "Recently healed" in api2.register_body

    def test_scan_keeps_persistent_out_of_window_failure_active(self):
        gh = FakeGh(failed_runs=[_run("Main CI/CD", "main", run_id=7)])
        api = FakeApi()
        scan(api=api, gh=gh, pol=DEFAULT_POLICY)
        reg_num = api.register_number

        # উইন্ডো-বাইরে কিন্তু এখনো লাল → সক্রিয় থাকবে
        gh2 = FakeGh(failed_runs=[], latest={("Main CI/CD", "main"): "failure"})
        api2 = FakeApi(register_body=api.register_body)
        api2.register_number = reg_num
        api2.comments[reg_num] = api.comments.get(reg_num, [])
        summary = scan(api=api2, gh=gh2, pol=DEFAULT_POLICY)
        assert summary["active"] == 1
        assert summary["healed"] == 0

    def test_dry_run_creates_nothing(self):
        gh = FakeGh(failed_runs=[_run("Main CI/CD", "main")])
        api = FakeApi()
        summary = scan(api=api, gh=gh, pol=DEFAULT_POLICY, dry_run=True)
        assert not api.issues
        assert not api.patched
        assert not api.comments
        assert summary["active"] == 1


# ── Workflow wiring (YAML) ────────────────────────────────────────────────────

class TestWorkflowWiring:
    def test_handler_calls_register_and_guard_watched(self):
        from pathlib import Path
        wf = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "continuous-agent-loop.yml"
        text = wf.read_text(encoding="utf-8")
        # ভাঙা inline-bash আর নেই
        assert "git log --oneline -10" not in text
        assert 'grep -c "CI Failure' not in text
        # single-funnel register কল
        assert "pipeline_failure_register.py --event" in text
        # Branch Creation Guard ট্রিগারে যুক্ত
        assert '"🌿 Branch Creation Guard"' in text
