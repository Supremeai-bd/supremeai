"""#3194 skill_bundle generator tests — verification contract coverage.

# বাংলা মন্তব্য: প্রতিটি টেস্ট #3194 verification contract-এর একটি বুলেট
# প্রমাণ করে — determinism, mandatory-rule injection, version/hash metadata,
# decision-ledger stamping, DB-driven bundle mutation (static docs untouched)।
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "agents" / "skill_bundle.py"


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location("skill_bundle_under_test", SCRIPT_PATH)
    assert spec and spec.loader, "skill_bundle module spec load failed"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mod = _load_module()


AGENT_RULES_FIXTURE = """# SupremeAI — AGENT_RULES.md (test fixture)

# 1. Universal Agent Contract

## U1 — Scope
Stay in scope. (fixture)

## U2 — Truth & Evidence
Evidence required. (fixture)

# 2. Non-Negotiable Engineering Policies

## P1 — Simple + Effective
Smallest solution wins. (fixture)

# 3. Role Policy Contracts

## Coder
Coder role policy body. (fixture)

## Auditor
Auditor role policy body. (fixture)
"""

RULES_YML_FIXTURE = """
security:
  rule_010:
    title: "No Hardcoded Secrets"
    description: "Secrets must come from the vault."
    severity: BLOCK
    category: security
style:
  rule_020:
    title: "Naming"
    description: "Consistent naming."
    severity: WARN
    category: style
