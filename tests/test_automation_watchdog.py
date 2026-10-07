"""Contract tests for scripts/agents/automation_watchdog.py (#4168).

Issue-র Verification চুক্তির ৬ কেস:
  1. healthy heartbeat   2. stale heartbeat   3. stuck claim
  4. stale CI evaluator  5. duplicate suppression  6. recovery/auto-close

সব pure core চালায় — কোনো নেটওয়ার্ক/git subprocess নেই।
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# scripts/agents/automation_watchdog.py — সরাসরি path থেকে লোড
_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "agents" / "automation_watchdog.py"
_spec = importlib.util.spec_from_file_location("automation_watchdog", _SCRIPT)
_wd = importlib.util.module_from_spec(_spec)
sys.modules["automation_watchdog"] = _wd
_spec.loader.exec_module(_wd)

NOW = 1_800_000_000.0
H = 3600


# ---------------------------------------------------------------------------
# 1. healthy heartbeat
# ---------------------------------------------------------------------------
def test_healthy_heartbeat():
    out = _wd.assess_heartbeat(NOW - 5 * 60, NOW)  # ৫ মিনিট আগে
    assert out["state"] == "healthy" and out["age_s"] < _wd.HEARTBEAT_STALE_S
    findings = _wd.evaluate(
        {"heartbeats": [{"name": "loop-1", "last_seen_epoch": NOW - 5 * 60}],
         "evaluator": {"name": "e", "last_success_epoch": NOW - 5 * 60}}, NOW)
    assert findings == [], "সুস্থ heartbeat থেকে finding আসবে না"


# ---------------------------------------------------------------------------
# 2. stale heartbeat (+ missing record = unknown, কখনো মিথ্যে সুস্থ নয়)
# ---------------------------------------------------------------------------
def test_stale_and_missing_heartbeat():
    out = _wd.assess_heartbeat(NOW - 7 * H, NOW)   # ৭ ঘণ্টা নীরব > ৬ ঘণ্টা
    assert out["state"] == "stale" and out["age_s"] > _wd.HEARTBEAT_STALE_S
    out_none = _wd.assess_heartbeat(None, NOW)      # রেকর্ড-ই নেই → fail-closed
    assert out_none["state"] == "unknown" and "fail-closed" in out_none["reason"]
    findings = _wd.evaluate(
        {"heartbeats": [{"name": "loop-1", "last_seen_epoch": NOW - 7 * H},
                        {"name": "loop-2", "last_seen_epoch": None}]}, NOW)
    types = {(f["type"], f["scope"]) for f in findings}
    assert ("stale_heartbeat", "loop-1") in types
    assert ("stale_heartbeat", "loop-2") in types


# ---------------------------------------------------------------------------
# 3. stuck claim (in-progress + no has-pr + বয়স > ২৪ঘ; fresh/has-pr বাদ)
# ---------------------------------------------------------------------------
def test_stuck_claim_detection():
    obs = {"heartbeats": [],
           "claims": [
               {"issue": 123, "agent": "bot", "claimed_at_epoch": NOW - 30 * H,
                "has_pr": False, "open": True},          # stuck
               {"issue": 124, "agent": "bot", "claimed_at_epoch": NOW - 30 * H,
                "has_pr": True, "open": True},           # has-pr = চলছে, stuck নয়
               {"issue": 125, "agent": "bot", "claimed_at_epoch": NOW - 2 * H,
                "has_pr": False, "open": True},          # এখনো fresh (slow ≠ dead)
               {"issue": 126, "agent": "bot", "claimed_at_epoch": NOW - 30 * H,
                "has_pr": False, "open": False},         # বন্ধ issue নয়
           ]}
    findings = _wd.evaluate(obs, NOW)
    stuck = [f for f in findings if f["type"] == "stuck_claim"]
    assert len(stuck) == 1 and stuck[0]["scope"] == "issue-123"
    assert str(int(30 * H)) in stuck[0]["evidence"]


# ---------------------------------------------------------------------------
# 4. stale CI evaluator
# ---------------------------------------------------------------------------
def test_stale_ci_evaluator():
    obs = {"heartbeats": [], "claims": [],
           "evaluator": {"name": "ai-pr-evaluator", "last_success_epoch": NOW - 30 * H}}
    findings = _wd.evaluate(obs, NOW)
    assert any(f["type"] == "stale_ci_evaluator" for f in findings)
    # fresh evaluator → কোনো finding নয়
    obs["evaluator"]["last_success_epoch"] = NOW - 2 * H
    assert _wd.evaluate(obs, NOW) == []
    # evaluator রেকর্ড-ই নেই → unknown finding (fail-closed)
    obs["evaluator"]["last_success_epoch"] = None
    assert any(f["type"] == "stale_ci_evaluator" for f in _wd.evaluate(obs, NOW))


# ---------------------------------------------------------------------------
# 5. duplicate suppression — একই fp এক রিপোর্টে একবার; fp সময়-স্থিতিশীল
# ---------------------------------------------------------------------------
def test_duplicate_suppression_and_stable_fingerprint():
    obs = {"heartbeats": [{"name": "loop-1", "last_seen_epoch": NOW - 7 * H},
                          {"name": "loop-1", "last_seen_epoch": NOW - 9 * H}],  # একই scope দুইবার
           "claims": [],
           "evaluator": {"name": "e", "last_success_epoch": None}}
    findings = _wd.evaluate(obs, NOW)
    scopes = [f["scope"] for f in findings if f["type"] == "stale_heartbeat"]
    assert scopes.count("loop-1") == 1, "একই scope-এর ডুপ্লিকেট finding একবারই"
    # fingerprint সময়ের সাথে অপরিবর্তিত (dedup SSOT)
    fp1 = _wd.fingerprint("stale_heartbeat", "loop-1")
    fp2 = _wd.fingerprint("STALE_HEARTBEAT", " loop-1 ")  # normalization
    assert fp1 == fp2
    # marker রাউন্ড-ট্রিপ
    body = _wd.issue_body_for(findings[0])
    m = _wd.collect_watchdog_issues([{"number": 9, "title": "t", "body": body}])
    assert list(m.keys()) == [findings[0]["fingerprint"]]


# ---------------------------------------------------------------------------
# 6. recovery/auto-close — finding মিটলে আগের watchdog issue বন্ধ হবে
# ---------------------------------------------------------------------------
def test_recovery_autoclose():
    old_fp = _wd.fingerprint("stale_heartbeat", "loop-1")
    open_watchdog = _wd.collect_watchdog_issues([
        {"number": 9, "title": "watchdog: loop-1", "body": f"<!-- watchdog-fp:{old_fp} -->"},
        {"number": 10, "title": "unrelated", "body": "no marker"},   # marker-হীন বাদ
        {"number": 11, "title": "other fp", "body": "<!-- watchdog-fp:ffff -->"},
    ])
    assert set(open_watchdog.keys()) == {old_fp, "ffff"}
    # এখন loop-1 সুস্থ — findings খালি → দুটোই recovery
    recs = _wd.compute_recoveries(open_watchdog, findings=[])
    nums = sorted(r["issue"] for r in recs)
    assert nums == [9, 11]
    # কিন্তু loop-1 আবার stale হলে শুধু অন্যটা recovery
    fresh_findings = _wd.evaluate(
        {"heartbeats": [{"name": "loop-1", "last_seen_epoch": NOW - 7 * H}]}, NOW)
    recs2 = _wd.compute_recoveries(open_watchdog, fresh_findings)
    assert [r["issue"] for r in recs2] == [11]
