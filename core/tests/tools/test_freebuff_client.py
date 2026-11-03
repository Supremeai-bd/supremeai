import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from tools.freebuff_client import FreebuffClient


@pytest.mark.asyncio
@patch("asyncio.create_subprocess_exec")
async def test_delegate_task_success(mock_subprocess):
    """
    বাংলা মন্তব্য: FreebuffClient সফলভাবে একটি টাস্ক এক্সটার্নাল CLI-কে ডেলিগেট করতে পারে কিনা তা পরীক্ষা করা হচ্ছে।
    """
    # সাবপ্রসেসকে মক করা হচ্ছে
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"Task output from freebuff", b"")
    mock_proc.returncode = 0
    mock_subprocess.return_value = mock_proc

    client = FreebuffClient(binary_path="/usr/local/bin/freebuff")
    result = await client.delegate_task(["generate", "--prompt", "hello"])

    # যাচাই করা হচ্ছে যে সাবপ্রসেস সঠিক আর্গুমেন্ট দিয়ে কল হয়েছে
    mock_subprocess.assert_awaited_once_with(
        "/usr/local/bin/freebuff",
        "generate",
        "--prompt",
        "hello",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    assert result["exit_code"] == 0
    assert result["stdout"] == "Task output from freebuff"
    assert result["stderr"] == ""


@pytest.mark.asyncio
@patch("asyncio.create_subprocess_exec")
async def test_delegate_task_cli_error(mock_subprocess):
    """
    বাংলা মন্তব্য: এক্সটার্নাল CLI টুলটি যদি কোনো এরর (non-zero exit code) রিটার্ন করে, তা সঠিকভাবে হ্যান্ডেল হয় কিনা।
    """
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"", b"Error: Invalid command")
    mock_proc.returncode = 1
    mock_subprocess.return_value = mock_proc

    client = FreebuffClient()
    result = await client.delegate_task(["invalid-command"])

    assert result["exit_code"] == 1
    assert result["stdout"] == ""
    assert result["stderr"] == "Error: Invalid command"


@pytest.mark.asyncio
@patch("asyncio.create_subprocess_exec")
async def test_delegate_task_execution_exception(mock_subprocess):
    """
    বাংলা মন্তব্য: যদি CLI টুলটি খুঁজেই পাওয়া না যায় (e.g., FileNotFoundError), সেই এক্সেপশনটি ধরা হয় কিনা।
    """
    # সাবপ্রসেসকে FileNotFoundError থ্রো করতে বলা হচ্ছে
    mock_subprocess.side_effect = FileNotFoundError("freebuff command not found")

    client = FreebuffClient()
    result = await client.delegate_task(["some-task"])

    assert result["success"] is False
    assert "freebuff command not found" in result["error"]
