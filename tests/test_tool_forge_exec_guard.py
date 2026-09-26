"""#1589 — ToolForge exec-path hardening tests.

Covers (gate-on local-dev mode only, since gate is fail-closed by default):
- default gate stays OFF: exec refused with the structured error
- timeout budget is actually enforced (infinite loop -> ToolForgeError fast)
- dunder-globals staging attempt -> SecurityViolationError
- benign tool still executes and returns its result
"""

from __future__ import annotations

import pytest

import services.tool_forge as tf
from services.tool_forge import (
    SecurityViolationError,
    ToolForgeError,
    ToolForgeService,
    ToolSpec,
)


@pytest.fixture()
def service():
    return ToolForgeService()


@pytest.fixture()
def gate_on(monkeypatch):
    monkeypatch.setattr(tf, "inprocess_codegen_enabled", lambda: True)


def _forge(service: ToolForgeService, code: str):
    spec = ToolSpec(name="probe_tool", description="test tool")
    return service.forge_tool(spec, code)


def test_gate_off_refuses_exec(service):
    spec = ToolSpec(name="probe_tool", description="test tool")
    code = "def probe_tool():\n    return 1\n"
    tool = service.forge_tool(spec, code)
    with pytest.raises(ToolForgeError) as err:
        service.execute_tool(tool, {})
    assert "SUPREMEAI_ALLOW_INPROCESS_CODEGEN" in str(err.value) or "denied" in str(err.value).lower()


def test_infinite_loop_hits_time_budget(service, gate_on):
    tool = _forge(service, "def probe_tool():\n    while True:\n        pass\n")
    with pytest.raises(ToolForgeError) as err:
        service.execute_tool(tool, {}, timeout_seconds=0.3)
    assert "execution budget" in str(err.value)


def test_dunder_globals_staging_rejected(service, gate_on):
    code = (
        "staged = [c for c in ().__class__.__mro__]\n"
        "def probe_tool():\n    return staged\n"
    )
    # AST scanner (strict) must already flag this; if it somehow passes the
    # scan, the runtime dunder-globals guard must still stop execution.
    try:
        tool = _forge(service, code)
    except SecurityViolationError:
        return  # scanner caught it — defense layer 1 works
    with pytest.raises((SecurityViolationError, ToolForgeError)):
        service.execute_tool(tool, {})


def test_benign_tool_executes_and_returns(service, gate_on):
    tool = _forge(service, "def probe_tool(a, b):\n    return a + b\n")
    assert service.execute_tool(tool, {"a": 2, "b": 3}) == 5
