# tests/test_nightly_ops_cron_bundle_2860.py
"""#2860 — nightly-ops cron বান্ডেল ১২→৪ চুক্তি-টেস্ট।

সংবিধান-চুক্তি (issue #2860 body):
1. schedule ব্লকে ঠিক ৪টি ক্যানোনিকাল cron (hourly/daily/weekly-Mon/weekly-Sun)।
2. ১৭টি job-এর প্রতিটির `if:`-শর্তে সঠিক `github.event.schedule` গার্ড (issue-র
   job→schedule পূর্ণ-ম্যাপ অনুযায়ী)।
3. পুরনো cron-স্ট্রিং ফাইলে আর কোথাও নেই (grep-শূন্য)।
4. সব workflow_dispatch ইনপুট অক্ষত — ম্যানুয়াল আর্ম প্রতিটি job-এ এখনও চালু।
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
WF = REPO / ".github" / "workflows" / "nightly-ops.yml"

CANONICAL = ["0 * * * *", "0 3 * * *", "17 3 * * 1", "0 3 * * 0"]

# issue #2860-র পূর্ণ job→schedule ম্যাপ (১৭ job)
EXPECTED_MAP = {
    "deep-audit": "0 3 * * *",
    "ai-safety": "0 3 * * *",
    "mission-passk": "0 3 * * *",
    "platform-sweep": "0 3 * * *",
    "platform-deep-audit": "0 3 * * *",
    "rate-limit-trend": "0 3 * * *",
    "stale-mutex": "0 3 * * *",
    "live-smoke": "0 3 * * *",
    "db-retention": "0 3 * * *",
    "workflow-runs-retention": "0 3 * * *",
    "e2e-customer": "0 3 * * *",
    "branch-retention": "17 3 * * 1",
    "silent-error": "17 3 * * 1",
    "dast": "17 3 * * 1",
    "constitution": "17 3 * * 1",
    "self-audit": "0 3 * * 0",
    "deploy-doctor-fallback": "0 * * * *",
}

LEGACY_CRONS = [
    "30 1 * * *", "0 2 * * *", "15 3 * * *", "30 3 * * *",
    "45 3 * * *", "30 5 * * 1", "0 4 * * 1", "17 6 * * 1",
]


def _load():
    text = WF.read_text(encoding="utf-8")
    doc = yaml.safe_load(text)
    return text, doc


def test_yaml_parses_and_schedule_block_has_exactly_4_canonical_crons():
    _, doc = _load()
    triggers = doc.get(True) or doc.get("on") or {}
    crons = [s["cron"] for s in triggers["schedule"]]
    assert sorted(crons) == sorted(CANONICAL), f"expected 4 canonical crons, got: {crons}"
    # ইস্যু-বডির আক্ষরিক তালিকার সাথে ক্রমানুসারেও মিলবে
    assert crons == CANONICAL


def test_every_job_has_expected_schedule_guard():
    _, doc = _load()
    jobs = doc["jobs"]
    assert set(jobs.keys()) == set(EXPECTED_MAP.keys()), (
        f"job-set drift: {set(jobs.keys()) ^ set(EXPECTED_MAP.keys())}"
    )
    for name, cron in EXPECTED_MAP.items():
        cond = str(jobs[name]["if"])
        assert f"github.event.schedule == '{cron}'" in cond, (
            f"job '{name}' must guard on '{cron}' (got: {cond[:120]})"
        )


def test_no_legacy_cron_string_remains_in_file():
    text, _ = _load()
    stale = [c for c in LEGACY_CRONS if c in text]
    assert not stale, f"legacy crons still present: {stale}"


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
    schedule_only = {"e2e-customer", "deploy-doctor-fallback"}
    for name in EXPECTED_MAP:
        if name in schedule_only:
            continue
        cond = str(doc["jobs"][name]["if"])
        assert "workflow_dispatch" in cond, (
            f"job '{name}' lost its workflow_dispatch arm"
        )
