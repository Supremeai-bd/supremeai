"""Comprehensive tests for api/routes/admin_dashboard.py — targets 100% line + branch coverage.

Covers all endpoints and helper functions not yet tested by test_admin_dashboard_coverage.py:
  - load_users / save_users (success, file-not-found default creation, exception)
  - get_users, create_user (create + update), delete_user (found + not-found)
  - get_costs (success, no-file, exception)
  - get_health_map (various config states)
  - trigger_deploy
  - get_metrics (with/without keys, psutil ok/failed)
  - get_providers (with/without keys)
  - get_model_router, set_router_override
  - get_codebase_export (success + failure)
  - load_cost_caps / save_cost_caps / get_cost_caps / update_cost_caps
  - get_env_etag (redis cached, .env exists, .env missing, exception)
  - _acquire_env_lock / _release_env_lock (redis + file fallback)
  - logs_stream (log generator with file present/absent, cancellation)
"""

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from api.routes.admin_dashboard import (
    RouterOverrideRequest,
    UserUpdate,
    _acquire_env_lock,
    _release_env_lock,
    create_user,
    delete_user,
    get_codebase_export,
    get_cost_caps,
    get_costs,
    get_env_etag,
    get_health_map,
    get_metrics,
    get_model_router,
    get_providers,
    get_users,
    load_cost_caps,
    load_users,
    logs_stream,
    save_cost_caps,
    save_users,
    set_router_override,
    trigger_deploy,
    update_cost_caps,
)

# ── Helpers ────────────────────────────────────────────────────────────


@pytest.fixture
def temp_users_file(tmp_path, monkeypatch):
    """Redirect USERS_FILE to a temp directory."""
    import api.routes.admin_dashboard as mod

    users_file = str(tmp_path / "users.json")
    monkeypatch.setattr(mod, "USERS_FILE", users_file)
    return users_file


@pytest.fixture
def temp_cost_caps_file(tmp_path, monkeypatch):
    """Redirect COST_CAPS_FILE to a temp directory."""
    import api.routes.admin_dashboard as mod

    caps_file = str(tmp_path / "cost_caps.json")
    monkeypatch.setattr(mod, "COST_CAPS_FILE", caps_file)
    return caps_file


@pytest.fixture
def temp_env_file(tmp_path, monkeypatch):
    """Redirect .env and .env.lock to a temp directory."""
    env_file = str(tmp_path / ".env")
    lock_file = str(tmp_path / ".env.lock")
    monkeypatch.setattr("os.getcwd", lambda: str(tmp_path))
    return env_file, lock_file


# ── load_users / save_users ────────────────────────────────────────────


class TestLoadSaveUsers:
    def test_load_users_creates_default(self, temp_users_file):
        """File doesn't exist → creates default users and returns them."""
        users = load_users()
        assert len(users) == 3
        assert users[0]["username"] == "admin"
        assert users[1]["role"] == "Operator"
        assert os.path.exists(temp_users_file)

    def test_load_users_existing_file(self, temp_users_file):
        """File exists → loads from file."""
        with open(temp_users_file, "w") as f:
            json.dump([{"username": "custom", "role": "Admin", "permissions": ["all"]}], f)
        users = load_users()
        assert len(users) == 1
        assert users[0]["username"] == "custom"

    def test_load_users_corrupt_file(self, temp_users_file):
        """Corrupt JSON → returns empty list."""
        with open(temp_users_file, "w") as f:
            f.write("not valid json{{{")
        users = load_users()
        assert users == []

    def test_save_users(self, temp_users_file):
        """save_users writes to file."""
        users = [{"username": "test", "role": "Admin", "permissions": ["all"]}]
        save_users(users)
        with open(temp_users_file) as f:
            loaded = json.load(f)
        assert loaded == users


# ── get_users / create_user / delete_user ──────────────────────────────


