import asyncio
import functools
import os
import time
from collections.abc import Callable
from typing import Any

# psycopg2 মডিউল না থাকলে যেন ডিরেক্ট ক্লায়েন্ট ইনিশিয়ালাইজেশন ক্র্যাশ না করে, সে জন্য সেফ ইমপোর্ট করা হলো।
try:
    import psycopg2
except ImportError:
    psycopg2 = None
from core.logging_config import logger

try:
    from supabase import Client, create_client
except ImportError:
    Client = Any  # type: ignore[misc,assignment]
    create_client = None

from core.config import settings


def _supabase_retry_decorator(func: Callable) -> Callable:
    """Decorator to retry Supabase operations with exponential backoff and consolidated logging."""

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # বাংলা মন্তব্য: কিছু মেথড (যেমন evolution_logs সংক্রান্ত) শুধুমাত্র service_client
        # ব্যবহার করে, self.client না থাকলেও সেগুলো চালানো উচিত — তাই উভয় ক্লায়েন্ট চেক করা হচ্ছে।
        has_any_client = bool(self.client) or bool(getattr(self, "service_client", None))
        if not has_any_client and func.__name__ not in (
            "__init__",
            "_derive_supabase_url",
            "bootstrap_schema",
            "get_bootstrap_statements",
            "_is_schema_cache_error",
            "_execute_response_with_retry",
        ):
            # বাংলা: আগে এখানে "None if ... else None" ছিল — দুই branch-ই None রিটার্ন করত,
            return None

        max_retries = 3
        for attempt in range(max_retries):
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                # Handle schema cache error via existing logic if possible, or just retry
                if attempt < max_retries - 1:
                    sleep_time = 2**attempt
                    logger.warning(
                        f"Supabase operation '{func.__name__}' failed: {e}. Retrying in {sleep_time}s..."
                    )
                    # FIX: original used time.sleep() which blocks the entire event loop
                    # when called from an async route. Detect async context and use
                    # asyncio.sleep() instead — but we can't `await` from a sync function.
                    # Workaround: detect running event loop; if found, switch to asyncio.run
                    # of an async sleep. This is still blocking but at least yields to
                    # the OS scheduler. The CORRECT fix is to make callers wrap with
                    # asyncio.to_thread() — see ADMIN_TASKS.md for migration plan.
                    try:
                        asyncio.get_running_loop()
                        # We're inside an event loop — can't use time.sleep without blocking.
                        # Use loop.run_in_executor to push the sleep to a thread pool.
                        import concurrent.futures

                        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                            future = ex.submit(time.sleep, sleep_time)
                            future.result(timeout=sleep_time + 1)
                    except RuntimeError:
                        # No running event loop — sync context, time.sleep is fine
                        time.sleep(sleep_time)
                else:
                    logger.warning(
                        f"Supabase operation '{func.__name__}' failed after {max_retries} retries: {e}"
                    )
                    # Return safe fallbacks based on method name prefix
                    if func.__name__.startswith("get_"):
                        return None
                    if func.__name__.startswith("is_"):
                        return False
                    return None
        return None

    return wrapper


def _apply_retries_to_public_methods(cls):
    for attr_name, attr_value in vars(cls).items():
        if (
            callable(attr_value)
            and not attr_name.startswith("_")
            and attr_name not in ("get_bootstrap_statements", "bootstrap_schema")
        ):
            setattr(cls, attr_name, _supabase_retry_decorator(attr_value))
    return cls


