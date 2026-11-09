-- ==============================================================================
-- SupremeAI Production Database Hardening: RLS, RBAC, and Schema Parity SSOT
-- 
-- Description:
--   1. Enables Row-Level Security (RLS) on all public tables idempotently.
--   2. Enforces service_role full bypass while restricting client queries.
--   3. Adds owner-only isolation policies for critical authentication & billing tables.
--   4. Enforces non-null defaults on users table (role, is_active, is_verified, mfa_enabled).
--   5. Fixes schema type parity (api_keys.user_id text -> uuid).
--
-- Safety:
--   - 100% idempotent: Safe to execute repeatedly in Supabase SQL Editor.
--   - Wrapped in exception handling blocks to prevent breaking on missing tables.
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. Enable RLS on All Public Tables
-- ------------------------------------------------------------------------------
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN (
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public' 
          AND tablename NOT LIKE 'pg_%' 
          AND tablename NOT LIKE 'sql_%'
          AND tablename NOT IN ('alembic_version', 'spatial_ref_sys')
    ) LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY;', r.tablename);
    END LOOP;
END $$;

-- ------------------------------------------------------------------------------
-- 2. Schema Hardening on `users` Table
-- ------------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'users') THEN
        -- role
        UPDATE public.users SET role = 'user' WHERE role IS NULL;
        ALTER TABLE public.users ALTER COLUMN role SET DEFAULT 'user';
        BEGIN
            ALTER TABLE public.users ALTER COLUMN role SET NOT NULL;
        EXCEPTION WHEN others THEN
            RAISE NOTICE 'Could not set NOT NULL on users.role: %', SQLERRM;
        END;

        -- is_active
        UPDATE public.users SET is_active = true WHERE is_active IS NULL;
        ALTER TABLE public.users ALTER COLUMN is_active SET DEFAULT true;
        BEGIN
            ALTER TABLE public.users ALTER COLUMN is_active SET NOT NULL;
        EXCEPTION WHEN others THEN
            RAISE NOTICE 'Could not set NOT NULL on users.is_active: %', SQLERRM;
        END;

        -- is_verified
        UPDATE public.users SET is_verified = false WHERE is_verified IS NULL;
        ALTER TABLE public.users ALTER COLUMN is_verified SET DEFAULT false;
        BEGIN
            ALTER TABLE public.users ALTER COLUMN is_verified SET NOT NULL;
        EXCEPTION WHEN others THEN
            RAISE NOTICE 'Could not set NOT NULL on users.is_verified: %', SQLERRM;
        END;

        -- mfa_enabled
        UPDATE public.users SET mfa_enabled = false WHERE mfa_enabled IS NULL;
        ALTER TABLE public.users ALTER COLUMN mfa_enabled SET DEFAULT false;
        BEGIN
            ALTER TABLE public.users ALTER COLUMN mfa_enabled SET NOT NULL;
        EXCEPTION WHEN others THEN
            RAISE NOTICE 'Could not set NOT NULL on users.mfa_enabled: %', SQLERRM;
        END;
    END IF;
END $$;

-- ------------------------------------------------------------------------------
-- 3. Type Parity: `api_keys.user_id` text -> uuid
-- ------------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
          AND table_name = 'api_keys' 
          AND column_name = 'user_id' 
          AND data_type = 'text'
    ) THEN
        BEGIN
            ALTER TABLE public.api_keys ALTER COLUMN user_id TYPE uuid USING user_id::uuid;
            RAISE NOTICE 'Successfully converted api_keys.user_id from text to uuid';
        EXCEPTION WHEN others THEN
            RAISE NOTICE 'Could not convert api_keys.user_id to uuid (invalid uuid values exist?): %', SQLERRM;
        END;
    END IF;
END $$;

-- ------------------------------------------------------------------------------
-- 4. Owner Isolation Policies for Critical Tables
-- ------------------------------------------------------------------------------
DO $$
DECLARE
    tbl text;
    user_col text;
BEGIN
    -- Tables where owner is `user_id`
    FOR tbl IN VALUES ('api_keys'), ('refresh_tokens'), ('user_wallets'), ('user_preferences') LOOP
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = tbl) THEN
            -- Service role bypass
            EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I;', tbl || '_service_role_all', tbl);
            EXECUTE format('CREATE POLICY %I ON public.%I FOR ALL TO service_role USING (true) WITH CHECK (true);', tbl || '_service_role_all', tbl);

            -- Owner-only select/update/delete
            EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I;', tbl || '_owner_isolated', tbl);
            EXECUTE format('CREATE POLICY %I ON public.%I FOR ALL TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);', tbl || '_owner_isolated', tbl);
        END IF;
    END LOOP;

    -- `users` table: users can read and update only their own profile
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'users') THEN
        DROP POLICY IF EXISTS users_service_role_all ON public.users;
        CREATE POLICY users_service_role_all ON public.users FOR ALL TO service_role USING (true) WITH CHECK (true);

        DROP POLICY IF EXISTS users_owner_self ON public.users;
        CREATE POLICY users_owner_self ON public.users FOR ALL TO authenticated USING (auth.uid() = id) WITH CHECK (auth.uid() = id);
    END IF;
END $$;