class TestUserCRUD:
    def test_get_users(self, temp_users_file):
        """get_users returns loaded users."""
        result = get_users()
        assert len(result) == 3
        assert result[0]["username"] == "admin"

    def test_create_user_new(self, temp_users_file):
        """Creating a new user adds them."""
        user = UserUpdate(username="newuser", role="Operator", permissions=["read"])
        result = create_user(user)
        assert result["status"] == "success"
        assert "created" in result["message"]
        users = load_users()
        assert any(u["username"] == "newuser" for u in users)

    def test_create_user_updates_existing(self, temp_users_file):
        """Creating an existing user updates them."""
        user = UserUpdate(username="admin", role="SuperAdmin", permissions=["all", "delete"])
        result = create_user(user)
        assert result["status"] == "success"
        assert "updated" in result["message"]
        users = load_users()
        admin = next(u for u in users if u["username"] == "admin")
        assert admin["role"] == "SuperAdmin"

    def test_delete_user_found(self, temp_users_file):
        """Deleting an existing user succeeds."""
        result = delete_user("admin")
        assert result["status"] == "success"
        users = load_users()
        assert not any(u["username"] == "admin" for u in users)

    def test_delete_user_not_found(self, temp_users_file):
        """Deleting a non-existent user raises 404."""
        with pytest.raises(HTTPException) as exc_info:
            delete_user("nonexistent")
        assert exc_info.value.status_code == 404


# ── get_costs ──────────────────────────────────────────────────────────


class TestGetCosts:
    def test_get_costs_no_report_file(self, tmp_path, monkeypatch):
        """CostAuditor returns no text_report → returns unavailable message."""
        with patch("api.routes.admin_dashboard.CostAuditor") as mock_cls:
            mock_auditor = MagicMock()
            mock_auditor.generate_report.return_value = {
                "text_report": str(tmp_path / "nonexistent.md")
            }
            mock_cls.return_value = mock_auditor
            result = get_costs()
        assert result["status"] == "ok"
        assert "Unavailable" in result["report"]

    def test_get_costs_with_report_file(self, tmp_path, monkeypatch):
        """CostAuditor returns a valid report path → reads and returns content."""
        report_file = tmp_path / "cost_report.md"
        report_file.write_text("# Cost Report\nSome content")
        with patch("api.routes.admin_dashboard.CostAuditor") as mock_cls:
            mock_auditor = MagicMock()
            mock_auditor.generate_report.return_value = {"text_report": str(report_file)}
            mock_cls.return_value = mock_auditor
            result = get_costs()
        assert result["status"] == "ok"
        assert "# Cost Report" in result["report"]

    def test_get_costs_exception(self):
        """CostAuditor raises → returns error status."""
        with patch("api.routes.admin_dashboard.CostAuditor") as mock_cls:
            mock_auditor = MagicMock()
            mock_auditor.generate_report.side_effect = RuntimeError("DB error")
            mock_cls.return_value = mock_auditor
            result = get_costs()
        assert result["status"] == "error"
        assert "DB error" in result["report"]


# ── get_health_map ─────────────────────────────────────────────────────


