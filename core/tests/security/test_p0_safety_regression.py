"""P0 safety regression tests (Task 9-c2).

Covers the remaining P0 hardening shipped on top of core.degraded_mode:

1. ``sqlite_fallback_allowed`` policy matrix (production refuse / gate opt-in /
   dev allow, warn-exactly-once).
2. CheckpointManager creates NO SQLite file when the fallback is refused.
3. AutoSkillCreator fail-closed behaviour:
   - scanner crash / False / None verdicts all reject the candidate;
   - production + unresolvable store → PersistenceUnavailableError;
   - test env → explicit recording mock (writes captured, not silently lost).
4. fuzz_sandbox extended import ban list.
5. SkillRegistry.register_skill returns False on DB write failure.
6. SkillInstaller.install_dependencies dependency allowlist.
"""

import asyncio
import json
import os
import sys
import types
from unittest.mock import patch

import pytest

import core.config
import core.degraded_mode as degraded_mode
from core.degraded_mode import sqlite_fallback_allowed
from tools.code.fuzz_sandbox import SecurityError, run_sandbox_ast_check

# The root-level ``skills`` package lives outside backend/ — mirror the sys.path
# handling used by core/self_evolution/auto_skill_creator.py.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from skills.registry import SkillRegistry

from core.self_evolution import auto_skill_creator as asc
from core.self_evolution.auto_skill_creator import (
    MOCKED_SKILL_WRITES,
    AutoSkillCreator,
    PersistenceUnavailableError,
)
from skills.installer import ALLOWED_SKILL_DEPENDENCIES, SkillInstaller
from skills.installer import SecurityError as InstallerSecurityError

# ── helpers / fixtures ────────────────────────────────────────────────────────


def _production_env(monkeypatch):
    """Simulate production exactly like test_session_degradation_regression.py:
    settings.env is a static attribute read at instantiation, so patch it on the
    singleton; ENV=production additionally defeats is_test_context's pytest check.
    """
    monkeypatch.setattr(core.config.settings, "env", "production")
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("SUPABASE_ALLOW_DB_DEGRADATION", raising=False)
    monkeypatch.delenv("ALLOW_DB_DEGRADATION", raising=False)


def _test_env(monkeypatch):
    monkeypatch.setattr(core.config.settings, "env", "test")
    monkeypatch.setenv("ENV", "test")


@pytest.fixture(autouse=True)
def _reset_gate_warnings():
    """Keep the once-per-feature CRITICAL cache isolated between tests."""
    degraded_mode.reset_warned_features()
    yield
    degraded_mode.reset_warned_features()


@pytest.fixture
def _mocked_writes_guard():
    saved = list(MOCKED_SKILL_WRITES)
    yield
    MOCKED_SKILL_WRITES[:] = saved


# ── 1. sqlite_fallback_allowed policy matrix ────────────────────────────────--


def test_sqlite_fallback_production_no_gate_refused_and_warns_once(monkeypatch):
    _production_env(monkeypatch)

    calls: list[str] = []

    class _FakeLogger:
        def critical(self, msg, *args, **kwargs):
            calls.append(str(msg))

        def warning(self, msg, *args, **kwargs):
            calls.append("W:" + str(msg))

        def error(self, msg, *args, **kwargs):
            calls.append("E:" + str(msg))

        def info(self, msg, *args, **kwargs):
            pass

    monkeypatch.setattr(degraded_mode, "logger", _FakeLogger())

    assert sqlite_fallback_allowed("regression_feature") is False
    # Second call for the same feature must NOT re-log the CRITICAL.
    assert sqlite_fallback_allowed("regression_feature") is False
    criticals = [c for c in calls if not c.startswith(("W:", "E:"))]
    assert len(criticals) == 1
    assert "P0" in criticals[0]
    assert "SUPABASE_ALLOW_DB_DEGRADATION" in criticals[0]


