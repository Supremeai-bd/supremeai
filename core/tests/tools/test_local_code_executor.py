import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from tools.code.local_code_executor import LocalCodeExecutor


@pytest.mark.asyncio
@patch("tools.code.local_code_executor.DockerSandbox")
async def test_execute_local_code_with_docker_success(MockDockerSandbox):
    """
    বাংলা মন্তব্য: ডকার স্যান্ডবক্স সফলভাবে কোড এক্সিকিউট করতে পারলে তার আউটপুট যাচাই করা হচ্ছে।
    """
    # ডকার স্যান্ডবক্সের run_secure মেথডকে মক করা হচ্ছে
    mock_sandbox_instance = MockDockerSandbox.return_value
    mock_sandbox_instance.run_secure = AsyncMock(
        return_value={
            "success": True,
            "output": "Docker execution success",
            "error": "",
        }
    )

    executor = LocalCodeExecutor(use_docker=True)
    result = await executor.execute_local_code("print('hello from docker')")

    # যাচাই করা হচ্ছে যে run_secure কল হয়েছে
    mock_sandbox_instance.run_secure.assert_awaited_once()
    assert result["success"] is True
    assert result["output"] == "Docker execution success"


@pytest.mark.asyncio
@patch("tools.code.local_code_executor.DockerSandbox")
@patch("asyncio.create_subprocess_exec")
async def test_execute_local_code_docker_fails_fallback_to_subprocess(
    mock_subprocess, MockDockerSandbox
):
    """
    বাংলা মন্তব্য: ডকার এক্সিকিউশন ব্যর্থ হলে সিস্টেমটি হোস্ট সাবপ্রসেসে ফলব্যাক করে কিনা তা পরীক্ষা করা হচ্ছে।
    """
    # ডকারকে ব্যর্থ হিসেবে সিমুলেট করা হচ্ছে
    MockDockerSandbox.return_value.run_secure.side_effect = Exception("Docker not available")

    # সাবপ্রসেসকে সফল হিসেবে সিমুলেট করা হচ্ছে
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"Subprocess success", b"")
    mock_proc.returncode = 0
    mock_subprocess.return_value = mock_proc

    executor = LocalCodeExecutor(use_docker=True)
    # production guard bypass করার জন্য settings.env কে mock করা হচ্ছে
    with patch("tools.code.local_code_executor.settings") as mock_settings:
        mock_settings.env = "test"
        result = await executor.execute_local_code("print('fallback')")

    # যাচাই করা হচ্ছে যে সাবপ্রসেস কল হয়েছে
    mock_subprocess.assert_awaited_once()
    assert result["success"] is True
    assert result["output"] == "Subprocess success"


@pytest.mark.asyncio
@patch("asyncio.create_subprocess_exec")
async def test_execute_host_subprocess_success(mock_subprocess):
    """
    বাংলা মন্তব্য: ডকার ছাড়া সরাসরি হোস্ট সাবপ্রসেস এক্সিকিউশন সফল হলে তার আউটপুট পরীক্ষা করা হচ্ছে।
    """
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"Host success", b"")
    mock_proc.returncode = 0
    mock_subprocess.return_value = mock_proc

    executor = LocalCodeExecutor(use_docker=False)
    with patch("tools.code.local_code_executor.settings") as mock_settings:
        mock_settings.env = "test"
        result = await executor.execute_local_code("print('hello from host')")

    mock_subprocess.assert_awaited_once()
    assert result["success"] is True
    assert result["output"] == "Host success"


@pytest.mark.asyncio
@patch("asyncio.create_subprocess_exec")
async def test_execute_host_subprocess_error(mock_subprocess):
    """
    বাংলা মন্তব্য: হোস্ট সাবপ্রসেস এক্সিকিউশনের সময় কোনো এরর হলে তা সঠিকভাবে হ্যান্ডেল হয় কিনা তা যাচাই করা হচ্ছে।
    """
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"", b"Syntax Error")
    mock_proc.returncode = 1
    mock_subprocess.return_value = mock_proc

    executor = LocalCodeExecutor(use_docker=False)
    with patch("tools.code.local_code_executor.settings") as mock_settings:
        mock_settings.env = "test"
        result = await executor.execute_local_code("print('good syntax')")

    assert result["success"] is False
    assert result["error"] == "Syntax Error"


@pytest.mark.asyncio
@patch("asyncio.create_subprocess_exec")
async def test_execute_host_subprocess_timeout(mock_subprocess):
    """
    বাংলা মন্তব্য: হোস্ট সাবপ্রসেস এক্সিকিউশন টাইমআউট হলে সিস্টেমটি সঠিকভাবে টাইমআউট এরর রিটার্ন করে কিনা।
    """
    mock_proc = AsyncMock()
    # communicate মেথডকে asyncio.TimeoutError থ্রো করতে বলা হচ্ছে
    mock_proc.communicate.side_effect = asyncio.TimeoutError
    mock_subprocess.return_value = mock_proc

    executor = LocalCodeExecutor(use_docker=False)
    with patch("tools.code.local_code_executor.settings") as mock_settings:
        mock_settings.env = "test"
        result = await executor.execute_local_code("import time; time.sleep(5)", timeout_seconds=2)

    assert result["success"] is False
    assert result["error"] == "Execution TimeoutExpired"
