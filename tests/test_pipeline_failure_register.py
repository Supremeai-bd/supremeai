"""Tests for scripts/ci/pipeline_failure_register.py v2 (#2928 → #2935).

# বাংলা মন্তব্য: FakeApi/FakeGh ইনজেকশন — কোনো নেটওয়ার্ক কল নেই।
# v2-চুক্তি-কভারেজ: ডায়নামিক workflow-ট্র্যাকিং (নাম-হার্ডকোড নয়),
# এক-গ্রুপ-প্রতি-ব্যর্থতা-ইস্যু (group:pipeline-failures), held PR-এর
# কারণসহ per-PR issue (evaluator-শেয়ার্ড মার্কার), per-branch watching issue,
# enforced-no-issue (branch আর নেই), হীল হলে auto-close, কমেন্ট-dedup।
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
    pr_issue_key,
    pr_checks_green,
    render_body,
    render_state,
    route_failure,
    scan,
)

REPO = pfr.REPO


# ── Fakes ────────────────────────────────────────────────────────────────────

class FakeApi:
    """in-memory GitHub REST — issues/comments/pulls/branches এন্ডপয়েন্ট।"""

    def __init__(self, *, open_prs=None, pr_files_map=None, register_body="",
                 existing_fix_issues=None, checks_map=None,
                 existing_branches=None, open_pr_states=None,
                 branch_sha_map=None, closed_fix_issues=None):
        self.issues: list[dict] = []          # created via POST
        self.register_body = register_body
        self.register_number: int | None = None   # POST-এ জন্ম নিলে সেট
        self.existing_fix_issues = existing_fix_issues or []
        # v2.2 (#2983): fresh-tip gate-এর জন্য branch→HEAD-sha; closed-history
        # dedupe-এর জন্য সাম্প্রতিক-বন্ধ ci-failure ইস্যুর তালিকা।
        self.branch_sha_map = branch_sha_map or {}
        self.closed_fix_issues = closed_fix_issues or []
        self.comments: dict[int, list[dict]] = {}
        self.open_prs = open_prs or []
        self.pr_files_map = pr_files_map or {}
        self.checks_map = checks_map or {}
        self.existing_branches = existing_branches  # None = সব branch আছে; set = শুধু ওগুলো
        self.open_pr_states = open_pr_states or {}  # pr-number → "open"/"closed" (reconcile-GC)
        self.patched: list[dict] = []
        self.closed: list[tuple[int, dict]] = []
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
            if "/branches/" in endpoint:
                branch = endpoint.split("/branches/", 1)[1].split("?")[0]
                if self.existing_branches is None or branch in self.existing_branches:
                    if branch in self.branch_sha_map:
                        # #2983 fresh-tip gate: repos/X/branches/{b} → commit.sha
                        return {"name": branch, "commit": {"sha": self.branch_sha_map[branch]}}
                    return {"name": branch}
                raise AssertionError(f"404 branch {branch}")
            if "/pulls/" in endpoint and "/comments" not in endpoint and "/files" not in endpoint:
                # repos/X/pulls/{n} — reconcile-GC-র _pr_still_open চেক
                num = int(endpoint.rstrip("/").rsplit("/", 1)[1])
                state = self.open_pr_states.get(num, "open")
                if state == "missing":
                    raise AssertionError(f"404 pull {num}")
                return {"number": num, "state": state}
            if "comments" in endpoint:
                num = int(endpoint.split("/issues/")[1].split("/comments")[0])
                return self.comments.get(num, [])
            if "issues?state=open&labels=ci-failure" in endpoint:
                return self.existing_fix_issues
            if "issues?state=closed&labels=ci-failure" in endpoint:
                return self.closed_fix_issues
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
                # রেজিস্টার-পেলোড চিনে নিই (labels-এ pipeline-failure + type:ledger)
                labels = payload.get("labels") or []
                if "pipeline-failure" in labels and "type:ledger" in labels:
                    self.register_number = num
                    self.register_body = payload.get("body", self.register_body)
                return {"number": num, **payload}
        if method == "PATCH":
            if "state" in (payload or {}):
                num = int(endpoint.rsplit("/", 1)[1])
                self.closed.append((num, payload))
                return {}
            self.patched.append(payload)
            self.register_body = payload["body"]
            return {}
        raise AssertionError(f"unexpected {method} {endpoint}")


class FakeGh:
    """gh CLI ফেক — run-list / pr-view / run-view-log-failed।"""

    def __init__(self, *, failed_runs=None, latest=None, log_text="", green_prs=None,
                 failed_checks_map=None):
        self.failed_runs = failed_runs or []
        self.latest = latest or {}       # (workflow, branch) → conclusion
        self.log_text = log_text
        self.green_prs = green_prs or set()
        self.failed_checks_map = failed_checks_map or {}

    def __call__(self, *args):
        if args[0] == "run" and "list" in args:
            if "--workflow" in args:
                wf = args[args.index("--workflow") + 1]
                br = args[args.index("--branch") + 1]
                val = self.latest.get((wf, br))
                # v2.2 (#2983): dict হলে conclusion+headSha দুটোই (fresh-tip gate)
                if isinstance(val, dict):
                    return json.dumps([val])
                return json.dumps([{"conclusion": val}])
            return json.dumps(self.failed_runs)
        if args[0] == "pr" and "view" in args:
            num = int(args[args.index("view") + 1])
            if num in self.failed_checks_map:
                rollup = self.failed_checks_map[num]
            elif num in self.green_prs:
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
        # v2 (#2935): ডায়নামিক — wildcard, নাম-হার্ডকোড নয়
        assert pol["workflows_watched"] == ["*"]
        assert pol["merge_first"] is True
        assert pol["group_label"] == "group:pipeline-failures"
        assert "pr-rebuild" in pol["issueable_routes"]

    def test_fingerprint_stable(self):
        assert fingerprint("A", "b") == fingerprint("A", "b")
        assert fingerprint("A", "b") != fingerprint("A", "c")

    def test_pr_issue_key_shared_contract_with_evaluator(self):
        # শেয়ার্ড মার্কার-চুক্তি: ai_pr_evaluator.py একই কী ব্যবহার করে
        assert pr_issue_key(2926) == "pr:2926"
        assert f"{DEFAULT_POLICY['fix_marker_prefix']}{pr_issue_key(2926)}-->" == "<!-- pfr-fix:pr:2926-->"


# ── ডায়নামিক ট্র্যাকিং ───────────────────────────────────────────────────────

class TestDynamicDiscovery:
    def test_unknown_new_pipeline_is_tracked(self):
        # বাংলা মন্তব্য: ভবিষ্যতের নতুন pipeline-ও (নাম যাই হোক) স্ক্যানে আসবে
        gh = FakeGh(failed_runs=[_run("🆕 Totally New Future Pipeline", "main", run_id=9)])
        runs = pfr.list_failed_runs(gh, DEFAULT_POLICY)
        assert any(r["name"] == "🆕 Totally New Future Pipeline" for r in runs)

    def test_excluded_workflow_filtered(self):
        pol = {**DEFAULT_POLICY, "exclude_workflows": ["Noise Bot CI"]}
        gh = FakeGh(failed_runs=[
            _run("Noise Bot CI", "main", run_id=1),
            _run("Main CI/CD", "main", run_id=2),
        ])
        runs = pfr.list_failed_runs(gh, pol)
        assert [r["name"] for r in runs] == ["Main CI/CD"]

    def test_self_workflow_recursion_guard(self, monkeypatch):
        # GITHUB_WORKFLOW env → নিজেকে-রেজিস্টার recursion আটকায়
        monkeypatch.setenv("GITHUB_WORKFLOW", "Continuous Agent Loop")
        assert "Continuous Agent Loop" in pfr.excluded_workflows(DEFAULT_POLICY)

    def test_explicit_allowlist_escape_hatch(self):
        pol = {**DEFAULT_POLICY, "workflows_watched": ["Main CI/CD"]}
        gh = FakeGh(failed_runs=[
            _run("Other", "main", run_id=1),
            _run("Main CI/CD", "main", run_id=2),
        ])
        runs = pfr.list_failed_runs(gh, pol)
        assert [r["name"] for r in runs] == ["Main CI/CD"]


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
        # v2: গ্রুপ-লেবেল সহ
        assert "group:pipeline-failures" in fix["labels"]

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
        assert row["issue_key"] == "pr:66"  # শেয়ার্ড কী — evaluator-ও এটিই খোঁজে

    def test_branch_gone_without_pr_is_enforced_no_issue(self):
        # v2: guard-ডিলিট/ক্লিনআপ-করা branch — workflow-নাম নির্বিশেষে enforced
        api = FakeApi(existing_branches=set())
        gh = FakeGh()
        row = route_failure(api, gh, _run("🌿 Branch Creation Guard", "fix/2999-y"), DEFAULT_POLICY)
        assert row["route"] == "enforced"
        assert row["issue_key"] is None
        assert not api.issues

    def test_branch_alive_without_pr_is_watching_with_issue_key(self):
        api = FakeApi(existing_branches={"fix/no-pr-z"})
        gh = FakeGh()
        row = route_failure(api, gh, _run("PR Gate (Unified Pipeline)", "fix/no-pr-z"), DEFAULT_POLICY)
        assert row["route"] == "watching"
        assert row["issue_key"] == "branch:fix/no-pr-z"


# ── #2983: fresh-tip gate + closed-history dedupe (stale re-file লুপ রোধ) ────

class TestFreshTipGate:
    """v2.2 — পুরনো SHA-র main-ব্যর্থতা "RED on main" হিসেবে ফাইল হবে না।"""

    def _main_run(self, sha):
        run = _run("CI Pipeline", "main")
        run["headSha"] = sha
        return run

    def test_stale_sha_main_failure_is_stale_tip_no_issue(self):
        # লাইভ-ঘটনা #2989-এর পুনরাবৃত্তি: পুরনো SHA-র ব্যর্থতা, বর্তমান main এগিয়ে
        api = FakeApi(branch_sha_map={"main": "newtip999999"})
        gh = FakeGh(latest={("CI Pipeline", "main"): {"conclusion": "success", "headSha": "newtip999999"}})
        row = route_failure(api, gh, self._main_run("oldsha123456"), DEFAULT_POLICY)
        assert row["route"] == "stale-tip"
        assert row["fix"] is None
        assert not api.issues  # fix-issue জন্মায়নি
        assert "oldsha123456" in row["detail"] and "newtip999999" in row["detail"]

    def test_current_tip_main_failure_still_files(self):
        # ব্যর্থতা বর্তমান tip-এই — মূল আচরণ অক্ষুণ্ণ (P1 fix-issue জন্মায়)
        api = FakeApi(branch_sha_map={"main": "abcd12340000"})
        gh = FakeGh(log_text="no recognizable files")
        row = route_failure(api, gh, self._main_run("abcd12340000"), DEFAULT_POLICY)
        assert row["route"] == "new-fix"
        assert row["fix"] is not None
        assert len(api.issues) == 1

    def test_stale_sha_but_current_tip_red_still_files(self):
        # ব্যতিক্রম: workflow-র সর্বশেষ main-রান বর্তমান tip-এই লাল = সত্যিকারের main-red
        api = FakeApi(branch_sha_map={"main": "newtip999999"})
        gh = FakeGh(
            log_text="no files",
            latest={("CI Pipeline", "main"): {"conclusion": "failure", "headSha": "newtip999999"}},
        )
        row = route_failure(api, gh, self._main_run("oldsha123456"), DEFAULT_POLICY)
        assert row["route"] == "new-fix"
        assert row["fix"] is not None

    def test_gate_skipped_when_tip_unknown_fail_open(self):
        # branches-API পাওয়া যায়নি → gate স্কিপ → পুরনো আচরণ (সৎ-ফাইল)
        api = FakeApi()  # branch_sha_map খালি → tip=None
        gh = FakeGh(log_text="no files")
        row = route_failure(api, gh, self._main_run("whatever12345"), DEFAULT_POLICY)
        assert row["route"] == "new-fix"

    def test_gate_disabled_by_policy(self):
        pol = dict(DEFAULT_POLICY)
        pol["fresh_tip_gate"] = False
        api = FakeApi(branch_sha_map={"main": "newtip999999"})
        gh = FakeGh(log_text="no files")
        row = route_failure(api, gh, self._main_run("oldsha123456"), pol)
        assert row["route"] == "new-fix"

    def test_stale_tip_row_renders_with_label(self):
        body = render_body(
            [{"fp": "x", "workflow": "CI Pipeline", "branch": "main", "route": "stale-tip",
              "count": 3, "last": "now", "pr": None, "fix": None, "detail": ""}],
            [], DEFAULT_POLICY,
        )
        assert "🕰️ stale-tip" in body


class TestClosedHistoryDedupe:
    """v2.2 — একই marker-এ সাম্প্রতিক-বন্ধ ইস্যু থাকলে re-file নয় (#2979-82 লুপ)।"""

    def _closed_issue(self, num, fp, closed_at="2026-10-01T12:00:00Z", first_line=True):
        marker = f"{DEFAULT_POLICY['fix_marker_prefix']}{fp}-->"
        body = (f"{marker}\n## Mission\n…" if first_line
                else f"## আলোচনা\nউদ্ধৃতি: {marker} — অন্য ইস্যুর মার্কার")
        return {"number": num, "body": body, "closed_at": closed_at}

    def test_recently_closed_same_marker_suppresses_refile(self):
        fp = fingerprint("CI Pipeline", "main")
        api = FakeApi(
            branch_sha_map={"main": "abcd12340000"},  # tip-এই ব্যর্থ — gate পাস
            closed_fix_issues=[self._closed_issue(2979, fp, closed_at="2026-10-02T10:00:00Z")],
        )
        gh = FakeGh(log_text="no files")
        run = _run("CI Pipeline", "main")
        run["headSha"] = "abcd12340000"
        row = route_failure(api, gh, run, DEFAULT_POLICY)
        assert row["route"] == "already-tracked"
        assert row["fix"] == 2979
        assert "closed-history" in row["detail"]
        assert not api.issues  # পুনরায় জন্মায়নি

    def test_closed_outside_window_files_fresh(self):
        # ৭ দিনের বেশি পুরনো বন্ধ-ইস্যু — সত্যিকারের নতুন ঘটনা হলে ফাইল হবে
        fp = fingerprint("CI Pipeline", "main")
        api = FakeApi(
            branch_sha_map={"main": "abcd12340000"},
            closed_fix_issues=[self._closed_issue(2979, fp, closed_at="2026-09-01T00:00:00Z")],
        )
        gh = FakeGh(log_text="no files")
        run = _run("CI Pipeline", "main")
        run["headSha"] = "abcd12340000"
        row = route_failure(api, gh, run, DEFAULT_POLICY)
        assert row["route"] == "new-fix"
        assert row["fix"] is not None

    def test_quoted_marker_not_first_line_ignored(self):
        # বডির মাঝে উদ্ধৃত marker (অন্য ইস্যুর আলোচনা) ≠ নিজের মার্কার-চুক্তি
        fp = fingerprint("CI Pipeline", "main")
        api = FakeApi(
            branch_sha_map={"main": "abcd12340000"},
            closed_fix_issues=[self._closed_issue(2979, fp, first_line=False,
                                                  closed_at="2026-10-02T10:00:00Z")],
        )
        gh = FakeGh(log_text="no files")
        run = _run("CI Pipeline", "main")
        run["headSha"] = "abcd12340000"
        row = route_failure(api, gh, run, DEFAULT_POLICY)
        assert row["route"] == "new-fix"

    def test_pr_route_unaffected_by_closed_history(self):
        # pr:N/branch:X কী নয় — held PR-এর নতুন ব্যর্থতা = বৈধ নতুন hold-issue
        api = FakeApi(open_prs=[_pr(66, "fix/2925-x", ["scripts/a.py"])])
        gh = FakeGh()
        row = route_failure(api, gh, _run("PR Gate (Unified Pipeline)", "fix/2925-x"), DEFAULT_POLICY)
        assert row["route"] == "pr-rebuild"
        assert row["issue_key"] == "pr:66"


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

    def test_v1_state_body_still_parses(self):
        # বাংলা মন্তব্য: #2933-এর বর্তমান (v1-ফরম্যাট) state-ও v2 পড়তে পারে — মাইগ্রেশন লাগে না
        v1_body = (
            "<!-- pfr-state\n"
            "6366a949e6d9: PR Gate (Unified Pipeline)|fix/2919-smart-dispatcher|pr-rebuild|5|2026-10-01T20:24|2026-10-01T22:02|2921|\n"
            "-->"
        )
        state = parse_state(v1_body, DEFAULT_POLICY)
        assert state["6366a949e6d9"]["workflow"] == "PR Gate (Unified Pipeline)"
        assert state["6366a949e6d9"]["pr"] == 2921

    def test_render_body_has_table_group_doctrine_and_marker(self):
        body = render_body(
            [{"fp": "x", "workflow": "W", "branch": "main", "route": "merge-first",
              "count": 1, "last": "now", "pr": 5, "fix": 77, "detail": "PR #5"}],
            [{"workflow": "W", "branch": "b", "healed_at": "now", "fix": 77}],
            DEFAULT_POLICY,
        )
        assert "🎯 merge-first" in body
        assert "Recently healed" in body
        assert DEFAULT_POLICY["state_marker"] in body
        # v2: গ্রুপ-মডেল ব্যাখ্যা + fix-লিংক
        assert "group:pipeline-failures" in body
        assert "#77" in body

    def test_render_body_enforced_row_shows_auto_resolved(self):
        body = render_body(
            [{"fp": "y", "workflow": "🌿 Branch Creation Guard", "branch": "gone-branch",
              "route": "enforced", "count": 1, "last": "now", "pr": None, "fix": None}],
            [], DEFAULT_POLICY,
        )
        assert "auto-resolved" in body


# ── Full scan (v2: per-failure issues + auto-close) ──────────────────────────

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

    def test_scan_holds_pr_with_reasons_issue(self):
        # v2 কোর: held PR-এর ব্যর্থতা → কারণসহ per-PR issue (এক গ্রুপ, আলাদা ইস্যু)
        api = FakeApi(open_prs=[_pr(2926, "fix/2925-priority-merge-queue-system", ["scripts/a.py"])])
        gh = FakeGh(
            failed_runs=[
                _run("PR Gate (Unified Pipeline)", "fix/2925-priority-merge-queue-system", run_id=10),
                _run("🌿 Branch Creation Guard", "fix/2925-priority-merge-queue-system", run_id=11),
            ],
            failed_checks_map={2926: [
                {"name": "🚦 Unified PR Gate", "conclusion": "FAILURE"},
                {"name": "🛡️ Constitutional System Gates", "conclusion": "FAILURE"},
            ]},
            log_text="FAILED scripts/a.py assertion",
        )
        summary = scan(api=api, gh=gh, pol=DEFAULT_POLICY)
        assert summary["active"] == 2
        # ২টি ব্যর্থ workflow → কিন্তু মাত্র ১টি per-PR issue (একত্রীকরণ)
        pr_issues = [i for i in api.issues if "<!-- pfr-fix:pr:2926-->" in i["body"]]
        assert len(pr_issues) == 1
        body = pr_issues[0]["body"]
        # কারণ-তালিকা: workflow-নাম + লাল চেক + claim-chain + freshness
        assert "PR Gate (Unified Pipeline)" in body
        assert "🌿 Branch Creation Guard" in body
        assert "Unified PR Gate" in body
        assert "claim-chain" in body
        assert "freshness" in body
        # টেমপ্লেট-সম্মত + গ্রুপ-লেবেল
        for section in ("Mission", "Touching Files", "Verification"):
            assert section in body
        assert "group:pipeline-failures" in pr_issues[0]["labels"]
        assert "P2-medium" in pr_issues[0]["labels"]

    def test_scan_pr_hold_reuses_evaluator_created_issue(self):
        # শেয়ার্ড মার্কার-চুক্তি: evaluator-জন্ম ইস্যু থাকলে register নতুন বানায় না
        existing = [{
            "number": 4001,
            "body": f"{DEFAULT_POLICY['fix_marker_prefix']}pr:2926-->\n## Mission\n... (evaluator তৈরি)",
        }]
        api = FakeApi(
            open_prs=[_pr(2926, "fix/2925-x", ["scripts/a.py"])],
            existing_fix_issues=existing,
        )
        gh = FakeGh(failed_runs=[_run("PR Gate (Unified Pipeline)", "fix/2925-x", run_id=10)])
        summary = scan(api=api, gh=gh, pol=DEFAULT_POLICY)
        assert summary["created_fixes"] == []
        assert not any("pfr-fix:pr:2926" in (i.get("body") or "") for i in api.issues)

    def test_scan_watching_branch_gets_p3_issue(self):
        api = FakeApi(existing_branches={"fix/old-thing"})
        gh = FakeGh(failed_runs=[_run("Main CI/CD", "fix/old-thing", run_id=3)])
        summary = scan(api=api, gh=gh, pol=DEFAULT_POLICY)
        assert summary["active"] == 1
        watch_issues = [i for i in api.issues if "<!-- pfr-fix:branch:fix/old-thing-->" in i["body"]]
        assert len(watch_issues) == 1
        assert "P3-low" in watch_issues[0]["labels"]
        assert "resurrect" in watch_issues[0]["body"]

    def test_scan_enforced_branch_gone_no_issue(self):
        api = FakeApi(existing_branches=set())
        gh = FakeGh(failed_runs=[_run("🌿 Branch Creation Guard", "deleted-by-guard", run_id=4)])
        summary = scan(api=api, gh=gh, pol=DEFAULT_POLICY)
        assert summary["active"] == 1
        # register-ইস্যু ছাড়া কোনো ইস্যু জন্মায়নি
        non_register = [i for i in api.issues if "type:ledger" not in (i.get("labels") or [])]
        assert non_register == []

    def test_scan_heals_and_auto_closes_fix_issue(self):
        # প্রথম স্ক্যান: main-red → fix-issue #951 জন্ম
        gh = FakeGh(failed_runs=[_run("Main CI/CD", "main", run_id=7)])
        api = FakeApi()
        scan(api=api, gh=gh, pol=DEFAULT_POLICY)
        reg_num = api.register_number
        fix_num = next(i for i in api.issues if "type:ledger" not in i["labels"])
        created_num = 950 + api.issues.index(fix_num) + 1

        # দ্বিতীয় স্ক্যান: failure উইন্ডো-বাইরে, সর্বশেষ রান সবুজ → healed + issue close
        gh2 = FakeGh(failed_runs=[], latest={("Main CI/CD", "main"): "success"})
        api2 = FakeApi(register_body=api.register_body)
        api2.register_number = reg_num
        api2.comments[reg_num] = api.comments.get(reg_num, [])
        summary = scan(api=api2, gh=gh2, pol=DEFAULT_POLICY)
        assert summary["active"] == 0
        assert summary["healed"] == 1
        assert "Recently healed" in api2.register_body
        # v2: fix-issue auto-close (কারণ-কমেন্টসহ)
        closed_nums = [n for n, _ in api2.closed]
        assert created_num in closed_nums

    def test_scan_heal_does_not_close_issue_still_referenced_by_active_row(self):
        # per-PR issue এখনো অন্য লাল workflow-দ্বারা ব্যবহৃত → close হবে না
        api = FakeApi(open_prs=[_pr(80, "fix/x", ["a.py"])])
        gh = FakeGh(failed_runs=[
            _run("PR Gate (Unified Pipeline)", "fix/x", run_id=1),
            _run("Main CI/CD", "fix/x", run_id=2),
        ])
        scan(api=api, gh=gh, pol=DEFAULT_POLICY)
        reg_num = api.register_number
        first_state = api.register_body

        # এখন PR Gate সবুজ হলো কিন্তু Main CI/CD এখনো লাল — issue বাঁচবে
        gh2 = FakeGh(
            failed_runs=[_run("Main CI/CD", "fix/x", run_id=3, created="2026-10-01T22:00:00Z")],
            latest={("PR Gate (Unified Pipeline)", "fix/x"): "success"},
        )
        api2 = FakeApi(register_body=first_state, open_prs=[_pr(80, "fix/x", ["a.py"])])
        api2.register_number = reg_num
        api2.comments[reg_num] = api.comments.get(reg_num, [])
        summary = scan(api=api2, gh=gh2, pol=DEFAULT_POLICY)
        assert summary["active"] == 1  # Main CI/CD সারি এখনো সক্রিয়
        assert api2.closed == []       # per-PR issue close হয়নি — এখনো দরকার

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


# ── v2.1 (#2960): উইন্ডো-ভেতরেই হীল ─────────────────────────────────────────

class TestWithinWindowHeal:
    """#2960 root-cause: সর্বশেষ রান সবুজ হলে উইন্ডো-ভেতরের fp-ও হীল।

    লাইভ-ঘটনা: Issue Template Guard main-এ একবার লাল → fix-ইস্যু #2960 জন্ম →
    পরের রানগুলো সবুজ — কিন্তু ব্যর্থ রান স্ক্যান-উইন্ডোতে থাকায় ইস্যুটি অযথা
    খোলা পড়ে ছিল। এখন প্রতিটি active fp-এর workflow+branch সর্বশেষ রান দেখা
    হয় — সবুজ হলে সাথে সাথে healed + fix-ইস্যু auto-close।
    """

    def test_recovered_failure_heals_inside_window(self):
        # প্রথম স্ক্যান: main-red → fix-issue জন্ম
        gh = FakeGh(failed_runs=[_run("Main CI/CD", "main", run_id=7)])
        api = FakeApi()
        scan(api=api, gh=gh, pol=DEFAULT_POLICY)
        reg_num = api.register_number
        fix_num = next(i for i in api.issues if "type:ledger" not in i["labels"])
        created_num = 950 + api.issues.index(fix_num) + 1

        # দ্বিতীয় স্ক্যান: ব্যর্থ রান এখনো উইন্ডোতে, কিন্তু সর্বশেষ রান সবুজ
        gh2 = FakeGh(
            failed_runs=[_run("Main CI/CD", "main", run_id=7)],
            latest={("Main CI/CD", "main"): "success"},
        )
        api2 = FakeApi(register_body=api.register_body)
        api2.register_number = reg_num
        api2.comments[reg_num] = api.comments.get(reg_num, [])
        summary = scan(api=api2, gh=gh2, pol=DEFAULT_POLICY)
        assert summary["active"] == 0
        assert summary["healed"] == 1
        assert "Recently healed" in api2.register_body
        # fix-issue auto-close (healed-কমেন্টসহ) — অযথা খোলা থাকে না
        assert created_num in [n for n, _ in api2.closed]

    def test_still_red_failure_stays_active_in_window(self):
        gh = FakeGh(
            failed_runs=[_run("Main CI/CD", "main", run_id=7)],
            latest={("Main CI/CD", "main"): "failure"},
        )
        api = FakeApi()
        summary = scan(api=api, gh=gh, pol=DEFAULT_POLICY)
        assert summary["active"] == 1
        assert summary["healed"] == 0

    def test_deleted_branch_no_latest_no_false_heal(self):
        # guard-ডিলিট প্রোটোকল-branch: latest-রান অজানা (None) → মিথ্যা-হীল নয়
        gh = FakeGh(failed_runs=[_run("🌿 Branch Creation Guard", "role/ci-fixer", run_id=9)])
        api = FakeApi()
        summary = scan(api=api, gh=gh, pol=DEFAULT_POLICY)
        assert summary["active"] == 1
        assert summary["healed"] == 0

    def test_no_double_heal_between_in_and_out_of_window_paths(self):
        # উইন্ডো-ভেতরে হীল হলে উইন্ডো-বাইরের পথে একই fp আর একবার হীল হবে না
        fp = fingerprint("Main CI/CD", "main")
        prev_body = (
            "<!-- pfr-state\n"
            f"{fp}: Main CI/CD|main|new-fix|3|2026-10-01T20:00|2026-10-01T21:00||951\n"
            "-->"
        )
        gh = FakeGh(
            failed_runs=[_run("Main CI/CD", "main", run_id=7)],
            latest={("Main CI/CD", "main"): "success"},
        )
        api = FakeApi(register_body=prev_body)
        api.register_number = 900
        summary = scan(api=api, gh=gh, pol=DEFAULT_POLICY)
        assert summary["healed"] == 1  # ডাবল-এন্ট্রি নয়
        assert summary["active"] == 0

    def test_healed_pr_hold_row_closes_when_gates_green(self):
        # pr-hold সারি: PR-গেট সবুজ হলে hold-ইস্যু healed — ci-fixer অপেক্ষায় থাকে না
        api = FakeApi(open_prs=[_pr(80, "fix/x", ["a.py"])])
        gh = FakeGh(failed_runs=[
            _run("PR Gate (Unified Pipeline)", "fix/x", run_id=1),
        ])
        scan(api=api, gh=gh, pol=DEFAULT_POLICY)
        reg_num = api.register_number
        first_state = api.register_body
        hold_num = next((n for n, _ in api.closed), None)
        assert hold_num is None  # এখনো লাল — কিছু বন্ধ হয়নি

        gh2 = FakeGh(
            failed_runs=[_run("PR Gate (Unified Pipeline)", "fix/x", run_id=1)],
            latest={("PR Gate (Unified Pipeline)", "fix/x"): "success"},
        )
        api2 = FakeApi(register_body=first_state, open_prs=[_pr(80, "fix/x", ["a.py"])])
        api2.register_number = reg_num
        api2.comments[reg_num] = api.comments.get(reg_num, [])
        summary = scan(api=api2, gh=gh2, pol=DEFAULT_POLICY)
        assert summary["active"] == 0
        assert summary["healed"] == 1


# ── পুনর্মিলন (race-পরবর্তী dedup + orphan-GC — লাইভ-ঘটনা #2939/#2940) ────────

import datetime as _dt  # noqa: E402 — টেস্ট-স্কোপে দেরিতে import


def _iso(minutes_ago: int) -> str:
    t = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(minutes=minutes_ago)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


class TestReconcile:
    def test_race_duplicates_close_all_but_oldest(self):
        # লাইভ-ঘটনা পুনরাবৃত্তি: ৯-সেকেন্ড ব্যবধানে দুটি একই-মার্কার ইস্যু
        marker = f"{DEFAULT_POLICY['fix_marker_prefix']}abc123-->"
        api = FakeApi(existing_fix_issues=[
            {"number": 2939, "body": marker + "\n## Mission", "created_at": _iso(45)},
            {"number": 2940, "body": marker + "\n## Mission", "created_at": _iso(44)},
        ])
        out = pfr.reconcile_fix_issues(api, DEFAULT_POLICY, active=[])
        # প্রাচীনতম #2939 বাঁচল (নকল-তালিকায় নেই); #2940 (নকল) close + কারণ-কমেন্ট
        assert 2940 in out["closed_dupes"]
        closed_nums = [n for n, _ in api.closed]
        assert 2940 in closed_nums
        # প্রাচীনতমটিও পরে orphan-GC হলো (active-রেফারেন্স নেই + grace পার)
        assert 2939 in out["closed_orphans"]
        assert 2939 in closed_nums

    def test_orphan_within_grace_is_kept(self):
        marker = f"{DEFAULT_POLICY['fix_marker_prefix']}xyz-->"
        api = FakeApi(existing_fix_issues=[
            {"number": 3001, "body": marker, "created_at": _iso(5)},  # ৫ মিনিট আগে — grace-ভিতর
        ])
        out = pfr.reconcile_fix_issues(api, DEFAULT_POLICY, active=[])
        assert out["closed_orphans"] == []
        assert api.closed == []

    def test_orphan_after_grace_closed_when_not_active(self):
        marker = f"{DEFAULT_POLICY['fix_marker_prefix']}old-fp-->"
        api = FakeApi(existing_fix_issues=[
            {"number": 3002, "body": marker, "created_at": _iso(90)},
        ])
        out = pfr.reconcile_fix_issues(api, DEFAULT_POLICY, active=[])
        assert 3002 in out["closed_orphans"]
        assert 3002 in [n for n, _ in api.closed]

    def test_active_referenced_issue_survives_gc(self):
        marker = f"{DEFAULT_POLICY['fix_marker_prefix']}live-fp-->"
        api = FakeApi(existing_fix_issues=[
            {"number": 3003, "body": marker, "created_at": _iso(120)},
        ])
        active = [{"fp": "live-fp", "fix": 3003, "route": "new-fix"}]
        out = pfr.reconcile_fix_issues(api, DEFAULT_POLICY, active=active)
        assert out["closed_orphans"] == []
        assert api.closed == []

    def test_pr_marker_issue_kept_while_pr_open(self):
        # held-PR ইস্যু: PR open থাকা পর্যন্ত GC-সুরক্ষিত (কারণগুলো এখনো অ্যাকশনেবল)
        marker = f"{DEFAULT_POLICY['fix_marker_prefix']}pr:2926-->"
        api = FakeApi(
            existing_fix_issues=[{"number": 3004, "body": marker, "created_at": _iso(90)}],
            open_pr_states={2926: "open"},
        )
        out = pfr.reconcile_fix_issues(api, DEFAULT_POLICY, active=[])
        assert out["closed_orphans"] == []

    def test_pr_marker_issue_gc_after_pr_closed(self):
        marker = f"{DEFAULT_POLICY['fix_marker_prefix']}pr:2926-->"
        api = FakeApi(
            existing_fix_issues=[{"number": 3005, "body": marker, "created_at": _iso(90)}],
            open_pr_states={2926: "closed"},
        )
        out = pfr.reconcile_fix_issues(api, DEFAULT_POLICY, active=[])
        assert 3005 in out["closed_orphans"]

    def test_claimed_in_progress_issue_survives_gc(self):
        # #2960 লাইভ-ঘটনা (2026-10-02 01:43): orphan-GC claimed+in-progress
        # ইস্যু বন্ধ করেছিল → Branch Creation Guard কাজ-চলা branch মুছে ফেলেছিল
        # ("issue is closed")। এখন claim-সুরক্ষা-উইন্ডোর ভেতরে GC নয়।
        marker = f"{DEFAULT_POLICY['fix_marker_prefix']}claimed-fp-->"
        issue = {
            "number": 3006,
            "body": marker,
            "created_at": _iso(90),
            "labels": [{"name": "ci-failure"}, {"name": "status:in-progress"}],
        }
        api = FakeApi(existing_fix_issues=[issue])
        api.comments[3006] = [
            {
                "body": "### 🔒 Atomic Claim Established — glm5.2-coder-1",
                "created_at": _iso(30),  # ৩০ মিনিট আগের claim — সাম্প্রতিক
            }
        ]
        out = pfr.reconcile_fix_issues(api, DEFAULT_POLICY, active=[])
        assert out["closed_orphans"] == []
        assert api.closed == []

    def test_abandoned_old_claim_still_gcs(self):
        # পরিত্যক্ত claim: লেবেল আছে কিন্তু সর্বশেষ claim ৬+ ঘণ্টা পুরনো →
        # claim-সুরক্ষা-উইন্ডো পার → GC হবে (চিরস্থায়ী-লেবেল-ফাঁদ নয়)
        marker = f"{DEFAULT_POLICY['fix_marker_prefix']}old-claim-fp-->"
        issue = {
            "number": 3007,
            "body": marker,
            "created_at": _iso(600),
            "labels": [{"name": "ci-failure"}, {"name": "status:in-progress"}],
        }
        api = FakeApi(existing_fix_issues=[issue])
        api.comments[3007] = [
            {
                "body": "### 🔒 Atomic Claim Established — someone",
                "created_at": _iso(400),  # ~৬.৬ ঘণ্টা আগে — উইন্ডো-বাইরে
            }
        ]
        out = pfr.reconcile_fix_issues(api, DEFAULT_POLICY, active=[])
        assert 3007 in out["closed_orphans"]

    def test_claim_without_in_progress_label_gcs(self):
        # in-progress লেবেল নেই (release হয়ে গেছে) → claim-সুরক্ষা প্রযোজ্য নয়
        marker = f"{DEFAULT_POLICY['fix_marker_prefix']}released-fp-->"
        issue = {
            "number": 3008,
            "body": marker,
            "created_at": _iso(90),
            "labels": [{"name": "ci-failure"}],
        }
        api = FakeApi(existing_fix_issues=[issue])
        api.comments[3008] = [
            {
                "body": "### 🔒 Atomic Claim Established — someone",
                "created_at": _iso(30),
            }
        ]
        out = pfr.reconcile_fix_issues(api, DEFAULT_POLICY, active=[])
        assert 3008 in out["closed_orphans"]

    def test_scan_summary_includes_reconciled(self):
        gh = FakeGh(failed_runs=[])
        api = FakeApi(register_body="empty", existing_fix_issues=[
            {"number": 4002, "body": f"{DEFAULT_POLICY['fix_marker_prefix']}zz-->", "created_at": _iso(90)},
        ])
        api.register_number = 900
        summary = scan(api=api, gh=gh, pol=DEFAULT_POLICY)
        assert summary["reconciled"]["closed_orphans"] == [4002]


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
        # v2 (#2935): ডায়নামিক পূর্ণ-স্ক্যান job — নতুন pipeline-ও ধরবে
        assert "pipeline_failure_register.py --scan" in text

    def test_pr_gate_wires_freshness_gate(self):
        from pathlib import Path
        wf = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "pr.yml"
        text = wf.read_text(encoding="utf-8")
        assert "freshness_gate.py --pr" in text

    def test_ai_pr_evaluation_workflow_exists(self):
        from pathlib import Path
        wf = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ai-pr-evaluation.yml"
        text = wf.read_text(encoding="utf-8")
        assert "ai_pr_evaluator.py" in text
        # নিরাপত্তা: evaluator main থেকেই চলে (verdict-integrity)
        assert "ref: main" in text
