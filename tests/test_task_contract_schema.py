# বাংলা মন্তব্য: #3088 §1/§5/§8 — canonical task-contract schema টেস্ট।
"""task_contract_schema.py — envelope validation, contract-hash provenance, outputs।"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "agents"))

from task_contract_schema import (  # noqa: E402
    ADMIN_GATE_STATUSES,
    ENVELOPE_SECTIONS,
    PRIORITIES,
    STANDARD_OUTPUTS,
    TASK_CONTRACT_VERSION,
    TASK_TYPES,
    AdminGate,
    TaskContract,
    contract_from_issue,
)


def _valid_contract(**overrides) -> TaskContract:
    base = dict(
        task_id="task-issue-3088", issue=3088, task_type="IMPLEMENT",
        group="governance", priority="P1", objective="canonical model",
        touching_files=["scripts/agents/task_contract_schema.py"],
    )
    base.update(overrides)
    return TaskContract(**base)


# ── envelope চুক্তি (#3088 §1) ────────────────────────────────────────────────

def test_valid_contract_passes_validation():
    assert _valid_contract().validate() == []


def test_task_types_and_priorities_enums():
    assert "ADMIN_DECISION" in TASK_TYPES and "FIX_CI" in TASK_TYPES
    assert PRIORITIES == ("P0", "P1", "P2", "P3")
    assert set(STANDARD_OUTPUTS.keys()) == set(TASK_TYPES)
    assert STANDARD_OUTPUTS["FIX_CI"] == ["Failure", "Root Cause", "Minimal Fix", "Rerun", "Evidence"]


def test_validation_catches_schema_violations():
    errors = _valid_contract(
        task_type="INVALID", priority="PX", group="", sequence=0,
        predecessor=9999, objective="  ",
    ).validate()
    # বাংলা মন্তব্য: প্রতিটি GUARD-ভাঙার আলাদা বার্তা — agent-এর সংশোধন-পথ স্পষ্ট।
    assert any("task_type" in e for e in errors)
    assert any("priority" in e for e in errors)
    assert any("group" in e for e in errors)
    assert any("sequence" in e for e in errors)
    assert any("predecessor" in e for e in errors)
    assert any("objective" in e for e in errors)


def test_to_dict_includes_standard_output_steps():
    d = _valid_contract(task_type="AUDIT").to_dict()
    assert d["standard_output_steps"] == STANDARD_OUTPUTS["AUDIT"]
    assert d["version"] == TASK_CONTRACT_VERSION


def test_roundtrip_from_dict():
    c = _valid_contract(admin_gate=AdminGate(required=True, status="WAITING"))
    clone = TaskContract.from_dict(c.to_dict())
    assert clone.contract_hash() == c.contract_hash()
    assert clone.admin_gate.status == "WAITING"


# ── provenance-safe approval (#3088 §5) ──────────────────────────────────────

def test_contract_hash_changes_when_work_definition_changes():
    c1 = _valid_contract()
    c2 = _valid_contract(objective="different objective")
    assert c1.contract_hash() != c2.contract_hash()


def test_contract_hash_stable_across_runs():
    assert _valid_contract().contract_hash() == _valid_contract().contract_hash()


def test_approved_work_requires_identity_and_hash():
    gate = AdminGate(required=True, status="APPROVED")  # provenance বাদ
    errors = _valid_contract(admin_gate=gate).validate()
    assert any("approved_by" in e for e in errors)
    assert any("contract_hash_at_approval" in e for e in errors)


def test_is_approved_for_work_binding():
    # বাংলা মন্তব্য: approval চুক্তি-hash-এ বাঁধা — চুক্তি বদলালে approval invalid।
    c = _valid_contract()
    good_gate = AdminGate(required=True, status="APPROVED",
                          approved_by="admin", contract_hash_at_approval=c.contract_hash())
    assert _valid_contract(admin_gate=good_gate).is_approved_for_work()
    stale_gate = AdminGate(required=True, status="APPROVED",
                           approved_by="admin", contract_hash_at_approval="deadbeef0000ffff")
    assert not _valid_contract(admin_gate=stale_gate).is_approved_for_work()
    assert not _valid_contract(admin_gate=AdminGate(required=True, status="WAITING")).is_approved_for_work()
    assert _valid_contract().is_approved_for_work()  # required=False → কাজ-যোগ্য


def test_admin_gate_status_enum():
    assert ADMIN_GATE_STATUSES == ("NOT_REQUIRED", "WAITING", "APPROVED", "REJECTED")


# ── issue→contract bridge + envelope (#3088 §8) ──────────────────────────────

def test_contract_from_issue_infers_type_from_title():
    assert contract_from_issue(1, "fix(ci): broken gate", [], "pipeline").task_type == "FIX_CI"
    assert contract_from_issue(1, "feat(x): new thing", [], "product").task_type == "IMPLEMENT"
    assert contract_from_issue(1, "audit(q): deep look", [], "governance").task_type == "AUDIT"
    # gate:admin-approval লেবেল → ADMIN_DECISION lane
    c = contract_from_issue(1, "chore(security): rotate keys", ["gate:admin-approval"], "security")
    assert c.task_type == "ADMIN_DECISION" and c.admin_gate.required and c.admin_gate.status == "WAITING"


def test_task_id_deterministic_per_issue():
    a = contract_from_issue(42, "t", [], "pipeline")
    b = contract_from_issue(42, "t", [], "pipeline")
    assert a.task_id == b.task_id == "task-issue-42"


def test_render_envelope_contains_all_sections():
    env = _valid_contract().render_envelope()
    assert env.startswith(ENVELOPE_SECTIONS[0])
    for key in ("GROUP:", "PRIORITY:", "SCOPE:", "ADMIN GATE:", "STOP CONDITIONS:", "OUTPUT FORMAT:"):
        assert key in env, f"envelope missing {key}"
