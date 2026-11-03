"""Tests for the MCP Policy Engine (backend/core/mcp_policy.py).

বাংলা মন্তব্য: Python mirror এর জন্য টেস্ট — TS risk.engine.ts এবং policy.engine.ts
এর সাথে consistency নিশ্চিত করে।

Constitution Compliance:
  - Law #16 (Verify Before Trust): policy engine logic verified before deployment
"""

import importlib.util
import sys
from pathlib import Path

# ── Fixtures ──────────────────────────────────────────────────────────

# Resolve project root from this test file location (works regardless of cwd)
# tests/core/test_mcp_policy.py → tests/core/ → tests/ → backend/ → project root
TEST_FILE = Path(__file__).resolve()
PROJECT_ROOT = TEST_FILE.parents[3]
POLICY_PATH = PROJECT_ROOT / "backend" / "core" / "mcp_policy.py"
AUDIT_PATH = PROJECT_ROOT / "backend" / "core" / "mcp_audit.py"


def _load_policy_module():
    """Load mcp_policy without triggering full backend init."""
    spec = importlib.util.spec_from_file_location("core.mcp_policy", str(POLICY_PATH))
    mod = importlib.util.module_from_spec(spec)
    # Prevent full backend init by stubbing logging_config
    sys.modules.setdefault("core.logging_config", type(sys)("core.logging_config"))
    spec.loader.exec_module(mod)
    return mod


# ── Risk Level Tests ──────────────────────────────────────────────────


def test_read_only_tools_are_r0():
    mod = _load_policy_module()
    read_only_tools = [
        "read_graph",
        "search_nodes",
        "open_nodes",
        "search_semantic",
        "get_similar_tasks",
        "get_recent_episodes",
        "build_context",
        "get_session_stats",
        "recall_facts",
        "search_learned_facts",
        "get_skill_dependencies",
        "find_optimal_learning_path",
        "get_render_deploy_preflight",
        "get_render_account_status",
    ]
    for tool in read_only_tools:
        decision, risk = mod.evaluate_tool(tool)
        assert risk == "R0", f"{tool} should be R0, got {risk}"
        assert decision == "ALLOW", f"{tool} should be ALLOW, got {decision}"


def test_safe_writes_are_r1():
    mod = _load_policy_module()
    safe_write_tools = [
        "create_entities",
        "create_relations",
        "add_observations",
        "store_document",
        "ingest_document_rag",
        "record_task",
        "remember_fact",
        "save_learned_fact",
    ]
    for tool in safe_write_tools:
        decision, risk = mod.evaluate_tool(tool)
        assert risk == "R1", f"{tool} should be R1, got {risk}"
        assert decision == "ALLOW", f"{tool} should be ALLOW, got {decision}"


def test_destructive_tools_require_approval():
    mod = _load_policy_module()
    destructive_tools = [
        "delete_entities",
        "delete_observations",
        "delete_relations",
        "clear_session",
        "refresh_render_account_status",
    ]
    for tool in destructive_tools:
        decision, risk = mod.evaluate_tool(tool)
        assert risk == "R2", f"{tool} should be R2, got {risk}"
        assert decision == "REQUIRE_APPROVAL", f"{tool} should require approval, got {decision}"


def test_unknown_tool_falls_back_to_r3():
    mod = _load_policy_module()
    decision, risk = mod.evaluate_tool("totally_unknown_tool")
    assert risk == "R3"
    assert decision == "REQUIRE_APPROVAL"


def test_is_tool_allowed_helper():
    mod = _load_policy_module()
    assert mod.is_tool_allowed("read_graph") is True
    assert mod.is_tool_allowed("create_entities") is True
    assert mod.is_tool_allowed("delete_entities") is False
    assert mod.is_tool_allowed("unknown_tool") is False


# ── Policy Engine Direct Tests ────────────────────────────────────────


def test_risk_engine_render_rules():
    mod = _load_policy_module()
    engine = mod.RiskEngine()
    assert engine.evaluate("render", "deploy") == "R2"
    assert engine.evaluate("render", "restart") == "R2"
    assert engine.evaluate("render", "suspend") == "R4"
    assert engine.evaluate("render", "delete") == "R6"


def test_risk_engine_supabase_rules():
    mod = _load_policy_module()
    engine = mod.RiskEngine()
    assert engine.evaluate("supabase", "restart") == "R3"
    assert engine.evaluate("supabase", "drop_db") == "R6"
    assert engine.evaluate("supabase", "insert") == "R2"


def test_risk_engine_redis_rules():
    mod = _load_policy_module()
    engine = mod.RiskEngine()
    assert engine.evaluate("redis", "flushall") == "R5"
    assert engine.evaluate("redis", "set") == "R1"
    assert engine.evaluate("redis", "del") == "R2"


def test_risk_engine_github_rules():
    mod = _load_policy_module()
    engine = mod.RiskEngine()
    assert engine.evaluate("github", "push") == "R2"
    assert engine.evaluate("github", "delete_repo") == "R6"


