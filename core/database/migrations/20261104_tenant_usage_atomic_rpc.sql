-- =============================================================================
-- SupremeAI Atomic Tenant Usage RPC Migration (Finding #6)
-- Target: Supabase PostgreSQL (Public Schema)
-- Generated: 2026-11-04
-- =============================================================================

BEGIN;

CREATE OR REPLACE FUNCTION public.increment_tenant_usage(
    p_tenant_id TEXT,
    p_date DATE,
    p_request_count INTEGER DEFAULT 1,
    p_token_count INTEGER DEFAULT 0
)
RETURNS TABLE (
    tenant_id TEXT,
    usage_date DATE,
    total_requests INTEGER,
    total_tokens BIGINT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    INSERT INTO public.tenant_usage (tenant_id, date, request_count, token_count, updated_at)
    VALUES (p_tenant_id, p_date, p_request_count, p_token_count, NOW())
    ON CONFLICT (tenant_id, date)
    DO UPDATE SET
        request_count = public.tenant_usage.request_count + EXCLUDED.request_count,
        token_count = public.tenant_usage.token_count + EXCLUDED.token_count,
        updated_at = NOW()
    RETURNING
        public.tenant_usage.tenant_id,
        public.tenant_usage.date AS usage_date,
        public.tenant_usage.request_count AS total_requests,
        public.tenant_usage.token_count AS total_tokens;
END;
$$;

-- Grant execution permission to service_role and authenticated users
GRANT EXECUTE ON FUNCTION public.increment_tenant_usage(TEXT, DATE, INTEGER, INTEGER) TO service_role, authenticated;

COMMIT;