"""

AGENTS_MD_FIXTURE = "# SupremeAI — AGENTS.md (test fixture)\nentry contract body\n"


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """বাংলা মন্তব্য: canonical ফাইলগুলো tmp fixture-এ monkeypatch —
    টেস্ট সবসময় নিজের ডেটায় চলে, রিপোর বর্তমান ডকুমেন্টের ওপর নির্ভর করে না।"""
    rules_md = tmp_path / "AGENT_RULES.md"
    rules_md.write_text(AGENT_RULES_FIXTURE, encoding="utf-8")
    rules_yml = tmp_path / "rules.yml"
    rules_yml.write_text(RULES_YML_FIXTURE, encoding="utf-8")
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text(AGENTS_MD_FIXTURE, encoding="utf-8")
    db = tmp_path / "policy.db"

    monkeypatch.setattr(mod, "CANONICAL_FILES", {
        "agents_md": agents_md,
        "agent_rules_md": rules_md,
        "constitution_rules_yml": rules_yml,
    })
    return {"db": db, "agents_md": agents_md, "tmp": tmp_path}


def _seed(env: dict[str, Path]) -> dict:
    return mod.seed_from_canonical(db_path=env["db"])


def _db_arg(env: dict[str, Path]) -> list[str]:
    return ["--db", str(env["db"])]


def _rules(env: dict[str, Path]) -> dict[str, dict]:
    """DB-র সব latest rule পড়া — assertion সহায়ক।"""
    conn = sqlite3.connect(str(env["db"]))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT rule_id, version, scope, mandatory FROM policy_rules"
    ).fetchall()
    conn.close()
    return {r["rule_id"]: dict(r) for r in rows}


# ---------------------------------------------------------------------------
# Contract bullet 1+4: একই task + একই policy version → identical bundle
# ---------------------------------------------------------------------------
def test_generation_is_deterministic(env):
    _seed(env)
    b1 = mod.generate_bundle("coder", "3194", "coding", db_path=env["db"])
    b2 = mod.generate_bundle("coder", "3194", "coding", db_path=env["db"])
    assert b1["content_hash"] == b2["content_hash"]
    # generated_at আলাদা হতে পারে (envelope metadata) কিন্তু payload hash এক হবে
    assert b1["rules"] == b2["rules"]


# ---------------------------------------------------------------------------
# Contract bullet 2: mandatory global rules cannot be omitted by filtering
# ---------------------------------------------------------------------------
def test_mandatory_rules_always_injected_and_foreign_roles_excluded(env):
    _seed(env)
    coder_bundle = mod.generate_bundle("coder", "100", db_path=env["db"])
    ids = {r["rule_id"] for r in coder_bundle["rules"]}

    # mandatory: U1, U2, P1 + constitution BLOCK rule_010 — সব থাকতে হবে
    for required in ("U1", "U2", "P1", "constitution:security:rule_010"):
        assert required in ids, f"mandatory rule {required} omitted — contract violation"
    # coder role rule থাকবে
    assert "role:coder" in ids
    # অন্য role-এর rule ও WARN constitution rule বাদ যাবে
    assert "role:auditor" not in ids
    assert "constitution:style:rule_020" not in ids

    auditor_bundle = mod.generate_bundle("auditor", "100", db_path=env["db"])
    auditor_ids = {r["rule_id"] for r in auditor_bundle["rules"]}
    # mandatory সেট অপরিবর্তিত — role filter শুধু non-mandatory বদলায়
    for required in ("U1", "U2", "P1", "constitution:security:rule_010"):
        assert required in auditor_ids
    assert "role:auditor" in auditor_ids
    assert "role:coder" not in auditor_ids


def test_task_scoped_rules_injected_only_for_matching_task_type(env):
    _seed(env)
    # task-scoped rule admin দিয়ে যোগ করা (DB-driven, static doc নয়)
    conn = sqlite3.connect(str(env["db"]))
    conn.execute(
        "INSERT INTO policy_rules (rule_id, version, scope, category, title, body,"
        " mandatory, superseded, created_at, source)"
        " VALUES ('task:deploy-check', 1, 'task:deploy', 'task', 'Deploy gate',"
        " 'Verify deploy health.', 0, 0, '2026-01-01T00:00:00Z', 'admin')"
    )
    conn.commit()
    conn.close()

    deploy_bundle = mod.generate_bundle("coder", "200", "deploy", db_path=env["db"])
    assert "task:deploy-check" in {r["rule_id"] for r in deploy_bundle["rules"]}

    coding_bundle = mod.generate_bundle("coder", "200", "coding", db_path=env["db"])
    assert "task:deploy-check" not in {r["rule_id"] for r in coding_bundle["rules"]}


# ---------------------------------------------------------------------------
# Contract bullet 3: bundle contains policy versions + content hash + AGENTS.md pin
# ---------------------------------------------------------------------------
def test_bundle_metadata_versions_and_hash_present(env):
    _seed(env)
    bundle = mod.generate_bundle("coder", "3194", "coding", db_path=env["db"])
    assert bundle["content_hash"] and len(bundle["content_hash"]) == 64
    assert bundle["bundle_schema"] == mod.BUNDLE_SCHEMA_VERSION
    assert bundle["policy_versions"], "policy_versions map must not be empty"
    # প্রতিটি selected rule-এর version map-এ থাকতে হবে
    for rule in bundle["rules"]:
        assert bundle["policy_versions"][rule["rule_id"]] == rule["version"]
    # AGENTS.md entry-contract pin
    import hashlib
    assert bundle["agents_md_sha256"] == hashlib.sha256(
        env["agents_md"].read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Contract bullet 5: decision JSON records bundle hash/version
# ---------------------------------------------------------------------------
def test_augment_decision_stamps_bundle_hash(env):
    _seed(env)
    bundle = mod.generate_bundle("coder", "3194", db_path=env["db"])
    decision = {"task": "3194", "agent": "coder-1", "result": "completed"}
    stamped = mod.augment_decision(decision, bundle)
    assert stamped["skill_bundle"]["content_hash"] == bundle["content_hash"]
    assert stamped["skill_bundle"]["bundle_schema"] == bundle["bundle_schema"]
    assert stamped["skill_bundle"]["policy_versions"] == bundle["policy_versions"]
    # মূল decision ক্ষেত্র অক্ষত
    assert stamped["task"] == "3194"
    # CLI stamp পথেও একই ফল (JSON round-trip)
    bpath = env["tmp"] / "b.json"
    dpath = env["tmp"] / "d.json"
    bpath.write_text(json.dumps(bundle), encoding="utf-8")
    dpath.write_text(json.dumps(decision), encoding="utf-8")
    assert mod.main(["stamp", "--bundle", str(bpath), "--decision", str(dpath)]) == 0
    assert json.loads(dpath.read_text())["skill_bundle"]["content_hash"] == \
        bundle["content_hash"]


# ---------------------------------------------------------------------------
# Contract bullet 6: DB rule update → new bundle, static documents untouched
# ---------------------------------------------------------------------------
def test_db_rule_version_bump_changes_bundle_without_touching_files(env):
    _seed(env)
    before = mod.generate_bundle("coder", "3194", db_path=env["db"])

    # admin policy write — rule-upsert CLI (guard সহ)
    rc = mod.main([
        "rule-upsert", "--rule-id", "U1", "--scope", "universal",
        "--category", "universal", "--title", "Scope",
        "--body", "Scope narrowed by admin (v2).", "--mandatory",
        "--confirm-policy-write", *_db_arg(env),
    ])
    assert rc == 0

    after = mod.generate_bundle("coder", "3194", db_path=env["db"])
    assert after["content_hash"] != before["content_hash"]
    assert after["policy_versions"]["U1"] == 2

    bodies = {r["rule_id"]: r["body"] for r in after["rules"]}
    assert bodies["U1"] == "Scope narrowed by admin (v2)."

    # স্ট্যাটিক ফাইল অক্ষত — fixture monkeypatched ফাইলের content অপরিবর্তিত
    assert "Stay in scope" in env["tmp"].joinpath("AGENT_RULES.md").read_text()

    # পুরনো version superseded — latest query-তে শুধু v2
    rules = _rules(env)
    assert rules["U1"]["version"] == 2


def test_policy_write_guard_refuses_without_confirm(env):
    _seed(env)
    rc = mod.main([
        "rule-upsert", "--rule-id", "UX", "--title", "t", "--body", "b",
        *_db_arg(env),
    ])
    assert rc == 2  # refused — agent নিজে থেকে policy বদলাতে পারে না


# ---------------------------------------------------------------------------
# Seed idempotency + tamper detection
# ---------------------------------------------------------------------------
def test_seed_is_idempotent_and_force_creates_new_version(env):
    first = _seed(env)
    second = _seed(env)
    # দ্বিতীয় seed-এ নতুন কিছু যোগ/আপডেট হয় না (idempotent bootstrap)
    assert second["added"] == 0 and second["updated"] == 0
    assert first["added"] == 7  # fixture-এ ৭টি canonical rule

    # canonical fixture বদলে force re-seed → নতুন version
    rules_md = env["tmp"] / "AGENT_RULES.md"
    rules_md.write_text(AGENT_RULES_FIXTURE.replace("Stay in scope. (fixture)",
                                                    "Scope tightened. (v2)"),
                        encoding="utf-8")
    forced = mod.seed_from_canonical(db_path=env["db"], force=True)
    assert forced["updated"] >= 1
    rules = _rules(env)
    assert rules["U1"]["version"] == 2


def test_verify_bundle_detects_tampering(env):
    _seed(env)
    bundle = mod.generate_bundle("coder", "3194", db_path=env["db"])
    assert mod.verify_bundle(bundle)["valid"] is True

    tampered = json.loads(json.dumps(bundle))
    tampered["rules"][0]["body"] = "fabricated rule body — মিথ্যা প্রমাণ"
    verdict = mod.verify_bundle(tampered)
    assert verdict["valid"] is False
    assert verdict["expected_hash"] != verdict["recorded_hash"]


# ---------------------------------------------------------------------------
# Contract bullet 7 (design): no second orchestration engine — pure functions,
# কোনো thread/daemon/scheduler machinery module-এ নেই।
# ---------------------------------------------------------------------------
def test_module_has_no_orchestration_machinery():
    forbidden = ("Thread", "Timer", "asyncio", "scheduler", "daemon", "Queue")
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    for token in forbidden:
        assert token not in source, (
            f"skill_bundle must stay a pure generator — found orchestration token "
            f"{token!r} (P1: no second orchestration engine)"
        )


# ---------------------------------------------------------------------------
# CLI generate path — end-to-end JSON output
# ---------------------------------------------------------------------------
def test_cli_generate_outputs_valid_bundle(env, tmp_path, capsys):
    _seed(env)
    out = tmp_path / "bundles" / "b.json"
    rc = mod.main(["generate", "--role", "coder", "--task-id", "3194",
                   "--task-type", "coding", "--out", str(out), *_db_arg(env)])
    assert rc == 0
    bundle = json.loads(out.read_text(encoding="utf-8"))
    assert bundle["role"] == "coder"
    assert bundle["task_id"] == "3194"
    assert mod.verify_bundle(bundle)["valid"] is True
