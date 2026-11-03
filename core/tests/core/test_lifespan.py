"""Tests for FastAPI Application Lifespan Manager.

এই মডিউলে টেস্ট করা হয়:
- Startup infrastructure initialization
- Database pool initialization
- Redis connection verification
- OpenTelemetry tracing setup
- Orchestrator initialization
- Background task startup
- Graceful shutdown of all services
"""

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.lifespan import app_lifespan
from core.startup.api_key_tables import ensure_api_key_tables


async def _run_lifespan(mock_app) -> None:
    """Lifespan context manager চালাও।"""
    async with app_lifespan(mock_app):
        pass


def _apply_common_patches(stack: contextlib.ExitStack) -> dict:
    """সব common patches একটি ExitStack-এ enter করে mocks-এর dict রিটার্ন করো।

    বাংলা মন্তব্য: মডিউলারাইজড lifespan-এর নতুন পাথ অনুযায়ী patch টার্গেটগুলো আপডেট করা হয়েছে।
    - core.lifespan (মূল entrypoint)
    - core.startup.services (initialize_independent_services)
    - core.shutdown (shutdown_services)
    """
    mocks = {}

    mocks["validate"] = stack.enter_context(
        patch("core.lifespan.StartupValidator.validate", new_callable=AsyncMock)
    )
    mocks["reliability"] = stack.enter_context(
        patch("core.lifespan.ReliabilityController.initialize", new_callable=AsyncMock)
    )
    # setup_tracing locally imported — সঠিক patch path ব্যবহার করতে হবে
    stack.enter_context(patch("core.observability.telemetry.setup_tracing", return_value=None))
    mocks["init_db_pool"] = stack.enter_context(
        patch("core.startup.services.init_db_pool", new_callable=AsyncMock)
    )
    mocks["config_refresh"] = stack.enter_context(
        patch("core.startup.services.config_cache.refresh_async", new_callable=AsyncMock)
    )
    mocks["redis_manager"] = stack.enter_context(patch("core.startup.services.redis_manager"))
    # Redis ping-এর জন্য mock return value সেট করো
    mock_ping = AsyncMock()
    mocks["redis_manager"].client.ping = mock_ping
    mocks["redis_manager"].close = AsyncMock()
    mocks["orchestrator"] = stack.enter_context(patch("core.lifespan.Orchestrator"))
    stack.enter_context(patch("core.startup.services.maintenance_pipeline.start_monitoring"))
    stack.enter_context(patch("database.supabase_client.SupabaseDB.bootstrap_schema"))

    def _closing_create_task(coro, **kwargs):
        # বাংলা মন্তব্য: coroutine বন্ধ না করলে asyncio "coroutine was never
        # awaited" RuntimeWarning দেয়, কারণ create_task() mocked থাকায়
        # কখনো schedule/await হয় না।
        coro.close()
        return MagicMock()

    mocks["create_task"] = stack.enter_context(
        patch("asyncio.create_task", side_effect=_closing_create_task)
    )
    stack.enter_context(patch("asyncio.to_thread", side_effect=lambda f, *a, **kw: f()))

    mocks["services_lifespan"] = stack.enter_context(patch("core.lifespan.services", create=True))
    mocks["services_startup"] = stack.enter_context(
        patch("core.startup.services.services", create=True)
    )
    mocks["services_shutdown"] = stack.enter_context(patch("core.shutdown.services", create=True))

    # Mock httpx.AsyncClient so it doesn't create real connections
    mocks["httpx_client"] = stack.enter_context(
        patch("core.lifespan.httpx.AsyncClient", return_value=AsyncMock())
    )

    # Services HTTP client mock (legacy, but keep for compatibility)
    mocks["services_lifespan"].global_http_client = mocks["httpx_client"].return_value
    mocks["services_startup"].global_http_client = mocks["httpx_client"].return_value
    mocks["services_shutdown"].global_http_client = mocks["httpx_client"].return_value

    return mocks


