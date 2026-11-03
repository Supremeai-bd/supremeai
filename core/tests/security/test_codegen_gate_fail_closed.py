"""Issue #704 + #682 regression: in-process codegen exec must fail-closed by default.

``services.tool_forge`` (issue #704),
``tools.code.safe_executor.run_restricted`` and ``core.skill_manager``
DB-skill loading (issue #682) execute model-generated or DB-stored Python via
in-process ``exec()``. Restricted builtins are not a security boundary, so
with no ``SUPREMEAI_ALLOW_INPROCESS_CODEGEN`` env var (the production/staging
default) nothing may execute:

- the tool forge raises its existing ``ToolForgeError``,
- the safe executor returns its existing ``(False, error_message)`` tuple,
- the skill manager raises its existing ``ValueError`` without exec'ing the
  DB-stored code.
"""

import json
from unittest.mock import AsyncMock

import pytest

from core.security.codegen_gate import ALLOW_INPROCESS_CODEGEN_ENV
from core.skill_manager import SkillManager
from services.tool_forge import ToolForgeError, ToolForgeService, ToolSpec
from tools.code.safe_executor import run_restricted


def test_tool_forge_fail_closed_by_default(monkeypatch):
    """No env var -> forged tool is registered but exec raises ToolForgeError."""
    monkeypatch.delenv(ALLOW_INPROCESS_CODEGEN_ENV, raising=False)
    service = ToolForgeService()
    spec = ToolSpec(name="adder", description="Adds two numbers")
    tool = service.forge_tool(
        spec,
        "def adder(a, b):\n    raise RuntimeError('executed while gate is off')\n",
    )
    assert tool.is_safe is True

    with pytest.raises(ToolForgeError, match=ALLOW_INPROCESS_CODEGEN_ENV):
        service.execute_tool(tool, {"a": 1, "b": 2})


def test_tool_forge_opt_in_executes(monkeypatch):
    """Explicit local-dev opt-in keeps the restricted exec path working."""
    monkeypatch.setenv(ALLOW_INPROCESS_CODEGEN_ENV, "true")
    service = ToolForgeService()
    spec = ToolSpec(name="adder", description="Adds two numbers")
    tool = service.forge_tool(spec, "def adder(a, b):\n    return a + b\n")

    assert service.execute_tool(tool, {"a": 2, "b": 3}) == 5


# ---------------------------------------------------------------------------
# Issue #682: tools.code.safe_executor.run_restricted
# ---------------------------------------------------------------------------


def test_safe_executor_fail_closed_by_default(monkeypatch):
    """No env var -> dynamically supplied code is NOT executed.

    The call site's existing ``(False, error_message)`` convention is returned
    with a structured denial; nothing is compiled or run.
    """
    monkeypatch.delenv(ALLOW_INPROCESS_CODEGEN_ENV, raising=False)

    ok, result = run_restricted("result = 2 + 2")

    assert ok is False
    assert isinstance(result, str)
    assert ALLOW_INPROCESS_CODEGEN_ENV in result


def test_safe_executor_opt_in_executes(monkeypatch):
    """Explicit local-dev opt-in keeps the restricted exec path working."""
    monkeypatch.setenv(ALLOW_INPROCESS_CODEGEN_ENV, "true")

    ok, result = run_restricted("result = 2 + 2")

    assert ok is True
    assert result["result"] == 4


# ---------------------------------------------------------------------------
# Issue #682: core.skill_manager DB-skill exec
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_skill_manager_db_exec_fail_closed_by_default(monkeypatch):
    """No env var -> DB-stored skill code is NOT exec'd (existing ValueError)."""
    monkeypatch.delenv(ALLOW_INPROCESS_CODEGEN_ENV, raising=False)
    mgr = SkillManager()

    monkeypatch.setattr(
        "tools.mcp.mcp_supabase.supabase_execute_sql",
        AsyncMock(
            return_value=json.dumps(
                {
                    "rows": [
                        {"code": ("raise RuntimeError('skill code executed while gate is off')")}
                    ]
                }
            )
        ),
        raising=False,
    )
    monkeypatch.setattr("core.skill_manager.run_sandbox_ast_check", lambda _: True, raising=False)

    with pytest.raises(ValueError, match=ALLOW_INPROCESS_CODEGEN_ENV):
        await mgr.get_skill("gated_skill")
