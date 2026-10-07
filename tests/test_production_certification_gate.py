"""Contract tests for scripts/ci/production_certification.py (#4167).

Issue-র Verification চুক্তি অনুযায়ী ৪টি কনট্রাক্ট কেস + deterministic verdict:
  1. stale evidence (SHA mismatch + age)  -> STALE, কখনো PASS নয়
  2. missing evidence                     -> UNKNOWN (fail-closed)
  3. SHA mismatch                         -> STALE (critical => NO-GO)
  4. successful certification             -> GO

সব টেস্ট pure core (assess_evidence / compute_verdict) চালায় — কোনো নেটওয়ার্ক/git নেই।
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

# scripts/ci/production_certification.py — সরাসরি path থেকে লোড (প্যাকেজ-নিরপেক্ষ)
_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ci" / "production_certification.py"
_spec = importlib.util.spec_from_file_location("production_certification", _SCRIPT)
_cert = importlib.util.module_from_spec(_spec)
sys.modules["production_certification"] = _cert
_spec.loader.exec_module(_cert)

CANDIDATE = "a" * 40
NOW = 1_800_000_000.0  # fixed epoch — deterministic


def _iso(epoch: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


# ---------------------------------------------------------------------------
# 1. STALE evidence — পুরনো প্রমাণ থেকে কখনো PASS infer হয় না
# ---------------------------------------------------------------------------
def test_stale_evidence_by_age():
    item = {
        "status": "PASS",
        "source": "deploy-train.yml run 1",
        "evidence_sha": CANDIDATE,
        "checked_at": _iso(NOW - 8 * 24 * 3600),  # ৮ দিন পুরনো > ৭ দিন max
        "max_age_s": _cert.DEFAULT_MAX_AGE_S,
        "critical": True,
    }
    out = _cert.assess_evidence(item, CANDIDATE, now=NOW)
    assert out["status"] == "STALE", f"পুরনো প্রমাণ STALE হওয়া চাই, পেলাম {out['status']}"
    assert "age" in out["reason"]
    # verdict: critical STALE = fail-closed NO-GO
    assert _cert.compute_verdict({"deploy_freshness": out}) == "NO-GO"


def test_stale_evidence_by_sha_mismatch():
    other = "b" * 40
    item = {
        "status": "PASS",
        "source": "deploy-train.yml run 1",
        "evidence_sha": other,  # evidence অন্য commit-এর সম্পর্কে
        "checked_at": _iso(NOW),
        "critical": True,
    }
    out = _cert.assess_evidence(item, CANDIDATE, now=NOW)
    assert out["status"] == "STALE"
    assert other[:7] in out["reason"] and CANDIDATE[:7] in out["reason"]


# ---------------------------------------------------------------------------
# 2. Missing evidence — fail-closed, কখনো PASS নয়
# ---------------------------------------------------------------------------
def test_missing_evidence_is_unknown_never_pass():
    # (ক) status-ই নেই (collector ব্যর্থ)
    out = _cert.assess_evidence({"source": "deploy-train.yml", "critical": True}, CANDIDATE, now=NOW)
    assert out["status"] == "UNKNOWN"
    # (খ) status আছে কিন্তু checked_at নেই — timestamp ছাড়া প্রমাণ নয়
    out2 = _cert.assess_evidence(
        {"status": "PASS", "source": "x", "evidence_sha": CANDIDATE, "critical": True},
        CANDIDATE, now=NOW,
    )
    assert out2["status"] == "UNKNOWN"
    assert "timestamp" in out2["reason"]
    # verdict: critical UNKNOWN = NO-GO (fail closed)
    assert _cert.compute_verdict({"sha_alignment": out}) == "NO-GO"
    assert _cert.compute_verdict({"sha_alignment": out2}) == "NO-GO"


# ---------------------------------------------------------------------------
# 3. SHA mismatch — deploy ভিন্ন commit-এ হলে candidate certify হয় না
# ---------------------------------------------------------------------------
def test_sha_mismatch_blocks_certification():
    deployed = "c" * 40
    item = {
        "status": "PASS",  # collector: deploy সফল ছিল
        "source": "deploy-train.yml run 99",
        "evidence_sha": deployed,  # কিন্তু ভিন্ন SHA-র
        "checked_at": _iso(NOW),
        "critical": True,
    }
    out = _cert.assess_evidence(item, CANDIDATE, now=NOW)
    assert out["status"] == "STALE"
    # critical-এ STALE = NO-GO — ভিন্ন SHA-র deploy candidate-কে cover করে না
    assert _cert.compute_verdict({"sha_alignment": out}) == "NO-GO"


# ---------------------------------------------------------------------------
# 4. Successful certification — সব প্রমাণ টাটকা + মিললে GO
# ---------------------------------------------------------------------------
def test_successful_certification_is_go():
    fresh = _iso(NOW - 60)
    items = {
        # critical ৫টি — সব PASS, টাটকা, SHA-মিল
        "release_freeze_git": _cert.assess_evidence(
            {"status": "PASS", "source": "git", "evidence_sha": CANDIDATE, "checked_at": fresh},
            CANDIDATE, now=NOW),
        "ci_green": _cert.assess_evidence(
            {"status": "PASS", "source": "check-runs API", "evidence_sha": CANDIDATE, "checked_at": fresh},
            CANDIDATE, now=NOW),
        "sha_alignment": _cert.assess_evidence(
            {"status": "PASS", "source": "deploy-train.yml run 1", "evidence_sha": CANDIDATE, "checked_at": fresh},
            CANDIDATE, now=NOW),
        "deploy_freshness": _cert.assess_evidence(
            {"status": "PASS", "source": "deploy-train.yml run 1", "evidence_sha": CANDIDATE,
             "checked_at": fresh, "max_age_s": _cert.DEFAULT_MAX_AGE_S},
            CANDIDATE, now=NOW),
        "secret_scan": _cert.assess_evidence(
            {"status": "PASS", "source": "regex scan", "evidence_sha": CANDIDATE, "checked_at": fresh},
            CANDIDATE, now=NOW),
        # non-critical প্রথমে PASS — পরে ladder-এ UNKNOWN করা হবে
        "ruff_lint": _cert.assess_evidence(
            {"status": "PASS", "source": "ruff", "evidence_sha": CANDIDATE, "checked_at": fresh},
            CANDIDATE, now=NOW),
        # NA সহনীয়
        "rollback_target": _cert.assess_evidence(
            {"status": "NA", "source": "deploy-train.yml", "checked_at": fresh},
            CANDIDATE, now=NOW),
    }
    verdict = _cert.compute_verdict(items)
    assert verdict == "GO", f"সবুজ প্রমাণে GO চাই, পেলাম {verdict}"
    # ladder: একই non-critical item UNKNOWN হলে -> CONDITIONAL (NO-GO নয়)
    items["ruff_lint"] = _cert.assess_evidence({"status": "", "source": "ruff"}, CANDIDATE, now=NOW)
    assert _cert.compute_verdict(items) == "CONDITIONAL"
    # আর সেটি critical হলে -> NO-GO (fail-closed)
    items["ruff_lint"]["critical"] = True
    assert _cert.compute_verdict(items) == "NO-GO"


# ---------------------------------------------------------------------------
# বোনাস কনট্রাক্ট: সরাসরি FAIL সর্বদা NO-GO; non-critical UNKNOWN = CONDITIONAL
# ---------------------------------------------------------------------------
def test_fail_is_always_no_go_and_noncritical_unknown_is_conditional():
    fail_item = _cert.assess_evidence(
        {"status": "FAIL", "source": "git", "evidence_sha": CANDIDATE,
         "checked_at": _iso(NOW), "critical": False},
        CANDIDATE, now=NOW)
    assert fail_item["status"] == "FAIL"
    assert _cert.compute_verdict({"x": fail_item}) == "NO-GO"

    unk = _cert.assess_evidence({"status": "", "source": "s"}, CANDIDATE, now=NOW)
    assert _cert.compute_verdict({"noncritical": unk}) == "CONDITIONAL"
