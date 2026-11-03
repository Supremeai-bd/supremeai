import sys
from unittest.mock import AsyncMock, MagicMock, patch
from unittest.mock import MagicMock as _MagicMock

import pytest

# Import guard: agents package init may import optional google.genai.
if "google" not in sys.modules:
    sys.modules["google"] = MagicMock()
if "google.genai" not in sys.modules:
    sys.modules["google.genai"] = MagicMock()

from agents.headless_terminal_agent import CommandSafety, HeadlessTerminalAgent


@pytest.mark.anyio
async def test_execute_blocks_dangerous_command():
    agent = HeadlessTerminalAgent()
    # Mock LLM network calls
    agent.interpreter.check_safety = AsyncMock(
        return_value=(CommandSafety.BLOCKED, "Dangerous command")
    )
    res = await agent.execute("echo malicious_payload_blocked")

    # Heuristic may classify differently depending on routing; assert it is not SAFE
    assert res.safety_status != CommandSafety.SAFE


@pytest.mark.anyio
async def test_execute_review_required_requires_confirmation():
    agent = HeadlessTerminalAgent()
    # Mock LLM network calls
    agent.interpreter.check_safety = AsyncMock(
        return_value=(CommandSafety.REVIEW_REQUIRED, "Requires review")
    )
    res = await agent.execute("sudo npm install -g x")
    # sudo কমান্ড SAFE হওয়া উচিত নয় — security policy enforce করা হচ্ছে
    assert res.safety_status != CommandSafety.SAFE


@pytest.mark.anyio
async def test_execute_natural_language_interpret_path():
    agent = HeadlessTerminalAgent()
    agent.interpreter.interpret = AsyncMock(return_value="echo hello")
    agent.interpreter.check_safety = AsyncMock(return_value=(CommandSafety.SAFE, "Ok"))

    mock_proc = _MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b"out", b""))
    mock_proc.returncode = 0

    with patch(
        "agents.headless_terminal_agent.asyncio.create_subprocess_exec",
        new_callable=AsyncMock,
        return_value=mock_proc,
    ):
        with patch(
            "agents.headless_terminal_agent.asyncio.wait_for",
            new_callable=AsyncMock,
            return_value=(b"out", b""),
        ):
            res = await agent.execute("what is the status", auto_confirm=True, context={})

    assert res.exit_code == 0
    assert "out" in res.output


@pytest.mark.anyio
async def test_execute_command_timeout():
    agent = HeadlessTerminalAgent()
    agent.interpreter.check_safety = AsyncMock(return_value=(CommandSafety.SAFE, "Ok"))

    mock_proc = _MagicMock()
    mock_proc.communicate = AsyncMock()
    mock_proc.returncode = None
    mock_proc.kill = MagicMock()

    with patch(
        "agents.headless_terminal_agent.asyncio.create_subprocess_exec",
        new_callable=AsyncMock,
        return_value=mock_proc,
    ):
        with patch(
            "agents.headless_terminal_agent.asyncio.wait_for",
            new_callable=AsyncMock,
            side_effect=TimeoutError,
        ):
            res = await agent.execute("ls")

    assert res.exit_code == 124
