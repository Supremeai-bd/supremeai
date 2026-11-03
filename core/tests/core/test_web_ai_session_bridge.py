"""Unit tests for WebAISessionBridge (Zero-Cost Web Session AI Adapter).

বাংলা সারসংক্ষেপ:
------------------
WebAISessionBridge-এর সেশন কুকি লোডিং, হেডার জেনারেশন, ভল্ট ইন্টিগ্রেশন
এবং Claude / ChatGPT / v0 এর মকড কল টেস্ট।
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from cryptography.fernet import Fernet

from core.browser_session_vault import BrowserSessionVault
from core.web_ai_session_bridge import (
    CURL_CFFI_AVAILABLE,
    ROOKIEPY_AVAILABLE,
    WebAISessionBridge,
    WebAISessionError,
)


@pytest.fixture
def test_vault(tmp_path):
    """টেস্টের জন্য ডামি এনক্রিপ্টেড সেশন ভল্ট।"""
    key = Fernet.generate_key()
    vault = BrowserSessionVault(tmp_path / "vault", encryption_key=key)
    return vault, key, tmp_path / "vault"


def test_bridge_init_and_dependencies():
    """বাংলা মন্তব্য: ব্রিজ ইনিশিয়ালাইজেশন ও অপশনাল ডিপেন্ডেন্সি টেস্ট।"""
    bridge = WebAISessionBridge()
    assert bridge.vault is None
    assert isinstance(CURL_CFFI_AVAILABLE, bool)
    assert isinstance(ROOKIEPY_AVAILABLE, bool)


def test_cookie_resolution_explicit_and_env(monkeypatch):
    """বাংলা মন্তব্য: সরাসরি টোকেন ও এনভায়রনমেন্ট ভেরিয়েবল থেকে কুকি রিজলভ যাচাই।"""
    bridge = WebAISessionBridge()

    # ১. সরাসরি পাস করা টোকেন
    cookies = bridge.resolve_session_cookies("claude", explicit_token="sk-ant-sid-test-token")
    assert cookies.get("sessionKey") == "sk-ant-sid-test-token"

    # ২. ENV ভেরিয়েবল থেকে টোকেন
    monkeypatch.setenv("CHATGPT_SESSION_TOKEN", "chatgpt-test-token-123")
    cookies_cg = bridge.resolve_session_cookies("chatgpt")
    assert cookies_cg.get("__Secure-next-auth.session-token") == "chatgpt-test-token-123"


def test_cookie_resolution_from_vault(test_vault):
    """বাংলা মন্তব্য: BrowserSessionVault থেকে এনক্রিপ্টেড সেশন কুকি রিকভারি যাচাই।"""
    vault, key, vault_path = test_vault
    # ভল্টে ডামি কুকি সেভ
    vault.save_session(
        service="claude",
        cookies=[{"name": "sessionKey", "value": "vault-recovered-secret"}],
        local_storage={"theme": "dark"},
    )

    bridge = WebAISessionBridge(vault_path=vault_path, encryption_key=key)
    cookies = bridge.resolve_session_cookies("claude")
    assert cookies.get("sessionKey") == "vault-recovered-secret"


@pytest.mark.asyncio
async def test_fail_closed_without_cookies():
    """বাংলা মন্তব্য: কোনো সেশন না থাকলে Fail-closed নিশ্চিত করা।"""
    bridge = WebAISessionBridge()
    with pytest.raises(WebAISessionError, match="No active session or cookies found"):
        await bridge.complete(service="claude", prompt="Hello Claude")


@pytest.mark.asyncio
async def test_claude_session_mocked_completion():
    """বাংলা মন্তব্য: Claude ওয়েব সেশন রিকোয়েস্ট ও OpenAI ফরম্যাট ভেরিফিকেশন।"""
    bridge = WebAISessionBridge()

    async def mock_execute(
        service, method, url, headers, cookies, json_data=None, timeout_seconds=30.0
    ):
        if "organizations" in url and method == "GET":
            return 200, [{"uuid": "org-uuid-1234", "name": "Personal"}]
        if "chat_conversations" in url and method == "POST" and "completion" not in url:
            return 201, {"uuid": "conv-uuid-5678"}
        if "completion" in url and method == "POST":
            return 200, {"completion": "Claude Web-এর পক্ষ থেকে শুভেচ্ছা! আপনার কাজ প্রস্তুত।"}
        return 404, {}

    with patch.object(bridge, "execute_http_request", side_effect=mock_execute):
        res = await bridge.complete(
            service="claude",
            prompt="Hello, Claude!",
            session_token="test-session-key",
        )

        assert res["object"] == "chat.completion"
        assert (
            res["choices"][0]["message"]["content"]
            == "Claude Web-এর পক্ষ থেকে শুভেচ্ছা! আপনার কাজ প্রস্তুত।"
        )
        assert res["usage"]["cost_usd"] == 0.0  # জিরো-কস্ট ইনভ্যারিয়েন্ট
        assert res["metadata"]["zero_cost"] is True


@pytest.mark.asyncio
async def test_chatgpt_session_mocked_completion():
    """বাংলা মন্তব্য: ChatGPT ওয়েব সেশন রিকোয়েস্ট ও রেসপন্স ভেরিফিকেশন।"""
    bridge = WebAISessionBridge()

    async def mock_execute(
        service, method, url, headers, cookies, json_data=None, timeout_seconds=30.0
    ):
        if "auth/session" in url:
            return 200, {"accessToken": "fake-jwt-token-999"}
        if "conversation" in url:
            return 200, {"text": "ChatGPT Web রিপ্লাই: কাজ সম্পন্ন!"}
        return 404, {}

    with patch.object(bridge, "execute_http_request", side_effect=mock_execute):
        res = await bridge.complete(
            service="chatgpt",
            prompt="Analyze this task",
            session_token="chatgpt-token",
        )

        assert res["object"] == "chat.completion"
        assert "ChatGPT Web রিপ্লাই" in res["choices"][0]["message"]["content"]
        assert res["usage"]["cost_usd"] == 0.0


@pytest.mark.asyncio
async def test_v0_session_mocked_completion():
    """বাংলা মন্তব্য: v0.dev ওয়েব সেশন রিকোয়েস্ট ও রেসপন্স ভেরিফিকেশন।"""
    bridge = WebAISessionBridge()

    async def mock_execute(
        service, method, url, headers, cookies, json_data=None, timeout_seconds=30.0
    ):
        if "api/generate" in url:
            return 200, {"result": "<Button>SupremeAI Generated Component</Button>"}
        return 404, {}

    with patch.object(bridge, "execute_http_request", side_effect=mock_execute):
        res = await bridge.complete(
            service="v0",
            prompt="Generate a sleek button",
            session_token="v0-auth-token",
        )

        assert "<Button>" in res["choices"][0]["message"]["content"]
        assert res["usage"]["cost_usd"] == 0.0


# ── WebAISessionPool & Auto-Rotation Tests ────────────────────────────────────


def test_session_pool_registration_and_lru():
    """বাংলা মন্তব্য: অ্যাকাউন্টের রেজিস্ট্রেশন ও LRU (Least Recently Used) বাছাই টেস্ট।"""
    from core.web_ai_session_bridge import WebAISessionPool

    pool = WebAISessionPool()
    # ক্লিন স্টেট
    pool.register_account("claude", "token-1", "acc-1")
    pool.register_account("claude", "token-2", "acc-2")

    assert len(pool.accounts["claude"]) == 2
    # ১ম অ্যাকাউন্ট পাওয়া উচিত
    chosen = pool.get_available_account("claude")
    assert chosen.account_id == "acc-1"

    # ১ম ব্যবহার হলে ২য় অ্যাকাউন্ট নির্বাচিত হবে
    pool.mark_success("claude", "acc-1")
    chosen2 = pool.get_available_account("claude")
    assert chosen2.account_id == "acc-2"


@pytest.mark.asyncio
async def test_session_pool_429_auto_rotation():
    """
    বাংলা সারসংক্ষেপ:
    ------------------
    auth2api অনুপ্রাণিত 429 রেট লিমিট অটো-রোটেশন টেস্ট।
    অ্যাকাউন্ট-১ এ 429 Too Many Requests আসলে সেটি কুলডাউনে যাবে
    এবং তাৎক্ষণিকভাবে অ্যাকাউন্ট-২ এ সুইচ করে সফলভাবে কাজ শেষ করবে।
    """
    from core.web_ai_session_bridge import WebAISessionPool

    bridge = WebAISessionBridge()
    pool = WebAISessionPool(bridge=bridge)
    pool.accounts.clear()

    pool.register_account("claude", "token-rate-limited", "acc-1")
    pool.register_account("claude", "token-healthy", "acc-2")

    async def mock_complete(
        service, prompt, system_prompt=None, model=None, session_token=None, **kwargs
    ):
        if session_token == "token-rate-limited":
            raise WebAISessionError("HTTP 429: Too Many Requests, slow down")
        if session_token == "token-healthy":
            return {
                "id": "chatcmpl-rotated",
                "object": "chat.completion",
                "created": 123456,
                "model": "claude-web",
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": "Rotated response!"}}
                ],
                "usage": {"cost_usd": 0.0},
                "metadata": {"zero_cost": True},
            }
        raise WebAISessionError("Invalid token")

    with patch.object(bridge, "complete", side_effect=mock_complete):
        res = await pool.complete_with_cascade(
            prompt="Test prompt",
            preferred_service="claude",
            fallback_chain=("claude",),
        )

        # যাচাই: রোটেশন হয়ে ২য় অ্যাকাউন্ট কাজ করেছে
        assert res["choices"][0]["message"]["content"] == "Rotated response!"
        assert res["metadata"]["account_used"] == "acc-2"
        assert res["metadata"]["failovers_triggered"] == 1

        # ১ম অ্যাকাউন্ট কুলডাউনে আছে কি না যাচাই
        acc1 = [a for a in pool.accounts["claude"] if a.account_id == "acc-1"][0]
        assert acc1.cooldown_until > 0


@pytest.mark.asyncio
async def test_session_pool_cross_provider_cascade():
    """
    বাংলা সারসংক্ষেপ:
    ------------------
    g4f অনুপ্রাণিত ক্রস-প্রোভাইডার ক্যাস্কেড টেস্ট।
    Claude সম্পূর্ণ ডাউন থাকলে ChatGPT-তে অটো-শিফট হয়ে কাজ সম্পন্ন হবে।
    """
    from core.web_ai_session_bridge import WebAISessionPool

    bridge = WebAISessionBridge()
    pool = WebAISessionPool(bridge=bridge)
    pool.accounts.clear()

    pool.register_account("claude", "token-claude", "claude-1")
    pool.register_account("chatgpt", "token-chatgpt", "chatgpt-1")

    async def mock_complete(
        service, prompt, system_prompt=None, model=None, session_token=None, **kwargs
    ):
        if service == "claude":
            raise WebAISessionError("Claude WAF Block 403 Forbidden")
        if service == "chatgpt":
            return {
                "id": "chatcmpl-cascade",
                "object": "chat.completion",
                "created": 123456,
                "model": "chatgpt-web",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ChatGPT rescued the request!"},
                    }
                ],
                "usage": {"cost_usd": 0.0},
                "metadata": {"zero_cost": True},
            }
        raise WebAISessionError("Unknown service")

    with patch.object(bridge, "complete", side_effect=mock_complete):
        res = await pool.complete_with_cascade(
            prompt="Hello multi-provider world",
            preferred_service="claude",
            fallback_chain=("claude", "chatgpt"),
        )

        assert res["choices"][0]["message"]["content"] == "ChatGPT rescued the request!"
        assert res["metadata"]["service_used"] == "chatgpt"
        assert res["metadata"]["failovers_triggered"] == 1


# ── FastAPI OpenAI Proxy Route Tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_fastapi_web_ai_proxy_routes():
    """
    বাংলা সারসংক্ষেপ:
    ------------------
    FastAPI /v1/chat/completions, /v1/models, /v1/pool/status এন্ডপয়েন্ট টেস্ট।
    """
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from api.routes.web_ai_proxy import router as web_ai_router
    from core.web_ai_session_bridge import global_session_pool

    test_app = FastAPI()
    test_app.include_router(web_ai_router)

    # মক রেসপন্স সেটআপ
    async def mock_cascade(
        prompt, system_prompt=None, preferred_service="claude", fallback_chain=None, model=None
    ):
        return {
            "id": "chatcmpl-mock-api",
            "object": "chat.completion",
            "created": 123456,
            "model": model or "auto-zero-cost",
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": "API proxy answer!"}}
            ],
            "usage": {"cost_usd": 0.0},
            "metadata": {"zero_cost": True, "service_used": preferred_service},
        }

    with patch.object(global_session_pool, "complete_with_cascade", side_effect=mock_cascade):
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            # ১. /v1/models টেস্ট
            m_resp = await client.get("/v1/models")
            assert m_resp.status_code == 200
            assert len(m_resp.json()["data"]) >= 3

            # ২. /v1/pool/status টেস্ট
            s_resp = await client.get("/v1/pool/status")
            assert s_resp.status_code == 200
            assert "services" in s_resp.json()

            # ৩. /v1/pool/accounts ডায়নামিক রেজিস্ট্রেশন টেস্ট
            # ROOT-CAUSE #2730-চুক্তি: request-body টোকেন এখন সচেতনভাবে প্রত্যাখ্যাত
            # (pool-poisoning প্রতিরোধ) — vault/env-নির্ভর token-less রেজিস্ট্রেশনই
            # সফল পথ; body-টোকেন 422।
            reg_resp = await client.post(
                "/v1/pool/accounts",
                json={
                    "service": "claude",
                    "account_id": "test-dynamic-1",
                },
            )
            assert reg_resp.status_code == 200
            assert reg_resp.json()["status"] == "success"
            assert reg_resp.json()["account_id"] == "test-dynamic-1"

            # ৩-খ. #2730 সিকিউরিটি-পিন: body-টোকেন পাঠালে 422 (pool poisoning ব্লকড)
            token_resp = await client.post(
                "/v1/pool/accounts",
                json={
                    "service": "claude",
                    "token": "dynamic-key-999",
                    "account_id": "test-dynamic-2",
                },
            )
            assert token_resp.status_code == 422
            assert "vault/env" in token_resp.json()["detail"]

            # ৪. /v1/chat/completions টেস্ট
            chat_resp = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "claude-3-7-sonnet-web",
                    "messages": [{"role": "user", "content": "Hello via proxy!"}],
                },
            )
            assert chat_resp.status_code == 200
            data = chat_resp.json()
            assert data["choices"][0]["message"]["content"] == "API proxy answer!"
            assert data["usage"]["cost_usd"] == 0.0


# ── Session Silent Refresh & Turnstile Auto-Pause Tests ───────────────────────


@pytest.mark.asyncio
async def test_refresh_session_and_vault_persistence(test_vault):
    """বাংলা মন্তব্য: সেশন রিফ্রেশ এবং ভল্টে ফ্রেশ টোকেন ও হেডার সিঙ্ক টেস্ট।"""
    vault, key, vault_path = test_vault
    bridge = WebAISessionBridge(vault_path=vault_path, encryption_key=key)

    async def mock_execute(
        service, method, url, headers, cookies, json_data=None, timeout_seconds=30.0, proxy=None
    ):
        if "api/auth/session" in url:
            return 200, {
                "accessToken": "fresh-refreshed-token-2026",
                "user": {"email": "test@dev.ai"},
            }
        return 404, {}

    with patch.object(bridge, "execute_http_request", side_effect=mock_execute):
        ok, res = await bridge.refresh_session(
            service="chatgpt",
            explicit_token="initial-token",
            custom_ua="Mozilla/5.0 Custom Test UA",
        )
        assert ok is True
        assert res["status"] == "refreshed"

        # ভল্টে রিফ্রেশড ডাটা যাচাই
        saved_cookies, saved_storage = vault.load_session("chatgpt")
        assert len(saved_cookies) > 0
        assert saved_storage.get("accessToken") == "fresh-refreshed-token-2026"
        assert saved_storage["headers"]["User-Agent"] == "Mozilla/5.0 Custom Test UA"


@pytest.mark.asyncio
async def test_turnstile_challenge_auto_pause():
    """
    বাংলা সারসংক্ষেপ:
    ------------------
    কোনো অ্যাকাউন্টে ক্লাউডফ্লেয়ার টার্নস্টাইল চ্যালেঞ্জ (HTTP 403) আসলে
    অ্যাকাউন্টটি পুলে সাময়িক পজ হবে এবং পরবর্তী সচল অ্যাকাউন্ট পিক করবে।
    """
    from core.web_ai_session_bridge import WebAISessionPool

    pool = WebAISessionPool()
    pool.accounts.clear()

    acc1 = pool.register_account("claude", "turnstile-token", "claude-turnstile")
    acc2 = pool.register_account("claude", "clean-token", "claude-clean")

    # মার্ক ফেইলিউর উইথ টার্নস্টাইল চ্যালেঞ্জ
    pool.mark_failure("claude", acc1.account_id, "Cloudflare Turnstile 403 Forbidden")
    assert acc1.turnstile_paused is True

    # পরবর্তী অনুরোধে টার্নস্টাইল আক্রান্ত অ্যাকাউন্ট এড়িয়ে ফ্রেশ অ্যাকাউন্ট ২ পাওয়া উচিত
    chosen = pool.get_available_account("claude")
    assert chosen.account_id == acc2.account_id


@pytest.mark.asyncio
async def test_refresh_pool_sessions_batch():
    """বাংলা মন্তব্য: পুলে থাকা সমস্ত অ্যাকাউন্টের বাল্ক রিফ্রেশ টেস্ট।"""
    from core.web_ai_session_bridge import WebAISessionPool

    bridge = WebAISessionBridge()
    pool = WebAISessionPool(bridge=bridge)
    pool.accounts.clear()

    pool.register_account("chatgpt", "cg-token-1", "cg-1")

    async def mock_refresh(service, explicit_token=None, custom_ua=None):
        return True, {"status": "ok"}

    with patch.object(bridge, "refresh_session", side_effect=mock_refresh):
        results = await pool.refresh_pool_sessions(custom_ua="Sniffed-Local-UA")
        assert "chatgpt" in results
        assert results["chatgpt"][0]["refreshed"] is True


@pytest.mark.asyncio
async def test_parallel_multi_task_execution():
    """
    বাংলা সারসংক্ষেপ:
    ------------------
    একই সাথে সমান্তরালে (Parallel) মাল্টিপল AI সেশন দিয়ে ভিন্ন ভিন্ন টাস্ক সম্পন্ন করার টেস্ট।
    - Task 1 (Frontend): v0
    - Task 2 (Backend): Claude
    - Task 3 (Audit): ChatGPT
    """
    from core.web_ai_session_bridge import WebAISessionPool

    bridge = WebAISessionBridge()
    pool = WebAISessionPool(bridge=bridge)

    async def mock_cascade(
        prompt, system_prompt=None, preferred_service="claude", fallback_chain=(), model=None
    ):
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": f"Completed by {preferred_service}: {prompt[:15]}",
                    }
                }
            ],
            "metadata": {"service_used": preferred_service, "account_used": "mock-acc"},
        }

    with patch.object(pool, "complete_with_cascade", side_effect=mock_cascade):
        tasks = [
            {"task_id": "task_frontend", "prompt": "Design React button", "service": "v0"},
            {"task_id": "task_backend", "prompt": "Build auth router", "service": "claude"},
            {"task_id": "task_audit", "prompt": "Audit SQL injection", "service": "chatgpt"},
        ]

        batch_result = await pool.execute_parallel_tasks(tasks=tasks, concurrency_limit=3)

        assert batch_result["total_tasks"] == 3
        assert batch_result["succeeded"] == 3
        assert batch_result["failed"] == 0
        assert "task_frontend" in batch_result["tasks"]
        assert batch_result["tasks"]["task_frontend"]["service"] == "v0"
        assert "Completed by v0" in batch_result["tasks"]["task_frontend"]["content"]
        assert batch_result["tasks"]["task_backend"]["service"] == "claude"
        assert batch_result["tasks"]["task_audit"]["service"] == "chatgpt"


@pytest.mark.asyncio
async def test_fastapi_parallel_tasks_route():
    """বাংলা মন্তব্য: FastAPI /v1/tasks/parallel এন্ডপয়েন্ট সমান্তরাল টাস্ক সম্পাদন টেস্ট।"""
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from api.routes.web_ai_proxy import router as proxy_router
    from core.web_ai_session_bridge import global_session_pool

    app = FastAPI()
    app.include_router(proxy_router)

    async def mock_parallel(tasks, concurrency_limit=5):
        return {
            "total_tasks": len(tasks),
            "succeeded": len(tasks),
            "failed": 0,
            "total_duration_ms": 150.0,
            "tasks": {
                t["task_id"]: {"status": "success", "service": t.get("service", "claude")}
                for t in tasks
            },
        }

    with patch.object(global_session_pool, "execute_parallel_tasks", side_effect=mock_parallel):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(
                "/v1/tasks/parallel",
                json={
                    "tasks": [
                        {"task_id": "ui_task", "prompt": "Build UI", "service": "v0"},
                        {"task_id": "api_task", "prompt": "Build API", "service": "claude"},
                    ],
                    "concurrency_limit": 2,
                },
            )
            assert res.status_code == 200
            data = res.json()
            assert data["total_tasks"] == 2
            assert data["succeeded"] == 2
            assert "ui_task" in data["tasks"]