def test_sqlite_fallback_production_gate_ignored_hard_fail(monkeypatch):
    """Wave 0.1 (issue #1224): the degradation flag no longer opens the SQLite
    escape hatch in production — the fallback stays refused + loudly warned,
    even when both the canonical flag and the legacy alias are set."""
    _production_env(monkeypatch)
    monkeypatch.setenv("SUPABASE_ALLOW_DB_DEGRADATION", "true")
    monkeypatch.setenv("ALLOW_DB_DEGRADATION", "true")  # legacy alias too

    calls: list[str] = []

    class _FakeLogger:
        def critical(self, msg, *args, **kwargs):
            calls.append(str(msg))

        def warning(self, msg, *args, **kwargs):
            pass

        def error(self, msg, *args, **kwargs):
            pass

        def info(self, msg, *args, **kwargs):
            pass

    monkeypatch.setattr(degraded_mode, "logger", _FakeLogger())

    assert sqlite_fallback_allowed("regression_feature_gate") is False
    # A different feature in the same production context is refused too.
    assert sqlite_fallback_allowed("regression_feature_gate_second") is False
    criticals = [c for c in calls if "P0" in c]
    assert criticals, "production refusal must fire the CRITICAL P0 warning"
    assert any("no longer permits SQLite fallback" in c for c in criticals)
    # The fail-closed variant must raise even with the flag set.
    from core.degraded_mode import SQLiteFallbackDisabledError, require_sqlite_allowed

    with pytest.raises(SQLiteFallbackDisabledError):
        require_sqlite_allowed("regression_feature_gate_raise")


def test_sqlite_fallback_dev_allowed(monkeypatch):
    monkeypatch.setattr(core.config.settings, "env", "development")
    monkeypatch.setenv("ENV", "development")
    monkeypatch.delenv("SUPABASE_ALLOW_DB_DEGRADATION", raising=False)
    assert sqlite_fallback_allowed("regression_feature_dev") is True


# ── 2. CheckpointManager creates no SQLite file when refused ────────────────--


def test_checkpoint_manager_production_no_gate_creates_no_db_file(monkeypatch, tmp_path):
    import tools.checkpoint_manager as checkpoint_mod

    _production_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(checkpoint_mod.pooled_pg, "is_available", lambda: False)
    monkeypatch.setattr(checkpoint_mod, "get_firestore_db", lambda *a, **k: None)

    manager = checkpoint_mod.CheckpointManager()

    assert manager.available is False
    assert manager.mode == "disabled"
    # The ephemeral checkpoints.db must NOT exist anywhere in the cwd tree.
    assert not (tmp_path / "checkpoints.db").exists()
    assert list(tmp_path.rglob("*.db")) == []


# ── 3. AutoSkillCreator fail-closed hardening ──────────────────────────────--


MOCK_AI_RESPONSE_JSON = {
    "code": "class SentimentAnalyzer:\n    async def execute(self, kwargs):\n        return {'sentiment': 'positive'}\n",
    "schema": {
        "metadata": {
            "name": "SentimentAnalyzer",
            "version": "1.0.0",
            "description": "Mocked sentiment analyzer.",
            "author": "supremeai_agent_id",
            "tags": [],
        },
        "interface": {
            "input_schema": {"type": "object"},
            "output_schema": {"type": "object"},
        },
        "execution": {
            "runtime": "python3.11",
            "entry_point": "main.execute",
            "dependencies": [],
            "timeout_seconds": 30,
        },
        "validation": {
            "tests": [
                {"input": {"text": "I love this!"}, "expected_output": {"sentiment": "positive"}}
            ],
            "security_level": "sandboxed",
        },
    },
}


def _make_creator(monkeypatch):
    """AutoSkillCreator with an unresolvable Firestore client (recording mock in test env)."""
    monkeypatch.setattr(asc, "_resolve_firestore_client", lambda: None)
    creator = AutoSkillCreator()
    # FitnessEngine writes a JSON telemetry file — neutralize for these tests.
    monkeypatch.setattr(creator.fitness_engine, "track_execution", lambda *a, **k: None)
    return creator


