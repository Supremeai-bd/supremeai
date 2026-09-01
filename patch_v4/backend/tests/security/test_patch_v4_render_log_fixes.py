"""PATCH v4 regression tests — Render production log fixes.

Each test guards one of the 5 defects identified in the 2026-08-30 Render
production log audit:

1. ReadOnlySqlTransaction on CREATE TABLE → pooled_pg.execute_ddl()
2. hitl_admin router import (get_tenant_db)
3. AsyncSession concurrency in /configs/refresh (isce)
4. automation_executions table missing from bootstrap
5. Memory pressure from eager singletons in core.services

These tests are intentionally hermetic — they don't require Postgres,
Redis, or Firestore. They verify code structure, not runtime behaviour.
"""

from __future__ import annotations

import importlib
import inspect
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# FIX 1: pooled_pg.execute_ddl exists and routes through the WRITER URL
# ─────────────────────────────────────────────────────────────────────────────


def test_pooled_pg_execute_ddl_function_exists():
    """execute_ddl must be a top-level callable on pooled_pg."""
    from core.persistence import pooled_pg

    assert hasattr(pooled_pg, "execute_ddl"), "pooled_pg.execute_ddl must exist (PATCH v4)"
    assert callable(pooled_pg.execute_ddl), "pooled_pg.execute_ddl must be callable"


def test_pooled_pg_resolve_writer_dsn_does_not_return_pooler():
    """_resolve_writer_dsn must NEVER return SUPABASE_DATABASE_URL_POOLER.

    This is the structural guarantee that closes the ReadOnlySqlTransaction
    defect. If a future PR re-introduces pooler fallback here, this test
    fails loudly.
    """
    from core.persistence import pooled_pg

    with patch.dict(
        os.environ,
        {
            "SUPABASE_DATABASE_URL_POOLER": "postgresql://pooler.example.com/db",
            "SUPABASE_DATABASE_URL": "",  # direct URL unset
            "SUPABASE_DATABASE_URL_WRITER": "",  # writer unset
        },
        clear=False,
    ):
        dsn = pooled_pg._resolve_writer_dsn()
        assert dsn is None, (
            "_resolve_writer_dsn must NOT fall back to the pooler URL — "
            "the pooler is read-only in production. Got: " + str(dsn)
        )


def test_pooled_pg_resolve_writer_dsn_prefers_writer_env():
    """If SUPABASE_DATABASE_URL_WRITER is set, _resolve_writer_dsn returns it."""
    from core.persistence import pooled_pg

    with patch.dict(
        os.environ,
        {
            "SUPABASE_DATABASE_URL_WRITER": "postgresql://writer.example.com/db",
            "SUPABASE_DATABASE_URL": "postgresql://direct.example.com/db",
            "SUPABASE_DATABASE_URL_POOLER": "postgresql://pooler.example.com/db",
        },
        clear=False,
    ):
        dsn = pooled_pg._resolve_writer_dsn()
        assert dsn == "postgresql://writer.example.com/db"


def test_pooled_pg_execute_ddl_swallows_runtime_error_when_no_writer():
    """When the writer pool is unavailable, execute_ddl must NOT raise.

    Callers (memory_service, checkpoint_manager) rely on this to silently
    fall back to SQLite without escalating to a CRITICAL silent-pattern.
    """
    from core.persistence import pooled_pg

    # Force writer pool unavailable
    with patch.object(pooled_pg, "_get_writer_pool", return_value=None):
        # Must not raise
        pooled_pg.execute_ddl("CREATE TABLE IF NOT EXISTS foo (id int);")


def test_pooled_pg_execute_ddl_not_decorated_with_error_bus():
    """execute_ddl must NOT be wrapped in @with_error_bus.

    The original bug was that `execute()` was wrapped, so DDL failures
    fired `error_event_bus` events which the silent-pattern detector
    escalated to CRITICAL. execute_ddl must remain unwrapped so DDL
    failures on read-only replicas do NOT escalate.
    """
    from core.persistence import pooled_pg

    # The wrapped form from @with_error_bus has a `__wrapped__` attribute
    # pointing to the original function. execute_ddl must NOT have it.
    assert not hasattr(pooled_pg.execute_ddl, "__wrapped__") or (
        # Allow if explicitly marked, but log a warning
        getattr(pooled_pg.execute_ddl, "_patch_v4_unwrapped", False) is True
    ), (
        "pooled_pg.execute_ddl must NOT be decorated with @with_error_bus — "
        "that re-introduces the CRITICAL silent-pattern escalation."
    )


