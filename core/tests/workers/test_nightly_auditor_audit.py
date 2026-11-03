"""NightlyChaosAuditor.execute_audit_sequence (workers/chaos_worker.py) এর ইউনিট টেস্ট।

বাংলা: অডিট সিকোয়েন্সের তিনটি ব্রাঞ্চ কভার করা হয়েছে —
(১) স্যান্ডবক্স নিরাপদ + রানটাইম 200 → PASSED (True),
(২) স্যান্ডবক্স বাইপাস শনাক্ত → LOCKED (False),
(৩) রানটাইম 500 → LOCKED (False)।
fuzz_sandbox ও httpx.AsyncClient মক করা হয়েছে; gate_ref=None (firestore নেই)।
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from workers import chaos_worker


def _make_auditor():
    # বাংলা: STAGING_REPLICA_URL সেট না থাকলে auditor নিজেকে disable করে দেয়
    # (target_url খালি -> execute_audit_sequence সবসময় False), তাই এই
    # নিরাপত্তা-টার্গেটেড unit test-গুলোর জন্য একটা ডামি URL সেট করা হচ্ছে।
    with (
        patch("workers.chaos_worker.get_firestore_db", return_value=None),
        patch.dict("os.environ", {"STAGING_REPLICA_URL": "https://staging.example.com"}),
    ):
        return chaos_worker.NightlyChaosAuditor()


def _make_async_client(status_code: int = 200):
    # বাংলা: `async with httpx.AsyncClient() as client` কাজ করার জন্য
    # __aenter__ যাতে নিজেকেই রিটার্ন করে (client == async_client)
    async_client = AsyncMock()
    async_client.__aenter__.return_value = async_client
    async_client.__aexit__.return_value = False
    resp = MagicMock()
    resp.status_code = status_code
    async_client.post.return_value = resp
    return async_client


@pytest.mark.asyncio
async def test_audit_passes_when_safe():
    auditor = _make_auditor()
    payloads = [("print('hello')", {"risk": "low"}), ("x = 1", {})]
    async_client = _make_async_client(status_code=200)

    with (
        patch("workers.chaos_worker.generate_fuzz_payloads", return_value=payloads),
        patch("workers.chaos_worker.run_sandbox_ast_check", return_value=False),
        patch("workers.chaos_worker.httpx.AsyncClient", return_value=async_client),
    ):
        result = await auditor.execute_audit_sequence()

    assert result is True


@pytest.mark.asyncio
async def test_audit_locks_on_sandbox_breach():
    auditor = _make_auditor()
    # বাংলা: স্যান্ডবক্স যদি ম্যালিশিয়াস কোডকে Safe বলে (True রিটার্ন), তবে breach গণ্য হয়
    payloads = [("import os; os.system('echo malicious_payload_blocked')", {"risk": "high"})]
    async_client = _make_async_client(status_code=200)

    with (
        patch("workers.chaos_worker.generate_fuzz_payloads", return_value=payloads),
        patch("workers.chaos_worker.run_sandbox_ast_check", return_value=True),
        patch("workers.chaos_worker.httpx.AsyncClient", return_value=async_client),
    ):
        result = await auditor.execute_audit_sequence()

    assert result is False


@pytest.mark.asyncio
async def test_audit_locks_on_runtime_server_error():
    auditor = _make_auditor()
    payloads = [("print('ok')", {})]
    async_client = _make_async_client(status_code=503)  # SERVER_ERROR_THRESHOLD (500) এর ওপরে

    with (
        patch("workers.chaos_worker.generate_fuzz_payloads", return_value=payloads),
        patch("workers.chaos_worker.run_sandbox_ast_check", return_value=False),
        patch("workers.chaos_worker.httpx.AsyncClient", return_value=async_client),
    ):
        result = await auditor.execute_audit_sequence()

    assert result is False


@pytest.mark.asyncio
async def test_audit_locks_when_fuzz_unavailable():
    auditor = _make_auditor()
    async_client = _make_async_client(status_code=200)

    # বাংলা: fuzz_sandbox আনঅভেইলেবল হলে ImportError → LOCKED (False)
    with (
        patch("workers.chaos_worker.generate_fuzz_payloads", None),
        patch("workers.chaos_worker.run_sandbox_ast_check", None),
        patch("workers.chaos_worker.httpx.AsyncClient", return_value=async_client),
    ):
        result = await auditor.execute_audit_sequence()

    assert result is False