@_apply_retries_to_public_methods
class SupabaseDB:
    """
    Supabase client wrapper for SupremeAI 2.0.
    Manages github_repos, system_config, and feature_flags.
    """

    def __init__(self):
        self.url = settings.supabase_url or self._derive_supabase_url(
            os.environ.get("SUPABASE_DATABASE_URL")
            or os.environ.get("SUPABASE_DATABASE_URL_POOLER")
        )
        self.key = settings.supabase_key
        self.client: Client | None = None

        if self.url and self.key and self.url.startswith(("http://", "https://")):
            try:
                self.client = create_client(self.url, self.key)
                logger.info("Initialized Supabase Client")
            except Exception as e:
                logger.warning(
                    f"Supabase Client initialization failed: {e}. Falling back to Mock Supabase Client."
                )
                try:
                    self.client = create_client("https://mock.supabase.co", "mock-key")
                except Exception as mock_err:
                    # বাংলা মন্তব্য: নেস্টেড এক্সেপশন শ্যাডোইং ফিক্স ও ক্লায়েন্ট ফেইলিউর লগ যোগ
                    logger.error(f"Fallback mock Supabase Client creation failed: {mock_err}")
                    self.client = None
        else:
            logger.warning(
                "SUPABASE_URL or SUPABASE_KEY invalid/missing. Running in offline/mock mode."
            )

        # বাংলা মন্তব্য: RLS-protected backend-only/audit টেবিল (যেমন evolution_logs)-এ
        # লিখতে হলে service_role key প্রয়োজন, যা RLS bypass করে। এই client কখনো
        # ইউজার Authorization ফরওয়ার্ড করবে না — শুধু ব্যাকএন্ড সিস্টেম রাইটের জন্য ব্যবহৃত হবে।
        self.service_key = settings.supabase_service_key
        self.service_client: Client | None = None
        if self.url and self.service_key and self.url.startswith(("http://", "https://")):
            try:
                self.service_client = create_client(self.url, self.service_key)
                logger.info("Initialized Supabase Service-Role Client (RLS bypass, backend-only)")
            except Exception as e:
                logger.warning(
                    f"Supabase Service Client initialization failed: {e}. Falling back to primary client."
                )
                self.service_client = self.client
        else:
            # সার্ভিস কী আলাদাভাবে সেট না থাকলে (ফলব্যাক কেসে supabase_service_key ==
            # supabase_key হয়ে যায়), তাই এখানে primary client-কেই ফলব্যাক ধরা হলো।
            self.service_client = self.client

    @staticmethod
    def _derive_supabase_url(database_url: str | None) -> str | None:
        if not database_url:
            return None
        try:
            from urllib.parse import urlparse

            parsed = urlparse(database_url)
            hostname = parsed.hostname or ""
            if hostname.endswith(".supabase.co"):
                if hostname.startswith("db."):
                    return f"https://{hostname[3:]}"
                return f"https://{hostname}"
        except Exception as exc:
            # বাংলা মন্তব্য: exception এবং debug দুটো আলাদা কল না করে একটি warning-এ consolidate করা হলো
            logger.warning(f"Failed to derive Supabase URL from DATABASE_URL: {exc}")
        return None

    @classmethod
    def get_bootstrap_statements(cls) -> list[str]:
        return [
            "CREATE TABLE IF NOT EXISTS outbox_events ("
            "id BIGSERIAL PRIMARY KEY,"
            "target_db TEXT NOT NULL,"
            "query_text TEXT NOT NULL,"
            "idempotency_key TEXT UNIQUE,"
            "created_at TEXT,"
            "processed_at TIMESTAMP WITH TIME ZONE"
            ");",
            "CREATE INDEX IF NOT EXISTS idx_outbox_events_unprocessed ON outbox_events (id) WHERE processed_at IS NULL;",
            "CREATE TABLE IF NOT EXISTS system_config ("
            "id SERIAL PRIMARY KEY,"
            "key TEXT NOT NULL UNIQUE,"
            "value TEXT,"
            "category TEXT,"
            "created_at TIMESTAMP WITH TIME ZONE NOT NULL,"
            "updated_at TIMESTAMP WITH TIME ZONE"
            ");",
            "CREATE TABLE IF NOT EXISTS skills ("
            "id UUID PRIMARY KEY DEFAULT gen_random_uuid(),"
            "name TEXT NOT NULL UNIQUE,"
            "category TEXT,"
            "prompt_template TEXT,"
            "parameters_schema JSONB,"
            "success_rate FLOAT DEFAULT 0.0,"
            "usage_count INTEGER DEFAULT 0,"
            "version TEXT DEFAULT '1.0.0',"
            "is_active BOOLEAN DEFAULT true,"
            "created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),"
            "updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),"
            "metadata JSONB DEFAULT '{}'"
            ");",
            "CREATE TABLE IF NOT EXISTS guardrails ("
            "id UUID PRIMARY KEY DEFAULT gen_random_uuid(),"
            "layer_name TEXT NOT NULL UNIQUE,"
            "rule_definition JSONB NOT NULL,"
            "priority INTEGER DEFAULT 0,"
            "is_active BOOLEAN DEFAULT true,"
            "created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),"
            "updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"
            ");",
            "CREATE TABLE IF NOT EXISTS provider_configs ("
            "id UUID PRIMARY KEY DEFAULT gen_random_uuid(),"
            "provider_name TEXT NOT NULL UNIQUE,"
            "rpm INTEGER DEFAULT 999999,"
            "tpm INTEGER DEFAULT 999999,"
            "rpd INTEGER DEFAULT 999999,"
            "priority INTEGER DEFAULT 0,"
            "is_active BOOLEAN DEFAULT true,"
            "created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),"
            "updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"
            ");",
            "CREATE TABLE IF NOT EXISTS feature_flags ("
            "id SERIAL PRIMARY KEY,"
            "feature_name TEXT NOT NULL UNIQUE,"
            "enabled BOOLEAN DEFAULT FALSE,"
            "allowed_users TEXT[],"
            "rollout_percentage INTEGER DEFAULT 100,"
            "created_at TIMESTAMP WITH TIME ZONE NOT NULL,"
            "updated_at TIMESTAMP WITH TIME ZONE"
            ");",
            "CREATE TABLE IF NOT EXISTS github_repos ("
            "id SERIAL PRIMARY KEY,"
            "repo_name TEXT NOT NULL,"
            "owner TEXT NOT NULL,"
            "description TEXT,"
            "language TEXT,"
            "created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"
            ");",
            "CREATE TABLE IF NOT EXISTS ai_model_behavior ("
            "id SERIAL PRIMARY KEY,"
            "model_name TEXT NOT NULL UNIQUE,"
            "behavior JSONB,"
            "created_at TIMESTAMP WITH TIME ZONE NOT NULL,"
            "updated_at TIMESTAMP WITH TIME ZONE"
            ");",
            "CREATE TABLE IF NOT EXISTS user_preferences ("
            "id SERIAL PRIMARY KEY,"
            "user_id TEXT NOT NULL UNIQUE,"
            "preferences JSONB,"
            "created_at TIMESTAMP WITH TIME ZONE NOT NULL,"
            "updated_at TIMESTAMP WITH TIME ZONE"
            ");",
            "CREATE TABLE IF NOT EXISTS usage_metrics ("
            "id SERIAL PRIMARY KEY,"
            "tenant_id TEXT,"
            "metric_name TEXT NOT NULL,"
            "metric_value NUMERIC,"
            "collected_at TIMESTAMP WITH TIME ZONE NOT NULL"
            ");",
            "CREATE TABLE IF NOT EXISTS tenant_limits ("
            "id SERIAL PRIMARY KEY,"
            "tenant_id TEXT NOT NULL UNIQUE,"
            "org_name TEXT,"
            "billing_tier TEXT,"
            "requests_per_minute INTEGER,"
            "max_tokens_per_day BIGINT,"
            "max_concurrent_sessions INTEGER,"
            "stripe_customer_id TEXT,"
            "notes TEXT,"
            "created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),"
            "updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"
            ");",
            "CREATE TABLE IF NOT EXISTS tenant_usage ("
            "id SERIAL PRIMARY KEY,"
            "tenant_id TEXT NOT NULL,"
            "date DATE NOT NULL,"
            "requests_count INTEGER DEFAULT 0,"
            "tokens_used BIGINT DEFAULT 0,"
            "cost_incurred NUMERIC DEFAULT 0.0,"
            "created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()"
            ");",
            "CREATE TABLE IF NOT EXISTS tools_registry ("
            "id TEXT PRIMARY KEY,"
            "name TEXT NOT NULL,"
            "file_path TEXT,"
            "category TEXT,"
            "dependencies TEXT[],"
            "cost_per_call NUMERIC DEFAULT 0.0,"
            "description TEXT,"
            "config_schema JSONB,"
            "status TEXT DEFAULT 'active',"
            "created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),"
            "updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"
            ");",
            "CREATE TABLE IF NOT EXISTS markdown_exports ("
            "id SERIAL PRIMARY KEY,"
            "job_id TEXT NOT NULL UNIQUE,"
            "repo_url TEXT,"
            "time_range TEXT,"
            "status TEXT,"
            "timestamp NUMERIC,"
            "created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()"
            ");",
            "CREATE TABLE IF NOT EXISTS referral_codes ("
            "id SERIAL PRIMARY KEY,"
            "code TEXT NOT NULL UNIQUE,"
            "referrer_id TEXT NOT NULL,"
            "status TEXT DEFAULT 'active',"
            "created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),"
            "expires_at NUMERIC,"
            "redeemed_count INTEGER DEFAULT 0,"
            "fraud_score NUMERIC DEFAULT 0.0"
            ");",
            "CREATE TABLE IF NOT EXISTS referral_redemptions ("
            "id SERIAL PRIMARY KEY,"
            "code TEXT NOT NULL,"
            "new_user_id TEXT,"
            "referrer_id TEXT,"
            "reward_amount NUMERIC,"
            "credits_awarded INTEGER,"
            "metadata JSONB,"
            "created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()"
            ");",
            "CREATE TABLE IF NOT EXISTS credit_ledger ("
            "id SERIAL PRIMARY KEY,"
            "tx_id TEXT NOT NULL UNIQUE,"
            "user_id TEXT NOT NULL,"
            "amount NUMERIC NOT NULL,"
            "reason TEXT,"
            "timestamp NUMERIC,"
            "balance_after NUMERIC,"
            "created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()"
            ");",
            "CREATE TABLE IF NOT EXISTS credit_wallets ("
            "id SERIAL PRIMARY KEY,"
            "user_id TEXT NOT NULL UNIQUE,"
            "balance NUMERIC DEFAULT 0.0,"
            "updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"
            ");",
            "CREATE TABLE IF NOT EXISTS domain_profiles ("
            "id SERIAL PRIMARY KEY,"
            "domain_name TEXT NOT NULL,"
            "profile JSONB,"
            "created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()"
            ");",
            "CREATE TABLE IF NOT EXISTS provider_benchmarks ("
            "id SERIAL PRIMARY KEY,"
            "provider_name TEXT NOT NULL,"
            "latency_ms INTEGER,"
            "cost NUMERIC,"
            "created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()"
            ");",
            "CREATE TABLE IF NOT EXISTS trading_portfolio (id SERIAL PRIMARY KEY,portfolio JSONB,updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());",
            "CREATE TABLE IF NOT EXISTS conversations ("
            "id SERIAL PRIMARY KEY,"
            "session_id TEXT NOT NULL UNIQUE,"
            "messages JSONB,"
            "updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"
            ");",
            "CREATE TABLE IF NOT EXISTS learned_facts ("
            "id TEXT PRIMARY KEY,"
            "content JSONB,"
            "tags JSONB,"
            "created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()"
            ");",
            "CREATE TABLE IF NOT EXISTS task_history ("
            "id SERIAL PRIMARY KEY,"
            "task TEXT NOT NULL,"
            "approach TEXT NOT NULL,"
            "result TEXT NOT NULL,"
            "success BOOLEAN NOT NULL,"
            "created_at TIMESTAMP WITH TIME ZONE NOT NULL"
            ");",
            "CREATE TABLE IF NOT EXISTS skill_proposals ("
            "id SERIAL PRIMARY KEY,"
            "skill_name TEXT NOT NULL,"
            "source_pattern TEXT,"
            "generated_code TEXT,"
            "status TEXT DEFAULT 'proposed',"
            "created_at TIMESTAMP WITH TIME ZONE NOT NULL,"
            "registered_at TIMESTAMP WITH TIME ZONE"
            ");",
            "CREATE TABLE IF NOT EXISTS feedback_loop ("
            "id SERIAL PRIMARY KEY,"
            "session_id TEXT NOT NULL,"
            "query TEXT,"
            "retrieved_chunks TEXT,"
            "user_rating REAL,"
            "adjusted BOOLEAN DEFAULT FALSE,"
            "created_at TIMESTAMP WITH TIME ZONE NOT NULL"
            ");",
            "CREATE TABLE IF NOT EXISTS evolution_logs (id SERIAL PRIMARY KEY,event JSONB NOT NULL,created_at TIMESTAMP WITH TIME ZONE NOT NULL);",
            # বাংলা মন্তব্য: ডিস্ট্রিবিউটেড এবং সার্ভারলেস ব্যালেন্স ট্র্যাকিং ও অপটিমিস্টিক লক সাপোর্টের জন্য স্কিমা বুটস্ট্র্যাপ
            "CREATE TABLE IF NOT EXISTS user_wallets ("
            "id UUID PRIMARY KEY DEFAULT gen_random_uuid(),"
            "user_id VARCHAR(255) NOT NULL UNIQUE,"
            "balance_usd NUMERIC(10, 6) NOT NULL DEFAULT 0.000000,"
            "monthly_allowance_usd NUMERIC(10, 6) NOT NULL DEFAULT 0.000000,"
            "version INTEGER NOT NULL DEFAULT 1,"
            "created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),"
            "updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"
            ");",
            "CREATE TABLE IF NOT EXISTS transaction_ledger ("
            "id UUID PRIMARY KEY DEFAULT gen_random_uuid(),"
            "transaction_id VARCHAR(255) NOT NULL UNIQUE,"
            "user_id VARCHAR(255) NOT NULL,"
            "amount_usd NUMERIC(10, 6) NOT NULL,"
            "transaction_type VARCHAR(50) NOT NULL,"
            "description VARCHAR(500),"
            "timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()"
            ");",
            "CREATE INDEX IF NOT EXISTS idx_user_time ON transaction_ledger (user_id, timestamp);",
            # বাংলা মন্তব্য: স্বয়ংক্রিয় স্কিল ইভোলিউশন ফিটনেস ট্র্যাকিং ও প্রপোজাল ম্যানেজমেন্ট DDL
            "CREATE TABLE IF NOT EXISTS skill_fitness ("
            "id UUID PRIMARY KEY DEFAULT gen_random_uuid(),"
            "skill_name VARCHAR(255) NOT NULL UNIQUE,"
            "success_count INTEGER NOT NULL DEFAULT 0,"
            "failure_count INTEGER NOT NULL DEFAULT 0,"
            "fitness_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,"
            "last_run_at TIMESTAMP WITH TIME ZONE,"
            "version INTEGER NOT NULL DEFAULT 1,"
            "created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),"
            "updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"
            ");",
            "CREATE TABLE IF NOT EXISTS code_proposals ("
            "id UUID PRIMARY KEY DEFAULT gen_random_uuid(),"
            "proposal_id VARCHAR(255) NOT NULL UNIQUE,"
            "skill_name VARCHAR(255) NOT NULL,"
            "generated_code TEXT NOT NULL,"
            "ast_validated BOOLEAN NOT NULL DEFAULT FALSE,"
            "ci_passed BOOLEAN NOT NULL DEFAULT FALSE,"
            "status VARCHAR(50) NOT NULL DEFAULT 'proposed',"
            "metadata_json JSONB DEFAULT '{}'::jsonb,"
            "version INTEGER NOT NULL DEFAULT 1,"
            "created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"
            ");",
            "CREATE INDEX IF NOT EXISTS idx_proposal_status ON code_proposals (status);",
            "CREATE INDEX IF NOT EXISTS idx_skill_fitness_score ON skill_fitness (fitness_score DESC);",
            # বাংলা মন্তব্য: pgvector এক্সটেনশন সক্রিয় করা এবং learned_facts টেবিলে ভেক্টর এমবেডিং ও RPC ফাংশন যুক্ত করা।
            "CREATE EXTENSION IF NOT EXISTS vector;",
            "ALTER TABLE learned_facts ADD COLUMN IF NOT EXISTS embedding vector(1536);",
            """
            CREATE OR REPLACE FUNCTION match_learned_facts (
                query_embedding vector(1536),
                match_threshold float,
                match_count int
            )
            RETURNS TABLE (
                id text,
                content jsonb,
                tags jsonb,
                similarity float
            )
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RETURN QUERY
                SELECT
                    learned_facts.id,
                    learned_facts.content,
                    learned_facts.tags,
                    1 - (learned_facts.embedding <=> query_embedding) AS similarity
                FROM learned_facts
                WHERE 1 - (learned_facts.embedding <=> query_embedding) > match_threshold
                ORDER BY learned_facts.embedding <=> query_embedding
                LIMIT match_count;
            END;
            $$;
            """,
            # গ্যাপ ফিক্স: skills/core_knowledge_qa.py এখন real pgvector সার্চ করে — এই টেবিল ও RPC
            # ফাংশনটি সেই সার্চের backing store। namespace কলাম দিয়ে role-based ফিল্টারিং (Admin
            # বনাম Standard_User) নিশ্চিত হয়।
            "CREATE TABLE IF NOT EXISTS knowledge_base ("
            "id VARCHAR(255) PRIMARY KEY,"
            "namespace VARCHAR(255) NOT NULL,"
            "content TEXT NOT NULL,"
            "source VARCHAR(500) NOT NULL,"
            "embedding vector(1536),"
            "created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"
            ");",
            "CREATE INDEX IF NOT EXISTS idx_knowledge_base_namespace ON knowledge_base (namespace);",
            """
            CREATE OR REPLACE FUNCTION match_knowledge_base (
                query_embedding vector(1536),
                match_namespace text,
                match_threshold float,
                match_count int
            )
            RETURNS TABLE (
                id text,
                content text,
                source text,
                similarity float
            )
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RETURN QUERY
                SELECT
                    knowledge_base.id,
                    knowledge_base.content,
                    knowledge_base.source,
                    1 - (knowledge_base.embedding <=> query_embedding) AS similarity
                FROM knowledge_base
                WHERE knowledge_base.namespace = match_namespace
                  AND 1 - (knowledge_base.embedding <=> query_embedding) > match_threshold
                ORDER BY knowledge_base.embedding <=> query_embedding
                LIMIT match_count;
            END;
            $$;
            """,
            # PATCH v4 (2026-08-30): Add automation_executions tables to bootstrap.
            # Production logs showed `relation "automation_executions" does not exist`
            # every cleanup cycle. Migration a1b2c3d4e5f6 exists but is never applied
            # at boot (no `alembic upgrade head` in startup). Boot-time DDL is the
            # only path that actually runs in production, so we mirror the migration
            # DDL here. Column types match `models/automation_execution.py` to avoid
            # Alembic drift if/when migrations are wired into deploy.
            "CREATE TABLE IF NOT EXISTS automation_executions ("
            "id VARCHAR(36) PRIMARY KEY,"
            "event_id VARCHAR(36) NOT NULL,"
            "idempotency_key VARCHAR(100),"
            "workflow_key VARCHAR(100) NOT NULL,"
            "provider VARCHAR(50) NOT NULL,"
            "status VARCHAR(50) DEFAULT 'PENDING',"
            "attempt INTEGER DEFAULT 1,"
            "started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),"
            "completed_at TIMESTAMP WITH TIME ZONE,"
            "duration_ms INTEGER,"
            "http_status INTEGER,"
            "external_execution_id VARCHAR(100),"
            "trace_id VARCHAR(100),"
            "error_code VARCHAR(100),"
            "error_message VARCHAR(1024),"
            "created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"
            ");",
            "CREATE INDEX IF NOT EXISTS idx_automation_executions_event_id ON automation_executions (event_id);",
            "CREATE INDEX IF NOT EXISTS idx_automation_executions_idempotency_key ON automation_executions (idempotency_key);",
            "CREATE INDEX IF NOT EXISTS idx_automation_executions_workflow_key ON automation_executions (workflow_key);",
            "CREATE INDEX IF NOT EXISTS idx_automation_executions_status ON automation_executions (status);",
            "CREATE INDEX IF NOT EXISTS idx_automation_executions_trace_id ON automation_executions (trace_id);",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_automation_workflow_idempotency ON automation_executions (workflow_key, idempotency_key);",
            "CREATE TABLE IF NOT EXISTS automation_execution_attempts ("
            "id VARCHAR(36) PRIMARY KEY,"
            "execution_id VARCHAR(36) NOT NULL REFERENCES automation_executions(id) ON DELETE CASCADE,"
            "attempt INTEGER DEFAULT 1 NOT NULL,"
            "status VARCHAR(50) DEFAULT 'PENDING',"
            "started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),"
            "completed_at TIMESTAMP WITH TIME ZONE,"
            "duration_ms INTEGER,"
            "http_status INTEGER,"
            "error_code VARCHAR(100),"
            "error_message VARCHAR(1024),"
            "created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"
            ");",
            "CREATE INDEX IF NOT EXISTS idx_automation_execution_attempts_execution_id ON automation_execution_attempts (execution_id);",
        ]

    def bootstrap_schema(self):
        """PATCH v4 (2026-08-30): Route DDL through the WRITER URL only.

        Previous behaviour tried `SUPABASE_DATABASE_URL_POOLER` first — that
        endpoint is read-only in our production Supabase tenant, so every
        `CREATE TABLE IF NOT EXISTS` raised `ReadOnlySqlTransaction` and
        cascaded to CRITICAL silent-pattern escalation. The fallback to
        `SUPABASE_DATABASE_URL` (direct) was never reached because the
        except-branch continued to the next URL only after logging a warning.

        New behaviour:
          1. Try `SUPABASE_DATABASE_URL_WRITER` (canonical writer).
          2. Fall back to `SUPABASE_DATABASE_URL` (direct, typically writable).
          3. NEVER try `SUPABASE_DATABASE_URL_POOLER` for DDL — it is read-only
             in production.
          4. If neither writer URL is configured, log a single error and
             return (do NOT silently run DDL against the pooler).
        """
        # PATCH v4: writer-first ordering; pooler deliberately excluded.
        writer_url = os.getenv("SUPABASE_DATABASE_URL_WRITER") or os.getenv("SUPABASE_DATABASE_URL")
        pooler_url = os.getenv("SUPABASE_DATABASE_URL_POOLER")
        if not writer_url and not pooler_url:
            logger.error(
                "SUPABASE_DATABASE_URL_WRITER (or SUPABASE_DATABASE_URL) is required "
                "for schema bootstrap. Pooler URL is read-only in production and is "
                "no longer used for DDL."
            )
            return
        if not writer_url and pooler_url:
            logger.error(
                "Only SUPABASE_DATABASE_URL_POOLER is configured, but it is read-only "
                "for DDL. Set SUPABASE_DATABASE_URL_WRITER (or SUPABASE_DATABASE_URL "
                "direct connection) to enable schema bootstrap."
            )
            return

        statements = self.get_bootstrap_statements()

        tried_urls = []
        # PATCH v4: writer only. Pooler removed from DDL candidates.
        for candidate_url in (writer_url,):
            if not candidate_url:
                continue
            tried_urls.append(candidate_url)
            try:
                if candidate_url.startswith("sqlite"):
                    logger.info("Skipping psycopg2 bootstrap for SQLite: %s", candidate_url)
                    continue
                # বাংলা মন্তব্য: connect_timeout=10 দেওয়া হলো যাতে Render/Supabase SSL handshake
                # অনির্দিষ্টকালের জন্য ব্লক না করে। 10s পরে exception raise হবে।
                conn = psycopg2.connect(candidate_url, connect_timeout=10)
                try:
                    cur = conn.cursor()
                    for statement in statements:
                        cur.execute(statement)
                    conn.commit()
                finally:
                    cur.close()
                    conn.close()
                logger.info(
                    "Supabase schema bootstrap completed using %s.",
                    "SUPABASE_DATABASE_URL_WRITER" if candidate_url == writer_url else "SUPABASE_DATABASE_URL",
                )
                return
            except Exception as e:
                # PATCH v4: ReadOnlySqlTransaction is now structurally impossible
                # (writer-only), but we still downgrade DDL failures to WARNING
                # to avoid the silent-pattern CRITICAL escalation seen in v3.
                msg = str(e)
                if "read-only" in msg.lower() or "ReadOnlySqlTransaction" in msg:
                    logger.warning(
                        "Supabase schema bootstrap failed (read-only endpoint): %s. "
                        "Set SUPABASE_DATABASE_URL_WRITER to a writable endpoint. "
                        "Continuing without schema bootstrap — out-of-band migrations required.",
                        e,
                    )
                else:
                    logger.exception(f"Supabase operation error: {e}")
                    logger.warning(
                        "Supabase schema bootstrap failed for %s: %s",
                        "SUPABASE_DATABASE_URL_WRITER" if candidate_url == writer_url else "SUPABASE_DATABASE_URL",
                        e,
                    )

        logger.error(
            "Supabase schema bootstrap failed for all candidates: %s",
            ", ".join([u for u in tried_urls if u]),
        )

    def _is_schema_cache_error(self, error: Exception) -> bool:
        message = str(error) if error is not None else ""
        return (
            "Could not find the table" in message
            or "PGRST205" in message
            or "schema cache" in message.lower()
        )

    def _execute_response_with_retry(self, operation, fallback=None):
        try:
            response = operation()
            return getattr(response, "data", response)
        except Exception as e:
            if self._is_schema_cache_error(e):
                logger.warning(
                    "Supabase operation failed due missing table schema cache; bootstrapping schema and retrying: %s",
                    e,
                )
                self.bootstrap_schema()
                try:
                    response = operation()
                    return getattr(response, "data", response)
                except Exception as retry_error:
                    logger.exception(f"Supabase operation error: {retry_error}")
                    logger.error(
                        "Supabase retry after schema bootstrap failed: %s",
                        retry_error,
                    )
                    return fallback
            logger.debug(f"Supabase operation failed: {e}")
            return fallback

    # --- System Config ---
    def get_config(self, key: str) -> Any | None:
        res = self.client.table("system_config").select("value").eq("key", key).execute()
        if res.data:
            return res.data[0].get("value")
        return None

    def set_config(self, key: str, value: Any, category: str = "general"):
        self.client.table("system_config").upsert(
            {"key": key, "value": value, "category": category}
        ).execute()

    # --- Feature Flags ---
    def is_feature_enabled(self, feature_name: str, user_id: str | None = None) -> bool:
        res = (
            self.client.table("feature_flags")
            .select("*")
            .eq("feature_name", feature_name)
            .execute()
        )
        if not res.data:
            return False

        flag = res.data[0]
        if not flag.get("enabled", False):
            return False

        allowed_users = flag.get("allowed_users")
        # বাংলা মন্তব্য: allowed_users থাকলে সেটাই এখনpack/real gate —
        # আগের কোড ভুলবশত সব ক্ষেত্রেই True রিটার্ন করতো (Patch 16 fix)
        if allowed_users:
            return bool(user_id and user_id in allowed_users)

        rollout_pct = flag.get("rollout_percentage")
        if rollout_pct is not None and rollout_pct < 100 and user_id:
            # বাংলা মন্তব্য: deterministic percentage rollout
            import hashlib

            bucket = int(hashlib.sha256(f"{feature_name}:{user_id}".encode()).hexdigest(), 16) % 100
            return bucket < rollout_pct

        return True

    # --- GitHub Repos ---
    def add_github_repo(
        self, repo_name: str, owner: str, description: str = "", language: str = ""
    ):
        self.client.table("github_repos").upsert(
            {
                "repo_name": repo_name,
                "owner": owner,
                "description": description,
                "language": language,
            }
        ).execute()

    # --- AI Model Behavior ---
    def get_model_behavior(self, model_name: str) -> Any | None:
        if not self.client:
            return None
        try:
            res = (
                self.client.table("ai_model_behavior")
                .select("*")
                .eq("model_name", model_name)
                .single()
                .execute()
            )
            if res.data:
                return res.data
            return None
        except Exception as e:
            logger.exception(f"Supabase operation error: {e}")
            # It's okay if a model is not found, so we can log this at a debug level.
            logger.debug(f"Could not fetch AI model behavior for '{model_name}': {e}")
            return None

    def upsert_model_behavior(self, data: dict) -> Any | None:
        if not self.client:
            return None
        try:
            # Use upsert with on_conflict on 'model_name' if the table is set up for it.
            res = self.client.table("ai_model_behavior").upsert(data).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            logger.exception(f"Supabase operation error: {e}")
            return None

    # --- User Preferences ---
    def get_user_preferences(self, user_id: str) -> Any | None:
        if not self.client:
            return None
        try:
            res = self.client.table("user_preferences").select("*").eq("user_id", user_id).execute()
            if res.data:
                return res.data[0]
            return None
        except Exception as e:
            logger.exception(f"Supabase operation error: {e}")
            return None

    def upsert_user_preferences(self, data: dict) -> Any | None:
        if not self.client:
            return None
        try:
            res = self.client.table("user_preferences").upsert(data).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            logger.exception(f"Supabase operation error: {e}")
            return None

    def get_configs_by_category(self, category: str) -> list[dict]:
        if not self.client:
            return []
        try:
            res = self.client.table("system_config").select("*").eq("category", category).execute()
            return res.data or []  # type: ignore
        except Exception as e:
            logger.exception(f"Supabase operation error: {e}")
            return []

    # --- Evolution / Self-Evolution Persistence ---
    def insert_task_history(
        self,
        task: str,
        approach: str,
        result: str,
        success: bool,
        created_at: str,
    ) -> Any | None:
        if not self.client:
            return None
        entry = {
            "task": task,
            "approach": approach,
            "result": result,
            "success": success,
            "created_at": created_at,
        }
        res_data = self._execute_response_with_retry(
            lambda: self.client.table("task_history").insert(entry).execute(),
            fallback=None,
        )
        return res_data[0] if isinstance(res_data, list) and res_data else None

    def get_repeated_failures(self, min_occurrences: int = 3) -> list[dict[str, Any]]:
        if not self.client:
            return []
        rows = self._execute_response_with_retry(
            lambda: self.client.table("task_history").select("*").eq("success", False).execute(),
            fallback=[],
        )
        rows = rows or []
        groups: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            key = (row.get("task"), row.get("approach"))
            if key not in groups:
                groups[key] = {
                    "task": row.get("task"),
                    "approach": row.get("approach"),
                    "failures": 0,
                    "last_failed": row.get("created_at"),
                }
            groups[key]["failures"] += 1
            groups[key]["last_failed"] = max(groups[key]["last_failed"], row.get("created_at"))
        return [value for value in groups.values() if value["failures"] >= min_occurrences]

    def insert_skill_proposal(
        self,
        skill_name: str,
        source_pattern: str,
        generated_code: str,
        status: str,
        created_at: str,
    ) -> Any | None:
        if not self.client:
            return None
        try:
            entry = {
                "skill_name": skill_name,
                "source_pattern": source_pattern,
                "generated_code": generated_code,
                "status": status,
                "created_at": created_at,
            }
            res = self.client.table("skill_proposals").insert(entry).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            logger.exception(f"Supabase operation error: {e}")
            return None

    def insert_feedback(
        self,
        session_id: str,
        query: str,
        retrieved_chunks: str,
        user_rating: float,
        created_at: str,
    ) -> Any | None:
        if not self.client:
            return None
        try:
            entry = {
                "session_id": session_id,
                "query": query,
                "retrieved_chunks": retrieved_chunks,
                "user_rating": user_rating,
                "created_at": created_at,
            }
            res = self.service_client.table("feedback_loop").insert(entry).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            logger.exception(f"Supabase operation error: {e}")
            return None

    def append_evolution_log(self, entry: dict[str, Any]) -> Any | None:
        # বাংলা মন্তব্য: evolution_logs একটা RLS-protected audit টেবিল, ইচ্ছাকৃতভাবে
        # কোনো authenticated/anon INSERT policy নেই। তাই service_client (service_role
        # key, RLS bypass) ব্যবহার হচ্ছে — শুধু ব্যাকএন্ড সিস্টেম-লেভেল রাইট, ইউজার-ফেসিং নয়।
        client = self.service_client
        if not client:
            return None
        # বাংলা মন্তব্য: যদি এন্ট্রিতে 'event' কী না থাকে, তবে পুরো এন্ট্রিকে 'event' ফিল্ডে র‍্যাপ করা হচ্ছে
        if "event" not in entry:
            entry = {"event": entry}
        # created_at যদি না থাকে তবে স্বয়ংক্রিয়ভাবে কারেন্ট টাইম এড করা হচ্ছে
        if "created_at" not in entry:
            from datetime import UTC, datetime

            entry["created_at"] = datetime.now(UTC).isoformat()
        try:
            res = client.table("evolution_logs").insert(entry).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            logger.exception(f"Supabase operation error: {e}")
            return None

    def get_evolution_logs(self, limit: int = 200) -> list[dict[str, Any]]:
        # বাংলা মন্তব্য: এই টেবিলে কোনো SELECT policy নেই (RLS ON + 0 policies),
        # তাই পড়ার সময়ও service_client ব্যবহার করা হচ্ছে।
        client = self.service_client
        if not client:
            return []
        try:
            res = (
                client.table("evolution_logs")
                .select("*")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return res.data or []  # type: ignore
        except Exception as e:
            logger.exception(f"Supabase operation error: {e}")
            return []

    # --- Usage Metrics ---
    def upsert_usage_metric(self, data: dict) -> Any | None:
        if not self.client:
            return None
        try:
            res = self.client.table("usage_metrics").upsert(data).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            logger.exception(f"Supabase operation error: {e}")
            return None

    # --- Skills Registry DB integration ---
    def upsert_db_skill(self, data: dict) -> Any | None:
        if not self.client:
            return None
        try:
            res = self.client.table("skills").upsert(data).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            logger.exception(f"Supabase operation error: {e}")
            return None

    def get_db_skill(self, name: str) -> Any | None:
        if not self.client:
            return None
        try:
            res = self.client.table("skills").select("*").eq("name", name).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            logger.exception(f"Supabase operation error: {e}")
            return None

    def get_all_db_skills(self) -> list[dict]:
        if not self.client:
            return []
        try:
            res = self.client.table("skills").select("*").execute()
            return res.data or []  # type: ignore
        except Exception as e:
            logger.exception(f"Supabase operation error: {e}")
            return []

    # --- Guardrails DB integration ---
    def upsert_db_guardrail(self, data: dict) -> Any | None:
        if not self.client:
            return None
        try:
            res = self.client.table("guardrails").upsert(data).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            logger.exception(f"Supabase operation error: {e}")
            return None

    def get_db_guardrails(self) -> list[dict]:
        if not self.client:
            return []
        try:
            res = (
                self.client.table("guardrails")
                .select("*")
                .eq("is_active", True)
                .order("priority", desc=False)
                .execute()
            )
            return res.data or []  # type: ignore
        except Exception as e:
            logger.exception(f"Supabase operation error: {e}")
            return []

    # --- Provider Configs DB integration ---
    def upsert_db_provider_config(self, data: dict) -> Any | None:
        if not self.client:
            return None
        try:
            res = self.client.table("provider_configs").upsert(data).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            logger.exception(f"Supabase operation error: {e}")
            return None

    def get_db_provider_configs(self) -> list[dict]:
        if not self.client:
            return []
        try:
            res = (
                self.client.table("provider_configs")
                .select("*")
                .eq("is_active", True)
                .order("priority", desc=False)
                .execute()
            )
            return res.data or []  # type: ignore
        except Exception as e:
            logger.exception(f"Supabase operation error: {e}")
            return []

    # বাংলা মন্তব্য: 'a' দিয়ে শুরু হওয়া মেথডগুলোকে থ্রেডপুলে রান করানোর জন্য ডায়নামিক এসিঙ্ক প্রক্সি মেথড।
    # এটি ইভেন্ট লুপকে ব্লক হওয়া থেকে বাঁচাবে।
    def __getattr__(self, name: str) -> Any:
        # বাংলা মন্তব্য: অসীম রিকার্সন এড়াতে প্রাইভেট বা নির্দিষ্ট ফিল্ড সরাসরি বাইপাস
        if name in ("client", "url", "key", "service_client", "service_key") or name.startswith(
            "_"
        ):
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

        if name.startswith("a") and hasattr(self, name[1:]):
            sync_attr = getattr(self, name[1:])
            if callable(sync_attr):
                import asyncio
                from functools import partial

                async def async_wrapper(*args, **kwargs):
                    loop = asyncio.get_running_loop()
                    func = partial(sync_attr, *args, **kwargs)
                    return await loop.run_in_executor(None, func)

                return async_wrapper
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


db = SupabaseDB()