def _mock_llm(monkeypatch):
    import core.llm.llm_gateway as gateway_mod

    async def fake_acompletion(*args, **kwargs):
        return {"success": True, "text": json.dumps(MOCK_AI_RESPONSE_JSON)}

    monkeypatch.setattr(gateway_mod.llm_gateway, "acompletion", fake_acompletion)


def test_creator_scanner_crash_rejects_candidate(monkeypatch, _mocked_writes_guard):
    _test_env(monkeypatch)
    creator = _make_creator(monkeypatch)
    _mock_llm(monkeypatch)

    def _boom(code):
        raise RuntimeError("scanner exploded")

    monkeypatch.setattr(asc, "run_sandbox_ast_check", _boom)
    result = asyncio.run(
        creator.generate_and_deploy_skill(user_demand="d", skill_name="ScanCrashSkill")
    )

    assert result["success"] is False
    assert "Security Sandbox Violation" in result["error"]
    assert "fail-closed" in result["error"]
    # Nothing was persisted for the rejected candidate.
    assert len(MOCKED_SKILL_WRITES) == 0


def test_creator_scanner_false_verdict_rejects_candidate(monkeypatch, _mocked_writes_guard):
    _test_env(monkeypatch)
    creator = _make_creator(monkeypatch)
    _mock_llm(monkeypatch)
    monkeypatch.setattr(asc, "run_sandbox_ast_check", lambda code: False)

    result = asyncio.run(
        creator.generate_and_deploy_skill(user_demand="d", skill_name="ScanFalseSkill")
    )

    assert result["success"] is False
    assert "Security Sandbox Violation" in result["error"]
    assert "AST layout normalization" in result["error"]


def test_creator_scanner_none_verdict_rejects_candidate(monkeypatch, _mocked_writes_guard):
    _test_env(monkeypatch)
    creator = _make_creator(monkeypatch)
    _mock_llm(monkeypatch)
    monkeypatch.setattr(asc, "run_sandbox_ast_check", lambda code: None)

    result = asyncio.run(
        creator.generate_and_deploy_skill(user_demand="d", skill_name="ScanNoneSkill")
    )

    assert result["success"] is False
    # ANY verdict that is not exactly True must be rejected.
    assert "Security Sandbox Violation" in result["error"]
    assert "Unexpected scanner verdict" in result["error"]


def test_creator_production_db_unresolvable_raises_persistence_error(monkeypatch):
    _production_env(monkeypatch)
    monkeypatch.setattr(asc, "_resolve_firestore_client", lambda: None)

    with pytest.raises(PersistenceUnavailableError):
        AutoSkillCreator()


def test_creator_test_env_uses_recording_mock(monkeypatch, _mocked_writes_guard):
    _test_env(monkeypatch)
    monkeypatch.setattr(asc, "_resolve_firestore_client", lambda: None)

    before = len(MOCKED_SKILL_WRITES)
    creator = AutoSkillCreator()

    assert isinstance(creator.skills_ref, asc._RecordingMockRef)
    # Writes go through the explicit recording sink — never silently lost.
    creator.skills_ref.document("doc-1").set({"skill": "demo", "code": "x = 1"})

    assert len(MOCKED_SKILL_WRITES) == before + 1
    assert MOCKED_SKILL_WRITES[-1]["data"] == {"skill": "demo", "code": "x = 1"}


def test_creator_module_has_no_silent_mock_fallback():
    """The dummy scanner / MockRef classes must be gone from the module."""
    source_vars = vars(asc)
    assert "run_sandbox_ast_check" in source_vars  # hard import, real function
    assert asc.run_sandbox_ast_check is not None
    assert not any(name.startswith("MockRef") or name.startswith("MockDoc") for name in source_vars)


# ── 4. fuzz_sandbox extended import ban list ───────────────────────────────--


