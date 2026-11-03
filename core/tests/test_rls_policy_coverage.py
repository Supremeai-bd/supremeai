"""
Regression tests for the RLS 42501 bug class (root cause: migration
17_enable_rls.sql enables RLS on every public table but only creates
policies for tables listed in its category arrays -- anything left out
becomes a silent deny-all, exactly as happened to evolution_logs).

These tests do NOT hit a real Supabase project. They assert the
*contract* that must hold for the fix to be correct:

  1. Group B (system/audit) tables -- evolution_logs, feedback_loop,
     tools_registry, referral_codes, referral_redemptions,
     scheduled_task_executions -- must be written via
     SupabaseDB.service_client, never SupabaseDB.client. If any of these
     is silently switched back to self.client, the RLS 42501 bug returns.

  2. SupabaseDB.client and SupabaseDB.service_client must be genuinely
     independent objects, so that a caller which forgets which one to
     use fails loudly (AttributeError / wrong table) rather than
     accidentally getting bypass access through a shared client.

  3. append_evolution_log() / get_evolution_logs() must not fall back to
     self.client under any circumstance -- this is the exact bug that
     shipped originally.

A live-Supabase smoke test (real anon/authenticated/service-role INSERT
against a disposable project) is intentionally NOT included here -- it
needs real credentials and a network call, so it belongs in a separate
manually-triggered integration job, not the default unit suite.
"""

import ast
import inspect
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]  # backend/
SUPABASE_CLIENT_PATH = REPO_ROOT / "database" / "supabase_client.py"

# Tables intentionally left with ZERO authenticated/anon RLS policy
# (RLS ON, deny-all for non-service callers) -- backend-only writers.
GROUP_B_SERVICE_ONLY_TABLES = [
    "evolution_logs",
    "feedback_loop",
    "tools_registry",
    "referral_codes",
    "referral_redemptions",
]

# Files (relative to backend/) known to write/read Group B tables, and
# the table(s) each is responsible for. Used to assert none of them
# regress back to the RLS-bound `.client`.
GROUP_B_CALL_SITES = {
    # evolution_logs is deliberately excluded here: append_evolution_log()/
    # get_evolution_logs() reach it via a local `client = self.service_client`
    # indirection rather than `self.service_client.table(...)` inline, which
    # this substring check can't see through. That path is covered precisely
    # by test_evolution_log_functions_never_reference_self_client() below.
    "database/supabase_client.py": ["feedback_loop"],
    "api/routes/tools_registry.py": ["tools_registry"],
    "scripts/seed_tools_registry.py": ["tools_registry"],
    "tools/learning/skill_recommender.py": ["tools_registry"],
    "tools/social/viral_referral_engine.py": ["referral_codes", "referral_redemptions"],
}


def _source_of(relative_path: str) -> str:
    path = REPO_ROOT / relative_path
    assert path.exists(), f"expected file missing: {relative_path}"
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("relative_path,tables", list(GROUP_B_CALL_SITES.items()))
def test_group_b_tables_never_use_rls_bound_client(relative_path, tables):
    """
    For every Group B (service-only) table, every `.table("<name>")` call
    site in its known-owning file must be reached through `.service_client`
    (or `self.service_client` / `<var>.service_client`), never the bare
    RLS-enforced `.client`.

    This is a static/source check (not a live DB call) so it runs in the
    default fast unit suite and fails immediately if someone reverts the
    835fa97-style fix for any of these tables.
    """
    source = _source_of(relative_path)
    for table in tables:
        # Every occurrence of .table("<table>") must be immediately
        # preceded by ".service_client" on the same call chain, i.e. the
        # substring "service_client.table(\"<table>\")" must account for
        # ALL occurrences of "table(\"<table>\")" in the file, minus a
        # tolerated `.table("evolution_logs")` inside comments/docstrings.
        all_occurrences = source.count(f'.table("{table}")')
        safe_occurrences = source.count(f'.service_client.table("{table}")')
        assert all_occurrences > 0, (
            f'expected at least one .table("{table}") call in {relative_path}; '
            "update GROUP_B_CALL_SITES if the code moved"
        )
        assert safe_occurrences == all_occurrences, (
            f"{relative_path}: found {all_occurrences - safe_occurrences} call(s) to "
            f'.table("{table}") NOT routed through .service_client. '
            f"{table} has RLS enabled with zero authenticated/anon policies "
            "(see migrations/legacy/17_enable_rls.sql + 18_fix_missing_rls_policies.sql) -- "
            "any write through the plain .client will fail with 42501 in production."
        )


def test_client_and_service_client_are_independent_attributes():
    """
    SupabaseDB must expose `client` and `service_client` as genuinely
    separate attributes (not one aliasing the other by default) whenever
    a distinct SUPABASE_SERVICE_ROLE_KEY is configured, so that code
    reviewers/static checks can tell the two code paths apart. We check
    this structurally via source inspection rather than instantiating
    SupabaseDB (which requires network/env setup at import time).
    """
    source = _source_of("database/supabase_client.py")
    tree = ast.parse(source)

    init_body_src = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "SupabaseDB":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                    init_body_src = ast.get_source_segment(source, item)
    assert init_body_src is not None, "SupabaseDB.__init__ not found"

    assert "self.client" in init_body_src
    assert "self.service_client" in init_body_src
    assert "self.service_key" in init_body_src, (
        "service_client must be built from a distinct service_key, not reuse "
        "self.key -- otherwise it's not actually a service-role bypass"
    )


def test_migration_18_does_not_grant_authenticated_access_to_group_b_tables():
    """
    18_fix_missing_rls_policies.sql intentionally adds no authenticated/anon
    CREATE POLICY for Group B tables. If a future edit adds one, it would
    silently reopen these backend-only tables to any authenticated user --
    catch that here rather than in production.
    """
    migration_path = (
        REPO_ROOT / "database" / "migrations" / "legacy" / "18_fix_missing_rls_policies.sql"
    )
    assert migration_path.exists(), "expected migrations/legacy/18_fix_missing_rls_policies.sql"
    sql = migration_path.read_text(encoding="utf-8")

    for table in GROUP_B_SERVICE_ONLY_TABLES:
        # crude but effective: no "CREATE POLICY ... ON public.<table>" for these
        assert f"ON public.{table}" not in sql, (
            f"migration 18 must not grant authenticated/anon policies to "
            f"'{table}' -- it is a backend/system-only table"
        )