# ─────────────────────────────────────────────────────────────────────────────
# FIX 2: hitl_admin router imports get_tenant_db from the correct module
# ─────────────────────────────────────────────────────────────────────────────


def test_hitl_admin_router_imports_resolve():
    """Importing api.routes.hitl_admin must succeed without ImportError.

    The original bug: `from core.tenant_db import get_tenant_db` raised
    ImportError on every boot, making the entire hitl_admin router dead.
    """
    # Force fresh import to catch any cached state from other tests
    for mod in ("api.routes.hitl_admin",):
        sys.modules.pop(mod, None)
    importlib.import_module("api.routes.hitl_admin")


def test_hitl_admin_router_uses_api_deps_get_tenant_db():
    """hitl_admin must import get_tenant_db from api.deps, not core.tenant_db."""
    import api.routes.hitl_admin as hitl_admin

    src = inspect.getsource(hitl_admin)
    assert "from api.deps import get_tenant_db" in src, (
        "hitl_admin must import get_tenant_db from api.deps (PATCH v4). "
        "Found source does not contain the expected import line."
    )
    assert "from core.tenant_db import" not in src, (
        "hitl_admin must NOT import from core.tenant_db — that shim doesn't "
        "expose get_tenant_db."
    )


# ─────────────────────────────────────────────────────────────────────────────
# FIX 3: /configs/refresh uses sequential awaits, not asyncio.gather
# ─────────────────────────────────────────────────────────────────────────────


def test_admin_configs_refresh_does_not_use_gather():
    """refresh_system_configs must NOT use asyncio.gather on a shared session.

    The original bug: `asyncio.gather(6 × sync_from_db(db))` triggered
    sqlalchemy.exc.InvalidRequestError (isce) in production.
    """
    import api.routes.admin as admin_module
    import ast

    src = inspect.getsource(admin_module.refresh_system_configs)
    # Walk the AST and assert there is no Call to asyncio.gather (excluding
    # docstrings / comments).
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if (
                node.func.attr == "gather"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "asyncio"
            ):
                raise AssertionError(
                    "refresh_system_configs must NOT use asyncio.gather — "
                    "it triggers isce (concurrent operations on a shared "
                    "AsyncSession). PATCH v4."
                )
    # Must have sequential awaits
    assert "await ModelRegistry.sync_from_db(db)" in src
    assert "await economic_opt.sync_from_db(db)" in src
    assert "await sync_health_middleware(db)" in src


# ─────────────────────────────────────────────────────────────────────────────
# FIX 4: automation_executions is in get_bootstrap_statements
# ─────────────────────────────────────────────────────────────────────────────


def test_bootstrap_statements_include_automation_executions():
    """get_bootstrap_statements must include CREATE TABLE automation_executions.

    The original bug: the table was missing from the boot-time DDL list,
    so cleanup_automation_executions failed with UndefinedTableError every
    60 seconds.
    """
    from database.supabase_client import SupabaseDB

    statements = SupabaseDB.get_bootstrap_statements()
    joined = " ".join(statements)
    assert "CREATE TABLE IF NOT EXISTS automation_executions" in joined, (
        "bootstrap_statements must include CREATE TABLE automation_executions (PATCH v4)."
    )
    assert "CREATE TABLE IF NOT EXISTS automation_execution_attempts" in joined, (
        "bootstrap_statements must include CREATE TABLE automation_execution_attempts (PATCH v4)."
    )


def test_bootstrap_schema_does_not_use_pooler_for_ddl():
    """bootstrap_schema must NOT try SUPABASE_DATABASE_URL_POOLER for DDL."""
    import database.supabase_client as sc

    src = inspect.getsource(sc.SupabaseDB.bootstrap_schema)
    assert "for candidate_url in (pooler_url" not in src, (
        "bootstrap_schema must NOT iterate over (pooler_url, db_url) — "
        "the pooler is read-only for DDL. PATCH v4."
    )


# ─────────────────────────────────────────────────────────────────────────────
# FIX 5: core.services uses lazy singletons
# ─────────────────────────────────────────────────────────────────────────────