@pytest.mark.parametrize(
    "code",
    [
        "import requests",
        "import urllib.request",
        "import ctypes",
        "import pickle",
        "from http import client",
        "import importlib",
        "import runpy",
        "import marshal",
    ],
)
def test_fuzz_rejects_newly_banned_imports(code):
    with pytest.raises(SecurityError):
        run_sandbox_ast_check(code)


def test_fuzz_still_allows_safe_code():
    assert run_sandbox_ast_check("import json\nimport math\nresult = 1 + 2\n") is True
    assert run_sandbox_ast_check("x = 41 + 1\nprint_like = None\n") is True


# ── 5. SkillRegistry.register_skill returns False on DB failure ────────────--


def test_register_skill_returns_false_when_db_write_fails(monkeypatch, tmp_path):
    class _FakeDB:
        client = object()  # truthy — pretend Supabase is configured

        def upsert_db_skill(self, data):
            raise RuntimeError("simulated Supabase outage")

    fake_module = types.ModuleType("database.supabase_client")
    fake_module.db = _FakeDB()
    monkeypatch.setitem(sys.modules, "database.supabase_client", fake_module)
    monkeypatch.setenv("ENV", "test")  # avoid the ENV=local JSON fallback write

    registry = SkillRegistry(registry_path=str(tmp_path / "registry.json"))
    assert (
        registry.register_skill("reg_skill", "1.0.0", "desc", "/tmp/entry.py", dependencies=[])
        is False
    )


def test_register_skill_returns_true_when_db_write_succeeds(monkeypatch, tmp_path):
    class _FakeDB:
        client = object()

        def upsert_db_skill(self, data):
            return {"name": data["name"]}

    fake_module = types.ModuleType("database.supabase_client")
    fake_module.db = _FakeDB()
    monkeypatch.setitem(sys.modules, "database.supabase_client", fake_module)
    monkeypatch.setenv("ENV", "test")

    registry = SkillRegistry(registry_path=str(tmp_path / "registry.json"))
    assert (
        registry.register_skill("reg_skill_ok", "1.0.0", "desc", "/tmp/entry.py", dependencies=[])
        is True
    )


# ── 6. SkillInstaller.install_dependencies allowlist ───────────────────────--


@pytest.fixture
def installer(tmp_path):
    registry = SkillRegistry(registry_path=str(tmp_path / "registry.json"))
    return SkillInstaller(registry=registry, skills_dir=str(tmp_path / "dynamic"))


def test_install_dependencies_rejects_non_allowlisted(monkeypatch, installer):
    monkeypatch.delenv("SUPREMEAI_SKILL_DEPS_ENABLED", raising=False)
    spawned = {"count": 0}

    def _fake_run(*args, **kwargs):
        spawned["count"] += 1
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr("skills.installer.subprocess.run", _fake_run)

    with pytest.raises(InstallerSecurityError):
        installer.install_dependencies(["evil-package"])

    # SecurityError must fire BEFORE pip is ever spawned.
    assert spawned["count"] == 0


def test_install_dependencies_allows_allowlisted(monkeypatch, installer):
    monkeypatch.delenv("SUPREMEAI_SKILL_DEPS_ENABLED", raising=False)
    spawned = {"count": 0}

    def _fake_run(cmd, *args, **kwargs):
        spawned["count"] += 1
        # The full requirement is passed to pip; only the base name is allowlisted.
        assert cmd[-1].split("==")[0].split(">=")[0] == "httpx"
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr("skills.installer.subprocess.run", _fake_run)

    assert installer.install_dependencies(["httpx"]) is True
    assert spawned["count"] == 1
    # Version specifiers normalize to the allowlisted base name.
    assert installer.install_dependencies(["httpx>=0.24"]) is True


def test_allowed_skill_dependencies_covers_bundled_skills():
    assert {"httpx", "beautifulsoup4", "bs4", "pandas"} <= ALLOWED_SKILL_DEPENDENCIES
    assert "requests" not in ALLOWED_SKILL_DEPENDENCIES