class TestEnsureAPIKeyTables:
    """Tests for ensure_api_key_tables function."""

    @pytest.mark.anyio
    async def test_creates_tables_successfully(self):
        """API key tables সফলভাবে তৈরি হয় কিনা পরীক্ষা করো।"""
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_transaction = AsyncMock()

        mock_pool.acquire = AsyncMock(return_value=mock_conn)
        mock_pool.release = AsyncMock()
        mock_conn.transaction = MagicMock(return_value=mock_transaction)
        mock_conn.execute = AsyncMock()

        with patch("core.startup.api_key_tables.get_db_pool", return_value=mock_pool):
            await ensure_api_key_tables()

        mock_pool.acquire.assert_called_once()
        mock_pool.release.assert_called_once()

    @pytest.mark.anyio
    async def test_handles_db_error(self):
        """Database error — ensure_api_key_tables exception propagate করে কিনা পরীক্ষা করো।"""
        mock_pool = AsyncMock()
        mock_pool.acquire = AsyncMock(side_effect=Exception("DB error"))

        with patch("core.startup.api_key_tables.get_db_pool", return_value=mock_pool):
            # ensure_api_key_tables internally exception propagate করে
            # lifespan startup-এ এটি ধরে defensive mode-এ চালু হয়
            with pytest.raises(Exception, match="DB error"):
                await ensure_api_key_tables()