def test_policy_engine_decision_boundaries():
    mod = _load_policy_module()
    engine = mod.PolicyEngine()
    # R0, R1 → ALLOW
    assert engine.decide("R0") == "ALLOW"
    assert engine.decide("R1") == "ALLOW"
    # R2-R5 → REQUIRE_APPROVAL
    assert engine.decide("R2") == "REQUIRE_APPROVAL"
    assert engine.decide("R3") == "REQUIRE_APPROVAL"
    assert engine.decide("R4") == "REQUIRE_APPROVAL"
    assert engine.decide("R5") == "REQUIRE_APPROVAL"
    # R6 → REQUIRE_APPROVAL (strict HITL)
    assert engine.decide("R6") == "REQUIRE_APPROVAL"


def test_singleton_engine():
    mod = _load_policy_module()
    engine1 = mod.get_policy_engine()
    engine2 = mod.get_policy_engine()
    assert engine1 is engine2


# ── Schema-Driven SSoT Tests (#2429) ──────────────────────────────────


def test_schema_snapshot_matches_canonical_schema():
    """Embedded Python snapshot অবশ্যই canonical config/mcp_policy_schema.json-এর হুবহু প্রতিচ্ছবি।

    বাংলা মন্তব্য: এটি scripts/ci/check_mcp_policy_parity.py-র ধাপ-১ (generator
    --check) এর ইন-টেস্ট সংস্করণ — টেস্ট চালানোর সময়েও snapshot drift ধরা পড়বে।
    """
    import json

    snapshot_mod = _load_policy_module()
    schema_path = PROJECT_ROOT / "config" / "mcp_policy_schema.json"
    canonical = json.loads(schema_path.read_text(encoding="utf-8"))
    generated = snapshot_mod.schema_info()
    assert generated["schema_version"] == canonical["schema_version"]
    assert sorted(generated["providers"]) == sorted(canonical["providers"].keys())
    assert generated["tools"] == len(canonical["tool_provider_action"])


def test_provider_default_risk_semantics():
    """Per-provider default risk — schema-র `_default` কী উভয় ইঞ্জিনে একই আচরণ দেয়।

    বাংলা মন্তব্য: আগে Python-এ memory/mesh-এর unknown action R0 হতো কিন্তু
    TS-এ R3 (গ্লোবাল default) — এই drift-ই #2429 দূর করেছে।
    """
    mod = _load_policy_module()
    engine = mod.RiskEngine()
    # memory/mesh/mcp_tools-এর provider-default R0 (platform-safe operations)।
    assert engine.evaluate("memory", "brand_new_memory_action") == "R0"
    assert engine.evaluate("mesh", "brand_new_mesh_op") == "R0"
    assert engine.evaluate("mcp_tools", "brand_new_tool_query") == "R0"
    # agent_tools-এর provider-default R3 (fail-closed — privileged category)।
    assert engine.evaluate("agent_tools", "brand_new_agent_action") == "R3"
    # Unknown provider → গ্লোবাল default R3।
    assert engine.evaluate("mystery_provider", "mystery_action") == "R3"


def test_read_only_keyword_semantics():
    """Read-only keyword সেট (verify, search, get, query, fetch, open সহ) উভয় ইঞ্জিনে অভিন্ন।"""
    mod = _load_policy_module()
    engine = mod.RiskEngine()
    for keyword in (
        "verify",
        "search",
        "get",
        "query",
        "fetch",
        "open",
        "read",
        "list",
        "summary",
        "status",
    ):
        risk = engine.evaluate("any_provider", f"prefix_{keyword}_suffix")
        assert risk == "R0", f"keyword '{keyword}' action should be R0, got {risk}"
    # system/health provider সর্বদা R0।
    assert engine.evaluate("system", "arbitrary_write") == "R0"
    assert engine.evaluate("health", "full_sweep") == "R0"


def test_new_python_providers_in_schema():
    """#2429-র মূল পয়েন্ট: Python-এর ৪টি নতুন provider এখন TS টাওয়ারসহ সব ইঞ্জিনে আছে।"""
    mod = _load_policy_module()
    engine = mod.RiskEngine()
    assert engine.evaluate("agent_tools", "execute") == "R5"
    assert engine.evaluate("agent_tools", "execute_code") == "R5"
    assert engine.evaluate("agent_tools", "verify") == "R0"
    assert engine.evaluate("memory", "delete") == "R2"
    assert engine.evaluate("mesh", "dispatch") == "R1"
    assert engine.evaluate("mesh", "send") == "R1"
    assert engine.evaluate("mcp_tools", "refresh") == "R2"


def test_decision_matrix_fail_closed():
    """Unknown risk level → fail-closed REQUIRE_APPROVAL (কখনো auto-allow নয়)।"""
    mod = _load_policy_module()
    engine = mod.PolicyEngine()
    assert engine.decide("R9") == "REQUIRE_APPROVAL"  # type: ignore[arg-type]
    assert engine.decide("") == "REQUIRE_APPROVAL"  # type: ignore[arg-type]


def test_schema_info_observability():
    """Law #19: চলমান schema সংস্করণ শনাক্তযোগ্য (version + hash + provider তালিকা)।"""
    mod = _load_policy_module()
    info = mod.schema_info()
    assert "schema_version" in info and "schema_hash" in info
    assert "render" in info["providers"] and "mesh" in info["providers"]
    assert info["tools"] > 0