class TestGetHealthMap:
    @pytest.mark.asyncio
    async def test_all_offline(self, monkeypatch):
        """No services configured → unconfigured / degraded status."""
        from core.config import settings

        monkeypatch.setattr(type(settings), "redis_url", property(lambda self: ""))
        monkeypatch.setattr(type(settings), "supabase_database_url", property(lambda self: ""))
        monkeypatch.setattr(settings, "_get_cached_secret", lambda k: "")

        result = await get_health_map()
        assert result["database"]["status"] == "degraded"
        assert result["redis"]["status"] == "degraded"
        assert result["cloudflare"]["status"] == "offline"
        assert result["render"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_all_healthy(self, monkeypatch):
        """All services configured → healthy status with live telemetry."""
        from core.config import settings

        monkeypatch.setattr(
            type(settings), "redis_url", property(lambda self: "rediss://redis.upstash.com")
        )
        monkeypatch.setattr(
            type(settings), "supabase_database_url", property(lambda self: "postgresql://db")
        )
        monkeypatch.setattr(
            settings, "_get_cached_secret", lambda k: "fake-token" if "CLOUDFLARE" in k else ""
        )

        result = await get_health_map()
        assert result["database"]["status"] == "healthy"
        assert result["redis"]["status"] == "healthy"
        assert result["cloudflare"]["status"] == "healthy"
        assert result["render"]["status"] == "healthy"
        assert "latency_ms" in result["database"]
        assert "latency_ms" in result["redis"]
        assert "live_uptime_seconds" in result["render"]


# ── trigger_deploy ─────────────────────────────────────────────────────


class TestTriggerDeploy:
    def test_trigger_deploy(self):
        """Deploy trigger FAILS CLOSED (501) until a deploy provider is configured.

        CONTRACT UPDATE (CI FIX 2026-09-16): the endpoint was deliberately
        hardened to always raise 501 Not Implemented ("fail closed until a real
        deployment provider is configured") — the old assertion expected the
        pre-hardening success payload and failed on every main-CI run since.
        """
        with pytest.raises(HTTPException) as excinfo:
            trigger_deploy()
        assert excinfo.value.status_code == 501
        assert "not configured" in str(excinfo.value.detail).lower()


# ── get_metrics ────────────────────────────────────────────────────────


class TestGetMetrics:
    def test_metrics_with_keys(self, monkeypatch):
        """All API keys set → all providers active."""
        from core.config import settings

        monkeypatch.setattr(settings, "_get_cached_secret", lambda k: "key1")
        result = get_metrics()
        assert "openrouter" in result["active_providers"]
        assert "gemini" in result["active_providers"]
        assert "groq" in result["active_providers"]
        assert "deepseek" in result["active_providers"]
        # বাংলা মন্তব্য: Wave-1 honesty fix-এর পরে psutil ব্যর্থ হলে মান সৎ None —
        # তাই এখানে "রিয়েল মান বা None" দুটোই গ্রহণযোগ্য (ভুয়া fallback আর নেই)।
        cpu_val = result["cpu_usage_percent"]
        assert cpu_val is None or cpu_val >= 0

    def test_metrics_no_keys(self, monkeypatch):
        """No API keys → falls back to ollama."""
        from core.config import settings

        monkeypatch.setattr(settings, "_get_cached_secret", lambda k: "")
        result = get_metrics()
        assert result["active_providers"] == ["ollama"]
        assert result["model_call_distribution"] == {"ollama": 100}

    def test_metrics_psutil_failure(self, monkeypatch):
        """psutil fails → honest None values (Wave-1: no fabricated fallbacks)."""
        from core.config import settings
        from core.observability.metrics_registry import reset_window_metrics

        # #2558 (order-dependence): একই pytest প্রসেসে আগের টেস্টগুলোর
        # instrumented request-গুলো module-level rolling window-এ জমে থাকে —
        # "idle process = honest 0.0" প্রিমিস যাচাই করতে হলে state রিসেট দরকার।
        reset_window_metrics()
        monkeypatch.setattr(
            settings,
            "_get_cached_secret",
            lambda k: "key1" if k == "OPENROUTER_API_KEY" else "",
        )
        # ISOLATION FIX (#2551 gate, full-tier red 36586150660 attempt 1+2):
        # ফুল স্যুটে এই টেস্টের আগে ~১৮০০টি টেস্ট চলে — আগের endpoint-টেস্টের
        # ObservabilityMiddleware রেকর্ড করা রিয়েল ট্রাফিক শেয়ার্ড গ্লোবালে
        # জমে: ৬০-সেকেন্ড rolling window (rps 2.817), metrics_engine.
        # latency_history (p50 6.4ms), collector _gauges (llm cost)। টেস্টটির
        # চুক্তি হলো "psutil ব্যর্থতা → সৎ None/0.0" — ট্রাফিক-গণিত নয়; তাই
        # idle-অবস্থা এখানেই hermetic ভাবে তৈরি করা হলো (fresh state swap —
        # monkeypatch টেস্ট-শেষে নিজেই ফেরত দেয়)।
        from collections import defaultdict, deque

        import core.observability.metrics_registry as _metrics_registry
        from core.monitoring import get_metrics_collector

        monkeypatch.setattr(_metrics_registry, "_window_events", deque())
        monkeypatch.setattr(_metrics_registry.metrics_engine, "latency_history", [])
        monkeypatch.setattr(get_metrics_collector(), "_gauges", defaultdict(float))
        import sys

        fake_psutil = MagicMock()
        fake_psutil.cpu_percent.side_effect = RuntimeError("psutil broken")
        with patch.dict(sys.modules, {"psutil": fake_psutil}):
            result = get_metrics()
        # CONTRACT UPDATE (Wave-1 honesty fix): আগে ভুয়া fallback (22.4/45.2/12.0)
        # ছিল — এখন psutil ব্যর্থ হলে সৎ None এবং GPU-র কল্পনাও বাদ।
        assert result["cpu_usage_percent"] is None
        assert result["memory_usage_percent"] is None
        assert result["gpu_usage_percent"] is None
        # CONTRACT UPDATE (CI red 36219425476, issue #1474 follow-up): the real
        # instrumentation pipeline (#1510) reports requests_per_second from the
        # genuine 60s rolling window — an idle process is an HONEST 0.0, not a
        # fabricated number, so None no longer applies to this field.
        # latency/cost/24h fields still have no data in a fresh process → None.
        assert result["requests_per_second"] == 0.0
        assert result["latency_p50_ms"] is None
        assert result["total_requests_24h"] is None
        assert result["cost_per_hour"] is None


# ── get_providers ──────────────────────────────────────────────────────


class TestGetProviders:
    # FIX (final-test ci-fixes): get_providers() এখন ASYNC এবং সৎ (honest) ডেটা রিপোর্ট করে —
    # ProviderRegistry-তে আসল traffic না থাকলে fallback-এ key-presence দেখায়।
    # পুরনো sync + hardcoded-contract test দুটো নতুন কন্ট্রাক্ট অনুযায়ী rewrite করা হলো।

    @staticmethod
    def _empty_registry(monkeypatch):
        """Force the honest fallback path (registry available but empty)."""
        from types import SimpleNamespace

        import services.dynamic_ai.orchestrator as orchestrator_module

        fake_orchestrator = SimpleNamespace(registry=SimpleNamespace(get_all_providers=lambda: {}))

        async def _fake_get_orchestrator():
            return fake_orchestrator

        monkeypatch.setattr(orchestrator_module, "get_ai_orchestrator", _fake_get_orchestrator)

    async def test_providers_with_keys(self, monkeypatch):
        """API keys set → fallback list marks those providers as configured/unknown."""
        from core.config import settings

        self._empty_registry(monkeypatch)
        monkeypatch.setattr(settings, "openrouter_api_key", "key", raising=False)
        monkeypatch.setattr(settings, "gemini_api_key", "key", raising=False)

        result = await get_providers()
        by_id = {p["id"]: p for p in result}

        assert {"openrouter", "gemini"} <= set(by_id)  # providers listed honestly
        assert by_id["openrouter"]["api_key_valid"] is True
        assert by_id["openrouter"]["status"] == "unknown"  # key present, no traffic yet
        assert by_id["gemini"]["api_key_valid"] is True

    async def test_providers_no_keys(self, monkeypatch):
        """No API keys → every fallback provider reported as not_configured (no fake data)."""
        import sys

        from core.config import settings

        # ISOLATION FIX (#2551): ফুল স্যুটে আগের টেস্টগুলো services.dynamic_ai
        # orchestrator/registry singleton-এ প্রোভাইডার রেজিস্টার করে রাখে —
        # ফলে get_providers-এর registry-নির্ভর প্রথম শাখা fallback-এর বদলে
        # দূষিত state পড়ে (deterministic assert False, ২ রান)। টেস্টের চুক্তি
        # হলো "keys নেই → fallback key-presence রিপোর্ট" — তাই orchestrator
        # ইমপোর্ট-ই বন্ধ (halt) করে নিশ্চিতভাবে fallback-পথে নামানো হলো
        # (sys.modules None = ImportError → get_providers-এর except-fallback)।
        monkeypatch.setitem(sys.modules, "services.dynamic_ai.orchestrator", None)
        for provider in (
            "openrouter_api_key",
            "gemini_api_key",
            "groq_api_key",
            "deepseek_api_key",
            "openai_api_key",
            # বাংলা মন্তব্য: mistral_api_key vault-backed lazy property ও env দুটো পথেই
            # যাতে কোনো পূর্ববর্তী টেস্টের অবশিষ্ট কী না লিক হয়, সেজন্য hermetic খালি করা হলো।
            "mistral_api_key",
        ):
            monkeypatch.setattr(settings, provider, "", raising=False)
        # #2558: _get_cached_secret-এ os.getenv precedence আছে — আগের টেস্ট
        # env-এ key রেখে গেলে setter-লেখা cache তাকে হারায়।
        # টেস্টের "no keys" প্রিমিস সত্য রাখতে env থেকেও key সরাতে হয়।
        for env_key in (
            "OPENROUTER_API_KEY",
            "GEMINI_API_KEY",
            "GROQ_API_KEY",
            "DEEPSEEK_API_KEY",
            "OPENAI_API_KEY",
            "MISTRAL_API_KEY",
        ):
            monkeypatch.delenv(env_key, raising=False)

        # FIX-2 (#2551, run 36590898621): vault-backed keys-এর জন্য শুধু
        # attribute/cache-সেট যথেষ্ট নয় — _get_cached_secret getter-এ
        # "12-factor: env ALWAYS take precedence" (config_secrets.py) — ফলে
        # যেকোনো MISTRAL_API_KEY-জাতীয় env/vault মান ফিরে আসত। ফাইলের নিজস্ব
        # প্রতিষ্ঠিত প্যাটার্ন (test_metrics_with_keys): getter-ই প্যাচ — সব
        # vault-backed key নিশ্চিতভাবে খালি।
        monkeypatch.setattr(
            settings,
            "_get_cached_secret",
            lambda k: "",
        )

        result = await get_providers()

        assert len(result) > 0
        assert all(p["status"] == "not_configured" for p in result)
        assert all(p["api_key_valid"] is False for p in result)
        assert all(p["latency_ms"] is None for p in result)  # no fabricated latency


# ── get_model_router / set_router_override ─────────────────────────────


class TestModelRouter:
    def test_get_model_router(self):
        """Returns default router state."""
        result = get_model_router()
        assert result["current_override"] is None
        assert result["ab_test_active"] is False
        assert "openrouter" in result["provider_order"]

    def test_set_router_override(self):
        """Sets override and returns success."""
        payload = RouterOverrideRequest(
            provider="openrouter", model="gpt-4o", remaining_requests=100
        )
        result = set_router_override(payload)
        assert result["status"] == "success"
        assert result["override"]["provider"] == "openrouter"
        assert result["override"]["remaining"] == 100


# ── get_codebase_export ────────────────────────────────────────────────


class TestCodebaseExport:
    @pytest.mark.asyncio
    async def test_export_success(self):
        """Export succeeds → returns markdown."""
        with patch(
            "api.routes.admin_dashboard.export_codebase_to_markdown",
            new_callable=AsyncMock,
        ) as mock_export:
            mock_export.return_value = "# Codebase\nSome markdown"
            result = await get_codebase_export()
        assert result["success"] is True
        assert "# Codebase" in result["markdown"]

    @pytest.mark.asyncio
    async def test_export_failure(self):
        """Export fails → raises HTTPException 500."""
        # বাংলা মন্তব্য: admin_dashboard এ সরাসরি import করা হয়েছে, তাই local namespace patch করতে হবে।
        with patch(
            "api.routes.admin_dashboard.export_codebase_to_markdown",
            new_callable=AsyncMock,
        ) as mock_export:
            mock_export.side_effect = RuntimeError("Export failed")
            with pytest.raises(HTTPException) as exc_info:
                await get_codebase_export()
        assert exc_info.value.status_code == 500


# ── load_cost_caps / save_cost_caps / get_cost_caps / update_cost_caps ─


class TestCostCaps:
    def test_load_cost_caps_creates_default(self, temp_cost_caps_file):
        """File doesn't exist → creates default caps."""
        caps = load_cost_caps()
        assert "default_cap" in caps
        assert caps["default_cap"] == 10.0
        assert os.path.exists(temp_cost_caps_file)

    def test_load_cost_caps_existing(self, temp_cost_caps_file):
        """File exists → loads from file."""
        with open(temp_cost_caps_file, "w") as f:
            json.dump({"default_cap": 50.0, "per_tenant": {"t1": 10.0}}, f)
        caps = load_cost_caps()
        assert caps["default_cap"] == 50.0
        assert caps["per_tenant"]["t1"] == 10.0

    def test_save_cost_caps(self, temp_cost_caps_file):
        """save_cost_caps writes to file."""
        caps = {"default_cap": 100.0, "per_tenant": {}}
        save_cost_caps(caps)
        with open(temp_cost_caps_file) as f:
            loaded = json.load(f)
        assert loaded == caps

    def test_get_cost_caps(self, temp_cost_caps_file):
        """get_cost_caps returns loaded caps."""
        result = get_cost_caps()
        assert "default_cap" in result

    def test_update_cost_caps(self, temp_cost_caps_file):
        """update_cost_caps merges and saves."""
        payload = {"new_cap": 200.0}
        result = update_cost_caps(payload)
        assert result["status"] == "success"
        assert result["caps"]["new_cap"] == 200.0
        assert result["caps"]["default_cap"] == 10.0  # original preserved


# ── get_env_etag ───────────────────────────────────────────────────────


class TestGetEnvEtag:
    def test_env_etag_redis_cached(self):
        """Redis has cached etag → returns it."""
        import core.services as app_mod

        mock_redis = MagicMock()
        mock_redis.configured = True
        mock_redis.get.return_value = "cached-etag"
        old = getattr(app_mod, "redis_queue", None)
        app_mod.redis_queue = mock_redis
        try:
            result = get_env_etag()
            assert result == "cached-etag"
        finally:
            app_mod.redis_queue = old

    def test_env_etag_no_redis_no_env_file(self):
        """No redis, no .env file → returns 'empty-env'."""
        import core.services as app_mod

        old = getattr(app_mod, "redis_queue", None)
        app_mod.redis_queue = None
        try:
            with patch("os.path.exists", return_value=False):
                result = get_env_etag()
            assert result == "empty-env"
        finally:
            app_mod.redis_queue = old

    def test_env_etag_redis_not_configured(self):
        """Redis exists but not configured → falls back to .env file."""
        import core.services as app_mod

        mock_redis = MagicMock()
        mock_redis.configured = False
        old = getattr(app_mod, "redis_queue", None)
        app_mod.redis_queue = mock_redis
        try:
            with patch("os.path.exists", return_value=False):
                result = get_env_etag()
            assert result == "empty-env"
        finally:
            app_mod.redis_queue = old


# ── _acquire_env_lock / _release_env_lock ──────────────────────────────


class TestEnvLock:
    def test_acquire_redis_lock(self):
        """Redis lock acquired → returns True."""
        import core.services as app_mod

        mock_redis = MagicMock()
        mock_redis.configured = True
        mock_redis.set_nx.return_value = True
        old = getattr(app_mod, "redis_queue", None)
        app_mod.redis_queue = mock_redis
        try:
            result = _acquire_env_lock()
            assert result is True
            mock_redis.set_nx.assert_called_once()
        finally:
            app_mod.redis_queue = old

    def test_acquire_redis_fails_fallback_file(self, tmp_path):
        """Redis lock fails → falls back to file lock."""
        import core.services as app_mod

        mock_redis = MagicMock()
        mock_redis.configured = True
        mock_redis.set_nx.side_effect = RuntimeError("redis down")
        old = getattr(app_mod, "redis_queue", None)
        app_mod.redis_queue = mock_redis
        lock_path = str(tmp_path / ".env.lock")
        try:
            result = _acquire_env_lock(lock_path=lock_path)
            assert result is True
            assert os.path.exists(lock_path)
        finally:
            app_mod.redis_queue = old
            if os.path.exists(lock_path):
                os.remove(lock_path)

    def test_acquire_file_exists(self, tmp_path):
        """File lock already exists → returns False."""
        lock_path = str(tmp_path / ".env.lock")
        with open(lock_path, "w") as f:
            f.write("locked")
        result = _acquire_env_lock(lock_path=lock_path)
        assert result is False

    def test_acquire_no_redis_file_lock(self, tmp_path):
        """No redis → uses file lock."""
        import core.services as app_mod

        old = getattr(app_mod, "redis_queue", None)
        app_mod.redis_queue = None
        lock_path = str(tmp_path / ".env.lock")
        try:
            result = _acquire_env_lock(lock_path=lock_path)
            assert result is True
        finally:
            app_mod.redis_queue = old
            if os.path.exists(lock_path):
                os.remove(lock_path)

    def test_release_lock_redis(self):
        """Release lock with redis configured."""
        import core.services as app_mod

        mock_redis = MagicMock()
        mock_redis.configured = True
        old = getattr(app_mod, "redis_queue", None)
        app_mod.redis_queue = mock_redis
        try:
            _release_env_lock()
            mock_redis._request.assert_called_once_with("DEL", "lock:env_write")
        finally:
            app_mod.redis_queue = old

    def test_release_lock_no_redis(self, tmp_path):
        """Release lock without redis → tries to remove file."""
        import core.services as app_mod

        old = getattr(app_mod, "redis_queue", None)
        app_mod.redis_queue = None
        lock_path = str(tmp_path / ".env.lock")
        with open(lock_path, "w") as f:
            f.write("locked")
        try:
            _release_env_lock(lock_path=lock_path)
            assert not os.path.exists(lock_path)
        finally:
            app_mod.redis_queue = old


# ── logs_stream ────────────────────────────────────────────────────────


class TestLogsStream:
    def test_logs_stream_no_log_file(self):
        """No log file exists → returns streaming response."""
        with patch("os.path.exists", return_value=False):
            result = logs_stream()
        assert result is not None
        assert result.media_type == "text/event-stream"

    def test_logs_stream_with_log_file(self, tmp_path):
        """Log file exists → yields log lines."""
        log_file = tmp_path / "app.log"
        log_file.write_text("line1\nline2\nline3\n")
        with (
            patch(
                "os.path.exists",
                side_effect=lambda p: p == str(log_file) or p == "logs/app.log",
            ),
            patch("builtins.open", create=True) as mock_open,
        ):
            mock_open.return_value = MagicMock(
                __enter__=MagicMock(
                    return_value=MagicMock(
                        readlines=MagicMock(return_value=["line1\n", "line2\n", "line3\n"]),
                        readline=MagicMock(return_value=""),
                        seek=MagicMock(),
                        close=MagicMock(),
                    )
                ),
                __exit__=MagicMock(return_value=False),
            )
            result = logs_stream()
        assert result is not None

    def test_logs_stream_log_generator_cancellation(self, tmp_path):
        """Log generator handles CancelledError."""
        import api.routes.admin_dashboard as mod

        async def mock_generator():
            yield "data: test\n\n"
            raise asyncio.CancelledError()

        with patch.object(mod, "StreamingResponse") as mock_sr:
            mock_sr.return_value = MagicMock()
            logs_stream()