class TestAppLifespan:
    """Tests for app_lifespan context manager."""

    @pytest.mark.anyio
    async def test_startup_validates(self):
        """Startup validation call করা হয় কিনা পরীক্ষা করো।"""
        mock_app = MagicMock()
        mock_app.state = MagicMock()
        mock_app.state.subsystem_status = {}

        with contextlib.ExitStack() as stack:
            mocks = _apply_common_patches(stack)

            await _run_lifespan(mock_app)

            mocks["validate"].assert_called_once()

    @pytest.mark.anyio
    async def test_startup_skips_db_for_sqlite(self):
        """SQLite database-এ PostgreSQL pool init skip করা হয় কিনা পরীক্ষা করো।"""
        mock_app = MagicMock()
        mock_app.state = MagicMock()
        mock_app.state.subsystem_status = {}

        with contextlib.ExitStack() as stack:
            mocks = _apply_common_patches(stack)
            mock_settings_lifespan = stack.enter_context(patch("core.lifespan.settings"))
            mock_settings_lifespan.supabase_database_url = "sqlite+aiosqlite:///:memory:"
            mock_settings_services = stack.enter_context(patch("core.startup.services.settings"))
            mock_settings_services.supabase_database_url = "sqlite+aiosqlite:///:memory:"

            await _run_lifespan(mock_app)

            # SQLite হলে PostgreSQL pool initialize করা উচিত নয়
            mocks["init_db_pool"].assert_not_called()

    @pytest.mark.anyio
    async def test_shutdown_closes_http_client(self):
        """Shutdown-এ HTTP client বন্ধ করা হয় কিনা পরীক্ষা করো।"""
        mock_app = MagicMock()
        mock_app.state = MagicMock()
        mock_app.state.subsystem_status = {}

        with contextlib.ExitStack() as stack:
            mocks = _apply_common_patches(stack)
            # The HTTP client used in shutdown will be the one returned by httpx.AsyncClient()
            mock_http_client = mocks["httpx_client"].return_value

            mock_pool = AsyncMock()
            mock_pool.close = AsyncMock()
            mock_get_pool = stack.enter_context(
                patch("core.shutdown.get_db_pool", new_callable=AsyncMock)
            )
            mock_get_pool.return_value = mock_pool

            mock_orch = MagicMock()
            mock_orch.stop = AsyncMock()
            mocks["orchestrator"].return_value = mock_orch

            await _run_lifespan(mock_app)

            mock_http_client.aclose.assert_called_once()

    @pytest.mark.anyio
    async def test_shutdown_cancels_background_tasks(self):
        """Background tasks shutdown-এ cancel করা হয় কিনা পরীক্ষা করো।"""
        mock_app = MagicMock()
        mock_app.state = MagicMock()
        mock_app.state.subsystem_status = {}

        with contextlib.ExitStack() as stack:
            mocks = _apply_common_patches(stack)

            stack.enter_context(
                patch(
                    "core.shutdown.shutdown_services",
                    new=AsyncMock(side_effect=asyncio.CancelledError),
                )
            )

            mock_pool = AsyncMock()
            mock_pool.close = AsyncMock()
            mock_get_pool = stack.enter_context(
                patch("core.shutdown.get_db_pool", new_callable=AsyncMock)
            )
            mock_get_pool.return_value = mock_pool

            mock_orch = MagicMock()
            mock_orch.stop = AsyncMock()
            mocks["orchestrator"].return_value = mock_orch

            # CancelledError expected result হওয়া উচিত
            with pytest.raises(asyncio.CancelledError):
                await _run_lifespan(mock_app)

    @pytest.mark.anyio
    async def test_handles_teardown_errors(self):
        """Teardown errors সত্ত্বেও crash না করা পরীক্ষা করো।"""
        mock_app = MagicMock()
        mock_app.state = MagicMock()
        mock_app.state.subsystem_status = {}

        with contextlib.ExitStack() as stack:
            _apply_common_patches(stack)

            # shutdown.py uses `from core.cache.redis_manager import redis_manager`
            mock_redis_shutdown = stack.enter_context(patch("core.shutdown.redis_manager"))
            mock_redis_shutdown.close = AsyncMock(side_effect=Exception("Redis error"))

            # ISOLATION/CONTRACT FIX (#2551, run 36595123376): মডুলারাইজড
            # lifespan রি-ফ্যাক্টরের পর থেকে shutdown পথ আর subsystem_status
            # লেখে না — status এখন startup-time snapshot (লেখক: core/startup/
            # services.py:108 ও api/server.py:46)। init_db_pool সফল মক হওয়ায়
            # db-র সঠিক মান "up"। এই টেস্টের বাস্তব চুক্তি: teardown-এর
            # redis-exception লাইফস্প্যান ক্র্যাশ করায় না + startup-status
            # অক্ষত থাকে। (আগের assertion shutdown-time db-"down" আশা করত —
            # বর্তমান কোডে সেই লেখার জায়গাই নেই, তাই টেস্টটি সর্বদা লাল হত।)
            await _run_lifespan(mock_app)

            assert mock_app.state.subsystem_status["db"] == "up"


class TestLifespanSubsystemStatus:
    """Tests for subsystem status tracking."""

    @pytest.mark.anyio
    async def test_subsystem_status_defaults(self):
        """Subsystem status সঠিকভাবে initialize হয় কিনা পরীক্ষা করো।"""
        mock_app = MagicMock()
        mock_app.state = MagicMock()
        mock_app.state.subsystem_status = {}

        with contextlib.ExitStack() as stack:
            mocks = _apply_common_patches(stack)
            # Make sure it's not sqlite so it calls init_db_pool
            mock_settings = MagicMock()
            mock_settings.supabase_database_url = "postgresql://dummy"
            stack.enter_context(patch("core.startup.services.settings", mock_settings))
            # DB failure simulate করো
            mocks["init_db_pool"].side_effect = Exception("DB failed")
            mocks["redis_manager"].client.ping.side_effect = Exception("Redis failed")

            await _run_lifespan(mock_app)

            # Subsystem status set হয়েছে কিনা চেক করো
            assert hasattr(mock_app.state, "subsystem_status")
            assert mock_app.state.subsystem_status["db"] in ("down", "optional_offline")
            assert mock_app.state.subsystem_status["redis"] in ("down", "optional_offline")
