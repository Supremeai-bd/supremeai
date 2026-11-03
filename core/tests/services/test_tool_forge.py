# backend/tests/services/test_tool_forge.py
import pytest

from core.security.codegen_gate import ALLOW_INPROCESS_CODEGEN_ENV
from services.tool_forge import (
    SecurityViolationError,
    ToolForgeError,
    ToolForgeService,
    ToolSpec,
)


def test_tool_forge_safe_tool_synthesis_and_execution(monkeypatch):
    # Issue #704: in-process exec is fail-closed by default; this coverage
    # test exercises the explicitly-enabled (local dev) path.
    monkeypatch.setenv(ALLOW_INPROCESS_CODEGEN_ENV, "true")
    service = ToolForgeService()
    spec = ToolSpec(
        name="calculate_discount",
        description="Calculates discounted price",
        parameters={"price": "float", "discount_pct": "float"},
        return_type="float",
    )

    code = """
def calculate_discount(price, discount_pct):
    return price * (1.0 - discount_pct / 100.0)
"""

    tool = service.forge_tool(spec, code)
    assert tool.is_safe is True
    assert tool.spec.name == "calculate_discount"

    result = service.execute_tool(tool, {"price": 100.0, "discount_pct": 20.0})
    assert result == 80.0


def test_tool_forge_blocks_os_system_rce():
    service = ToolForgeService()
    spec = ToolSpec(name="malicious_tool", description="Attempts RCE")

    malicious_code = """
import os
def malicious_tool():
    os.system("echo hacked")
    return True
"""

    with pytest.raises(SecurityViolationError):
        service.forge_tool(spec, malicious_code)


def test_tool_forge_blocks_eval_rce():
    service = ToolForgeService()
    spec = ToolSpec(name="eval_tool", description="Attempts eval escape")

    malicious_code = """
def eval_tool():
    return eval("1 + 1")
"""

    with pytest.raises(SecurityViolationError):
        service.forge_tool(spec, malicious_code)


def test_tool_forge_blocks_open_file_io():
    service = ToolForgeService()
    spec = ToolSpec(name="file_stealer", description="Attempts file read")

    malicious_code = """
def file_stealer():
    with open("/etc/passwd", "r") as f:
        return f.read()
"""

    with pytest.raises(SecurityViolationError):
        service.forge_tool(spec, malicious_code)


def test_tool_forge_execution_runtime_error_handled(monkeypatch):
    monkeypatch.setenv("SUPREMEAI_ALLOW_INPROCESS_CODEGEN", "true")
    service = ToolForgeService()
    spec = ToolSpec(name="zero_division_tool", description="Divides by zero")

    code = """
def zero_division_tool():
    return 10 / 0
"""

    tool = service.forge_tool(spec, code)
    with pytest.raises(ToolForgeError, match="Tool execution failed"):
        service.execute_tool(tool, {})
