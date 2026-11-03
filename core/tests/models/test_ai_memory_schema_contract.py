"""Hermetic contract tests for the Supabase ``ai_memory`` Phase C SQL (Task 7-b).

These tests never touch a database (sqlite cannot represent pgvector and the
SQLAlchemy engine is never connected). They lock three contracts:

1. The canonical SQL file exists and contains every required Phase C element
   (guarded table, extension, RLS + owner-scoped policies, HNSW index,
   updated_at trigger, retention function, pg_cron hook example).
2. The SQLAlchemy model ``models.ai_memory.AIMemory`` column set is exactly the
   SQL contract column set (they drifted historically — the ORM module used to
   crash on import and describe a table nobody used; see
   docs/database/AI_MEMORY_SCHEMA_AUDIT.md §1.1/§10).
3. The embedding dimension is the single canonical 384 everywhere (model
   constant ↔ every ``vector(N)`` occurrence in the SQL).

Run (from ``backend/``)::

    TESTING=true ENV=test \\
    TEST_DATABASE_URL="sqlite+aiosqlite:///./test.db" \\
    DATABASE_URL="postgresql://u:p@db.example.com:5432/supremeai" \\
    .venv/bin/python -m pytest tests/models/test_ai_memory_schema_contract.py -q
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# Settings is fail-fast; mirror the CI/test environment before any app import
# (setdefault only — never override a real deployment's variables).
os.environ.setdefault("TESTING", "true")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("TEST_DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("DATABASE_URL", "postgresql://u:p@db.example.com:5432/supremeai")

import sqlglot  # noqa: E402
from sqlglot import exp  # noqa: E402

from models.ai_memory import (  # noqa: E402
    EMBEDDING_DIMENSIONS,
    HAS_PGVECTOR_TYPE,
    AIMemory,
)

SQL_PATH = Path(__file__).resolve().parents[2] / "database" / "supabase" / "ai_memory_phase_c.sql"
SQL_TEXT = SQL_PATH.read_text(encoding="utf-8")

# Comments would weaken marker assertions — strip SQL line comments once.
_SQL_NO_COMMENTS = re.sub(r"(?m)^\s*--.*$", "", SQL_TEXT)

MODEL_COLUMNS = {col.name for col in AIMemory.__table__.columns}


# ─────────────────────────────────────────────────────────────────────────────
# Contract 1 — required SQL elements
# ─────────────────────────────────────────────────────────────────────────────
def test_sql_file_exists_at_canonical_path() -> None:
    assert SQL_PATH.is_file(), f"canonical SQL missing: {SQL_PATH}"


def test_sql_contains_phase_c_core_markers() -> None:
    required = [
        "CREATE EXTENSION IF NOT EXISTS vector",
        "CREATE TABLE IF NOT EXISTS ai_memory",
        "ENABLE ROW LEVEL SECURITY",
        "REVOKE ALL ON ai_memory FROM anon",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ai_memory TO authenticated",
        # HNSW vector index (baseline m=16 / ef_construction=64, cosine ops)
        "USING hnsw (embedding vector_cosine_ops)",
        "m = 16",
        "ef_construction = 64",
        # updated_at trigger
        "CREATE TRIGGER trg_ai_memory_updated_at",
        "BEFORE UPDATE ON ai_memory",
        # retention function + documented cron hook (the pg_cron example is a
        # comment block by design, so it is checked against the raw text)
        "CREATE OR REPLACE FUNCTION fn_ai_memory_retention_cleanup(p_days int DEFAULT NULL)",
        # RPC reconciliation (audit §1.3): live callers ↔ database functions
        "CREATE OR REPLACE FUNCTION match_memories(",
        "p_user_id",
        "match_experiences",
    ]
    missing = [marker for marker in required if marker not in _SQL_NO_COMMENTS]
    assert not missing, f"canonical SQL missing required markers: {missing}"
    assert "cron.schedule(" in SQL_TEXT, "commented pg_cron hook example missing"


def test_sql_is_idempotent_guaranteed() -> None:
    """Re-runnability: guarded DDL only.

    The single permitted bare ``CREATE INDEX`` is the HNSW statement nested in
    the DO-block that only fires when no ANN index exists (SQL Part 5) — the
    guard, not the syntax, makes it idempotent.
    """
    assert "CREATE TABLE IF NOT EXISTS ai_memory" in _SQL_NO_COMMENTS
    bare = re.findall(r"(?im)^\s*CREATE\s+INDEX\s+(?!IF NOT EXISTS)(\w+)", _SQL_NO_COMMENTS)
    assert bare == ["ix_ai_memory_embedding_hnsw"], (
        f"unexpected bare CREATE INDEX statements: {bare}"
    )
    # IVFFlat alternative stays documented (commented) as the fallback path
    assert "IF NOT EXISTS ix_ai_memory_embedding_ivfflat" in SQL_TEXT


def test_sql_parses_with_sqlglot_postgres_dialect() -> None:
    """Whole file must parse under the postgres dialect (PG-specific statements
    degrade to opaque Command nodes — acceptable; ParseError is not)."""
    statements = [s for s in sqlglot.parse(SQL_TEXT, read="postgres") if s is not None]
    assert len(statements) >= 20, "unexpectedly few statements parsed"

    create_tables = [s for s in statements if isinstance(s, exp.Create) and s.kind == "TABLE"]
    assert len(create_tables) == 1, "expected exactly one CREATE TABLE statement"
    schema = create_tables[0].find(exp.Schema)
    assert schema is not None, "CREATE TABLE has no parseable column schema"
    parsed_columns = {c.name for c in schema.expressions}
    assert parsed_columns == MODEL_COLUMNS, (
        f"sqlglot-parsed columns {sorted(parsed_columns)} != model columns {sorted(MODEL_COLUMNS)}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Contract 2 — model ↔ SQL column-set equality
# ─────────────────────────────────────────────────────────────────────────────
def _sql_create_table_block() -> str:
    match = re.search(
        r"CREATE TABLE IF NOT EXISTS ai_memory\s*\((.*?)\n\);",
        _SQL_NO_COMMENTS,
        re.DOTALL,
    )
    assert match is not None, "CREATE TABLE IF NOT EXISTS ai_memory block not found"
    return match.group(1)


def test_sql_column_set_matches_sqlalchemy_model() -> None:
    block = _sql_create_table_block()
    sql_columns: set[str] = set()
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        name_match = re.match(r"([a-z_]+)\s", stripped)
        if name_match:
            sql_columns.add(name_match.group(1))

    assert sql_columns, "no columns parsed from SQL CREATE TABLE block"
    assert sql_columns == MODEL_COLUMNS, (
        f"column drift:\n  SQL-only: {sorted(sql_columns - MODEL_COLUMNS)}"
        f"\n  model-only: {sorted(MODEL_COLUMNS - sql_columns)}"
    )
    # the live writer contract (audit §1.2) in both representations
    expected_writer_columns = {
        "id",
        "user_id",
        "session_id",
        "agent_type",
        "task_type",
        "content",
        "summary",
        "agent_id",
        "memory_type",
        "importance_score",
        "metadata",
        "embedding",
        "created_at",
        "updated_at",
    }
    assert sql_columns == expected_writer_columns


def test_model_has_no_legacy_dead_contract() -> None:
    """Regression guards for the audited dead-model defects (audit §1.1)."""
    assert "content_type" not in MODEL_COLUMNS, "content_type never existed in the live DB"
    assert list(AIMemory.__table__.foreign_keys) == [], (
        "user_id must not carry a ForeignKey (no users ORM table exists; audit §3)"
    )
    # attribute stays `metadata_` (column name is `metadata`)
    assert AIMemory.metadata_.name == "metadata"


# ─────────────────────────────────────────────────────────────────────────────
# Contract 3 — single embedding dimension (384)
# ─────────────────────────────────────────────────────────────────────────────
def test_embedding_dimension_is_single_and_canonical() -> None:
    # executable surface only — historical comments may mention other widths
    dims_in_sql = set(re.findall(r"vector\((\d+)\)", _SQL_NO_COMMENTS, re.IGNORECASE))
    assert dims_in_sql == {str(EMBEDDING_DIMENSIONS)}, (
        f"mixed vector dimensions in executable SQL: {dims_in_sql}; canonical is {EMBEDDING_DIMENSIONS}"
    )
    assert f"vector({EMBEDDING_DIMENSIONS})" in _SQL_NO_COMMENTS


def test_model_imports_and_exposes_dimension_constant() -> None:
    assert EMBEDDING_DIMENSIONS == 384
    # importable with OR without the optional pgvector package
    embedding_col = AIMemory.__table__.columns["embedding"]
    assert embedding_col.nullable is True
    type_name = type(embedding_col.type).__name__
    if HAS_PGVECTOR_TYPE:
        assert type_name == "Vector", f"expected pgvector Vector type, got {type_name}"
    else:  # pragma: no cover - slim envs without pgvector
        assert type_name == "_VectorPlaceholder", f"expected placeholder type, got {type_name}"
        assert embedding_col.type.__class__.cache_ok is True


# ─────────────────────────────────────────────────────────────────────────────
# Contract 4 — RLS owner scoping
# ─────────────────────────────────────────────────────────────────────────────
def test_rls_policies_are_owner_scoped_and_anon_denied() -> None:
    policy_roles = re.findall(
        r"CREATE POLICY (\w+) ON ai_memory\s+FOR \w+ TO (\w+)", _SQL_NO_COMMENTS
    )
    assert dict(policy_roles) == {
        "ai_memory_select_own": "authenticated",
        "ai_memory_insert_own": "authenticated",
        "ai_memory_update_own": "authenticated",
        "ai_memory_delete_own": "authenticated",
    }, f"unexpected policy/role set: {policy_roles}"

    # 5 scoping predicates: SELECT/DELETE USING, INSERT WITH CHECK,
    # UPDATE USING + WITH CHECK
    scoping = _SQL_NO_COMMENTS.count("auth.uid()::text = user_id")
    assert scoping == 5, f"expected 5 auth.uid() scoping predicates, found {scoping}"

    # anon is explicitly denied at the table level (RPC EXECUTE grants to anon
    # are intentional parity with migration 001 — RLS still applies inside those
    # SECURITY INVOKER functions, so anon matches zero rows)
    assert "REVOKE ALL ON ai_memory FROM anon" in _SQL_NO_COMMENTS
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON ai_memory TO authenticated" in _SQL_NO_COMMENTS


def test_retention_function_default_and_guards() -> None:
    assert "COALESCE(p_days, 180)" in _SQL_NO_COMMENTS, "retention default must be 180 days"
    assert "SECURITY DEFINER" in _SQL_NO_COMMENTS
    assert (
        "REVOKE EXECUTE ON FUNCTION fn_ai_memory_retention_cleanup(int) FROM PUBLIC"
        in _SQL_NO_COMMENTS
    )
    assert "DELETE FROM ai_memory" in _SQL_NO_COMMENTS


# ─────────────────────────────────────────────────────────────────────────────
# Contract 4 — match_memories RPC tenant isolation (issue #1689, CRITICAL)
# ─────────────────────────────────────────────────────────────────────────────
def test_match_memories_rpc_tenant_isolation_mandatory() -> None:
    """Issue #1689: `p_user_id` must be a MANDATORY argument with strict
    per-user equality — the old `DEFAULT NULL` + `(p_user_id IS NULL OR …)`
    contract let a single missing argument return EVERY user's memories."""
    block = re.search(
        r"CREATE OR REPLACE FUNCTION match_memories\((.*?)\$\$;",
        SQL_TEXT,
        re.DOTALL,
    )
    assert block is not None, "match_memories definition missing from canonical SQL"
    body = block.group(1)

    # 1. p_user_id has no DEFAULT NULL → PostgREST call without it fails closed
    assert re.search(r"p_user_id\s+text\s*\)", body) is not None, (
        "p_user_id must be declared WITHOUT a DEFAULT (mandatory argument)"
    )
    assert "DEFAULT NULL" not in body, "match_memories must not default p_user_id to NULL"

    # 2. strict tenant equality; the only NULL-user scope is the explicit
    #    agent-internal sentinel (agent-own learning rows have user_id IS NULL)
    assert "m.user_id = p_user_id" in body, "strict tenant equality predicate missing"
    assert "p_user_id IS NULL OR" not in body, "the old tenant-bypass predicate remains"
    assert "__agent_internal__" in body, "agent-scope sentinel predicate missing"

    # 3. anon must NOT have EXECUTE on the tenant RPC (unauthenticated callers
    #    carry no tenant identity)
    grants = re.findall(r"GRANT EXECUTE ON FUNCTION match_memories\([^;]*?\) TO ([^;]+);", SQL_TEXT)
    assert grants, "match_memories EXECUTE grant missing"
    for grant in grants:
        assert "anon" not in grant, f"anon must not EXECUTE match_memories: {grant}"
