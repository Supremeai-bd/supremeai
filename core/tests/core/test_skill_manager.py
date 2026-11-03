import json
from unittest.mock import AsyncMock

import pytest

from core.security.codegen_gate import ALLOW_INPROCESS_CODEGEN_ENV
from core.skill_manager import SkillManager


@pytest.mark.anyio
async def test_skill_manager_blocks_unsafe_code(monkeypatch):
    mgr = SkillManager()

    unsafe_code = (
        "import os\n"
        "class X(BaseSkill):\n"
        "    name='x'\n"
        "    async def run(self, **kwargs):\n"
        "        return os.getcwd()\n"
    )

    # Patch the local import used inside get_skill
    monkeypatch.setattr(
        "tools.mcp.mcp_supabase.supabase_execute_sql",
        AsyncMock(return_value=json.dumps({"rows": [{"code": unsafe_code}]})),
        raising=False,
    )

    def _raise(_):
        raise Exception("blocked")

    monkeypatch.setattr("core.skill_manager.run_sandbox_ast_check", _raise, raising=False)
    # Issue #682: opt in so this test keeps exercising the AST-vetting gate
    # (gate 1) instead of being short-circuited by the new fail-closed gate 0.
    monkeypatch.setenv(ALLOW_INPROCESS_CODEGEN_ENV, "true")

    with pytest.raises(ValueError):
        await mgr.get_skill("skill_x")


@pytest.mark.anyio
async def test_skill_manager_loads_safe_code_from_db(monkeypatch):
    mgr = SkillManager()

    safe_code = (
        "\n"
        "class MySkill(BaseSkill):\n"
        "    name = 'skill_y'\n"
        "    async def run(self, **kwargs):\n"
        "        return {'ok': True}\n"
    )

    monkeypatch.setattr(
        "tools.mcp.mcp_supabase.supabase_execute_sql",
        AsyncMock(return_value=json.dumps({"rows": [{"code": safe_code}]})),
        raising=False,
    )
    monkeypatch.setattr("core.skill_manager.run_sandbox_ast_check", lambda _: True, raising=False)
    # Issue #682: in-process skill exec is fail-closed by default; this coverage
    # test exercises the explicitly-enabled (local dev) path.
    monkeypatch.setenv(ALLOW_INPROCESS_CODEGEN_ENV, "true")

    skill = await mgr.get_skill("skill_y")
    assert skill is not None
    assert getattr(skill, "name", None) == "skill_y"


@pytest.mark.anyio
async def test_skill_manager_db_miss_uses_mcp_discovery_generic_tool(monkeypatch):
    mgr = SkillManager()

    monkeypatch.setattr(
        "tools.mcp.mcp_supabase.supabase_execute_sql",
        AsyncMock(return_value=json.dumps({"rows": []})),
        raising=False,
    )
    monkeypatch.setattr("core.skill_manager.run_sandbox_ast_check", lambda _: True, raising=False)
    monkeypatch.setattr(mgr.mcp_client, "discover_tools", AsyncMock(return_value=["generic_tool"]))

    with pytest.raises(ValueError):
        await mgr.get_skill("unknown_skill")
