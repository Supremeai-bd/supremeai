# tests/test_nightly_ops_cron_bundle_2860.py
"""#2860 — nightly-ops cron বান্ডেল ১২→৪ চুক্তি-টেস্ট।

সংবিধান-চুক্তি (issue #2860 body):
1. schedule ব্লকে ঠিক ৪টি ক্যানোনিকাল cron (4-hourly/daily/weekly-Mon/weekly-Sun —
   #4085: hourly → 4-hourly re-canonicalized, cost-optimization decision অনুযায়ী)।
2. ২২টি job-এর প্রতিটির `if:`-শর্তে সঠিক `github.event.schedule` গার্ড (issue-র
   job→schedule পূর্ণ-ম্যাপ অনুযায়ী; #4267: #4228/#4261-যোগ ৫ job অন্তর্ভুক্ত)।
3. পুরনো cron-স্ট্রিং ফাইলে আর কোথাও নেই (grep-শূন্য)।
4. সব workflow_dispatch ইনপুট অক্ষত — ম্যানুয়াল আর্ম প্রতিটি job-এ এখনও চালু।
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
WF = REPO / ".github" / "workflows" / "nightly-ops.yml"

CANONICAL = ["0 3 * * *", "0 3 * * 0"]

# #67 Workflow Diet 2-tier contract + #72 vault synth check
TIER1_DAILY = {
    "vault-synth-check",
    "rate-limit-trend",
    "stale-mutex",
    "live-smoke",
    "db-retention",
    "db-pool-health",
    "branch-retention",
    "workflow-runs-retention",
}

TIER2_WEEKLY_SUN = {
    "deep-audit",
    "platform-deep-audit",
    "docs-garbage-sweep",
    "e2e-customer",
    "load-locust",
    "chaos-suite",
    "browser-e2e",
    "silent-error",
    "dast",
    "constitution",
    "self-audit",
}

DISPATCH_ONLY = {
    "ai-safety",
    "mission-passk",
    "platform-sweep",
}

DORMANT = {
    "deploy-doctor-fallback",
}

ALL_EXPECTED_JOBS = TIER1_DAILY | TIER2_WEEKLY_SUN | DISPATCH_ONLY | DORMANT

LEGACY_CRONS = [
    "30 1 * * *", "0 2 * * *", "15 3 * * *", "30 3 * * *",
    "45 3 * * *", "30 5 * * 1", "0 4 * * 1", "17 6 * * 1",
]


def _load():
    text = WF.read_text(encoding="utf-8")
    doc = yaml.safe_load(text)
    return text, doc


def test_yaml_parses_and_schedule_block_has_canonical_crons():
    _, doc = _load()
    triggers = doc.get(True) or doc.get("on") or {}
    crons = [s["cron"] for s in triggers["schedule"]]
    assert crons == CANONICAL, f"expected canonical crons {CANONICAL}, got: {crons}"


def test_every_job_has_expected_schedule_guard():
    _, doc = _load()
    jobs = doc["jobs"]
    assert set(jobs.keys()) == ALL_EXPECTED_JOBS, (
        f"job-set drift: {set(jobs.keys()) ^ ALL_EXPECTED_JOBS}"
    )
    for name in TIER1_DAILY:
        cond = str(jobs[name]["if"])
        assert "github.event.schedule == '0 3 * * *'" in cond, (
            f"Tier 1 job '{name}' must guard on '0 3 * * *' (got: {cond[:120]})"
        )
    for name in TIER2_WEEKLY_SUN:
        cond = str(jobs[name]["if"])
        assert "github.event.schedule == '0 3 * * 0'" in cond, (
            f"Tier 2 job '{name}' must guard on '0 3 * * 0' (got: {cond[:120]})"
        )
    for name in DISPATCH_ONLY:
        cond = str(jobs[name]["if"])
        assert "workflow_dispatch" in cond, (
            f"Dispatch-only job '{name}' must guard on workflow_dispatch (got: {cond[:120]})"
        )
    for name in DORMANT:
        cond = str(jobs[name].get("if", ""))
        assert "false" in cond.lower(), f"Dormant job '{name}' must be disabled (got: {cond})"


def test_no_legacy_cron_string_remains_in_file():
    text, _ = _load()
    stale = [c for c in LEGACY_CRONS if c in text]
    assert not stale, f"legacy crons still present: {stale}"


def test_every_schedule_gate_matches_declared_cron():
    """#4085 — cron-triple drift guard (defect class prevention).

    চুক্তি: schedule / gate / contract-test — এই তিন পায়ের যেকোনো একটি
    একা বদলানো নিষিদ্ধ। এই টেস্ট নিশ্চিত করে প্রতিটি `github.event.schedule == 'X'`
    গার্ডের X আসলেই এই ফাইলের schedule ব্লকে ঘোষিত কোনো না কোনো cron-এর সমান —
    নাহলে গার্ড dead হয়ে যায় (silent-failure doctrine লঙ্ঘন, #4085-এর মূল ক্ষত)।
    """
    import re

    text, doc = _load()
    triggers = doc.get(True) or doc.get("on") or {}
    declared = {s["cron"] for s in triggers["schedule"]}
    gate_re = re.compile(r"github\.event\.schedule\s*==\s*'([^']+)'")
    for name, job in doc["jobs"].items():
        cond = str(job.get("if", ""))
        if "github.event.schedule" not in cond:
            continue
        for gate in gate_re.findall(cond):
            assert gate in declared, (
                f"job '{name}' gates on schedule '{gate}' "
                f"but no cron declares it (declared: {sorted(declared)}) "
                f"— dead watchdog, cron-triple drift (#4085)"
            )


def test_dispatch_inputs_intact_all_arms_still_reachable():
    _, doc = _load()
    triggers = doc.get(True) or doc.get("on") or {}
    inputs = triggers.get("workflow_dispatch", {}).get("inputs", {})
    run_inputs = [k for k in inputs if k.startswith("run_")]
    # ১৭ job — প্রতিটির জন্য run_* ইনপুট (deep-audit...constitution ম্যানুয়াল আর্মসহ)
    assert len(run_inputs) >= 15, f"dispatch arms lost: only {len(run_inputs)} run_* inputs"
    # schedule-only job-গুলোর dispatch আর্ম এই ফাইলে থাকে না (ইচ্ছাকৃত):
    #   e2e-customer → PR/dispatch আর্ম e2e-suites.yml-এ (Phase E #1857 পর্যন্ত),
    #   deploy-doctor-fallback → ম্যানুয়াল আর্ম ops-console-এ (হেডার migration map)
    schedule_only = {"e2e-customer", "deploy-doctor-fallback", "vault-synth-check"}
    for name in ALL_EXPECTED_JOBS:
        if name in schedule_only:
            continue
        cond = str(doc["jobs"][name]["if"])
        assert "workflow_dispatch" in cond, (
            f"job '{name}' lost its workflow_dispatch arm"
        )
