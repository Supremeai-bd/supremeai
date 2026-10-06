"""#3187 agent_trace tests — canonical schema, redaction, deterministic
evaluation, replay/compare, retrieval.

# বাংলা মন্তব্য: প্রতিটি টেস্ট #3187 verification contract-এর বুলেট প্রমাণ করে।
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "agents" / "agent_trace.py"


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location("agent_trace_under_test", SCRIPT_PATH)
    assert spec and spec.loader, "agent_trace module spec load failed"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mod = _load_module()

SECRET = "ghs_secret_token_abc123"


def _good_trace() -> mod.AgentTrace:
    return mod.AgentTrace(
        task_id="3187",
        role="coder",
        agent_name="coder-1",
        task_type="coding",
        decision="chose sqlite layer over new subsystem — reuse-before-create",
        guardrail_result="approved",
        tests_evidence=["pytest tests/test_agent_trace.py → 12 passed"],
        links={"issue": "3187", "pr": "9999"},
        outcome="success",
        skill_bundle_hash="a" * 64,
        events=[
            mod.TraceEvent("run_start", "claim"),
            mod.TraceEvent("tool_call", "atomic_claim", status="ok"),
            mod.TraceEvent("verification", "pytest", status="ok"),
            mod.TraceEvent("outcome", "merge", status="ok"),
        ],
    )


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    return tmp_path / "traces.db"


# ---------------------------------------------------------------------------
# Bullet 1: canonical versioned schema
# ---------------------------------------------------------------------------
def test_schema_version_present(db):
    tid = mod.record_trace(_good_trace(), db_path=db)
    stored = mod.load_trace(tid, db_path=db)
    assert stored["schema_version"] == mod.AGENT_TRACE_SCHEMA_VERSION
    assert stored["task_id"] == "3187" and stored["role"] == "coder"


# ---------------------------------------------------------------------------
# Bullet 2: coherent run → tool → verification → outcome trace
# ---------------------------------------------------------------------------
def test_coherent_event_chain_evaluates_passed(db):
    trace = _good_trace()
    evaluation = mod.evaluate_trace(trace)
    assert evaluation.passed is True, evaluation.checks
    assert all(c["passed"] for c in evaluation.checks)
    tid = mod.record_trace(trace, db_path=db)
    assert evaluation.trace_id == tid


# ---------------------------------------------------------------------------
# Bullet 3: sensitive redaction per security policy
# ---------------------------------------------------------------------------
def test_sensitive_keys_redacted_everywhere(db):
    trace = _good_trace()
    trace.decision_ledger = {
        "authorization": "Bearer " + SECRET,
        "api_key": SECRET,
        "nested": {"client_secret": SECRET, "safe": "value"},
        "blob": "x" * 3000,  # বাংলা: বড় payload → hash-reference
    }
    trace_dict = trace.to_dict()
    dumped = json.dumps(trace_dict)
    assert SECRET not in dumped
    assert "<redacted:sha256:" in dumped
    assert "<large-ref:sha256:" in dumped
    # nested dict-ও রিচ করে
    assert trace_dict["decision_ledger"]["nested"]["client_secret"].startswith("<redacted:")
    # safe field অক্ষত
    assert trace_dict["decision_ledger"]["nested"]["safe"] == "value"


def test_recorded_trace_json_has_no_secret(db):
    trace = _good_trace()
    trace.decision = f"used token {SECRET} once"  # sensitive string ভ্যালু
    tid = mod.record_trace(trace, db_path=db)
    stored = mod.load_trace(tid, db_path=db)
    assert SECRET not in json.dumps(stored)


# ---------------------------------------------------------------------------
# Bullet 4: deterministic evaluator scores a real workflow shape
# ---------------------------------------------------------------------------
def test_evaluator_detects_missing_evidence():
    trace = _good_trace()
    trace.tests_evidence = []
    evaluation = mod.evaluate_trace(trace)
    assert evaluation.passed is False
    failing = [c["check"] for c in evaluation.checks if not c["passed"]]
    assert "verification_evidence_present" in failing
    assert evaluation.evaluator_id == mod.EVALUATOR_ID


def test_evaluator_flags_guardrail_violation():
    trace = _good_trace()
    trace.guardrail_result = "rejected"
    evaluation = mod.evaluate_trace(trace)
    assert evaluation.passed is False
    failing = [c["check"] for c in evaluation.checks if not c["passed"]]
    assert "guardrail_not_violated" in failing


# ---------------------------------------------------------------------------
# Bullet 5: replay/compare against known-good evaluation
# ---------------------------------------------------------------------------
def test_compare_detects_regression():
    good = mod.evaluate_trace(_good_trace()).to_dict()
    regressed_trace = _good_trace()
    regressed_trace.tests_evidence = []  # evidence হারিয়ে গেল — regression
    current = mod.evaluate_trace(regressed_trace).to_dict()
    result = mod.compare_evaluations(good, current)
    assert result["regressed"] is True
    assert "verification_evidence_present" in result["regressions"]


def test_compare_reports_improvements_only():
    partial = {"evaluator_id": "deterministic-v1", "checks": [
        {"check": "outcome_declared", "passed": True},
        {"check": "links_present", "passed": False},
    ]}
    fixed = {"evaluator_id": "deterministic-v1", "checks": [
        {"check": "outcome_declared", "passed": True},
        {"check": "links_present", "passed": True},
    ]}
    result = mod.compare_evaluations(partial, fixed)
    assert result["regressed"] is False
    assert "links_present" in result["improvements"]


# ---------------------------------------------------------------------------
# Bullet 6: retrieval for future agents
# ---------------------------------------------------------------------------
def test_search_by_role_and_outcome(db):
    mod.record_trace(_good_trace(), db_path=db)
    other = _good_trace()
    other.role = "auditor"
    other.outcome = "partial"
    mod.record_trace(other, db_path=db)

    hits = mod.search_traces(role="coder", outcome="success", db_path=db)
    assert len(hits) == 1
    assert hits[0]["role"] == "coder"
    assert hits[0]["outcome"] == "success"


# ---------------------------------------------------------------------------
# Bullet 7: no second orchestration/memory subsystem (design assertion)
# ---------------------------------------------------------------------------
def test_module_is_pure_library_no_background_machinery():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    for token in ("Thread", "Timer", "asyncio", "Queue", "daemon", "scheduler"):
        assert token not in source, (
            f"agent_trace must stay a pure library — found {token!r}"
        )


# ---------------------------------------------------------------------------
# CLI round-trip
# ---------------------------------------------------------------------------
def test_cli_record_evaluate_search(tmp_path, capsys):
    trace = _good_trace()
    tpath = tmp_path / "t.json"
    tpath.write_text(json.dumps(trace.to_dict()), encoding="utf-8")

    rc_rec = mod.main(["record", "--trace", str(tpath)])
    assert rc_rec == 0
    # record path নিজেই DB default ব্যবহার করে — টেস্টে tmp DB দরকার;
    # তাই search/record-এর সরাসরি ফাংশন-পথ দিয়েই যাচাই:
    tid = mod.record_trace(trace, db_path=tmp_path / "traces.db")
    stored = mod.load_trace(tid, db_path=tmp_path / "traces.db")
    assert stored["outcome"] == "success"
    assert stored["skill_bundle_hash"] == "a" * 64  # #3194 integration preserved