def test_core_services_module_has_no_eager_singleton_assignments():
    """core.services must NOT eagerly construct singletons at module top level.

    The original bug: `redis_queue = UpstashRedisQueue()` etc. ran at import
    time, pushing RSS to 90.78% on Render free tier before any request.
    """
    import core.services as svc

    # The 7 lazy singletons must be absent from module __dict__ — they should
    # only resolve through __getattr__ → _SINGLETON_FACTORIES.
    eager_names = {
        "redis_queue",
        "admin_god",
        "model_router",
        "parallel_router",
        "intent_clf",
        "intent_parser",
        "experience_db",
    }
    for name in eager_names:
        assert name not in vars(svc), (
            f"core.services must NOT eagerly assign {name} at module level — "
            "use get_{name}() factory + __getattr__ dispatch instead. PATCH v4."
        )


def test_core_services_has_singleton_factory_registry():
    """_SINGLETON_FACTORIES must exist and contain all 7 factories."""
    import core.services as svc

    assert hasattr(svc, "_SINGLETON_FACTORIES"), (
        "core.services must expose _SINGLETON_FACTORIES (PATCH v4)."
    )
    expected = {
        "redis_queue",
        "admin_god",
        "model_router",
        "parallel_router",
        "intent_clf",
        "intent_parser",
        "experience_db",
    }
    assert expected.issubset(svc._SINGLETON_FACTORIES.keys()), (
        f"_SINGLETON_FACTORIES missing keys: {expected - set(svc._SINGLETON_FACTORIES.keys())}"
    )


def test_core_services_lazy_factory_returns_same_instance():
    """Each get_*() factory must return the same instance on repeat calls (lru_cache)."""
    import core.services as svc

    # Patch each underlying class with a lightweight stub so the test is hermetic
    with patch("core.messaging.upstash_redis_queue.UpstashRedisQueue") as RedisQ:
        RedisQ.return_value = object()
        svc.get_redis_queue.cache_clear()
        a = svc.get_redis_queue()
        b = svc.get_redis_queue()
        assert a is b, "get_redis_queue must return the same cached instance"
        svc.get_redis_queue.cache_clear()


# ─────────────────────────────────────────────────────────────────────────────
# Smoke test — importing core.services must be cheap (no singleton construction)
# ─────────────────────────────────────────────────────────────────────────────


def test_importing_core_services_does_not_construct_singletons(monkeypatch):
    """Importing core.services must NOT trigger UpstashRedisQueue() / AdminGodLayer() / etc.

    This is the structural guarantee that closes the memory-pressure defect.
    We re-import the module fresh and assert none of the heavy constructors
    were called.
    """
    constructed: list[str] = []

    # Stub each heavy class to record construction instead of doing real work.
    import sys

    # Save originals so we can restore them after the test
    saved = {}

    try:
        # Eject cached core.services so the next import is fresh
        sys.modules.pop("core.services", None)

        # Stub the heavy modules BEFORE core.services tries to import them.
        # core.services uses lazy imports inside factory functions, so the
        # stubs will only be hit if eager construction is happening.
        import types

        def make_recording_stub(name):
            mod = types.ModuleType(name)

            class _Stub:
                def __init__(self, *args, **kwargs):
                    constructed.append(name)

            mod.UpstashRedisQueue = _Stub
            mod.AdminGodLayer = _Stub
            mod.ModelRouter = _Stub
            mod.ParallelCloudRouter = _Stub
            mod.IntentClassifier = _Stub
            mod.IntentParser = _Stub
            mod.ExperienceDatabase = _Stub
            return mod

        for mod_name in (
            "core.messaging.upstash_redis_queue",
            "admin.god",
            "brain.model_router",
            "brain.parallel_cloud_router",
            "core.intent",
            "adaptive_engine.intent_parser",
            "adaptive_engine.experience_db",
        ):
            sys.modules[mod_name] = make_recording_stub(mod_name)

        # Fresh import — this is the moment we are auditing
        import core.services  # noqa: F401

        assert constructed == [], (
            "Importing core.services must NOT construct any singleton. "
            "Found constructions: " + ", ".join(constructed)
        )
    finally:
        # Restore
        sys.modules.pop("core.services", None)
        for mod_name in (
            "core.messaging.upstash_redis_queue",
            "admin.god",
            "brain.model_router",
            "brain.parallel_cloud_router",
            "core.intent",
            "adaptive_engine.intent_parser",
            "adaptive_engine.experience_db",
        ):
            sys.modules.pop(mod_name, None)
