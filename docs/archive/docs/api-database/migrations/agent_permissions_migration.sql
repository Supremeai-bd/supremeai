-- =====================================================
-- SupremeAI - Agent Permissions Table Migration (Pillar 0)
-- =====================================================
-- Supabase SQL Editor-এ এটা রান করুন।
-- Pillar 0-এর Database-Driven Permission Architecture-এর অংশ।

-- Step 1: Permission state enum type
-- 4 states per Burj Khalifa Plan:
--   always_allowed   → AI executes without asking
--   allowed_for_now  → Temporary/session-based permission (TTL-bound)
--   not_allowed      → AI must pause and request Admin approval
--   never_allowed    → Strictly blocked, AI will not even ask
CREATE TYPE permission_state AS ENUM (
    'always_allowed',
    'allowed_for_now',
    'not_allowed',
    'never_allowed'
);

-- Step 2: agent_permissions টেবিল তৈরি
CREATE TABLE IF NOT EXISTS agent_permissions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action_name     TEXT  NOT NULL UNIQUE,       -- e.g. 'sandbox_execute', 'deploy_main', 'update_core_logic'
    permission_state permission_state NOT NULL DEFAULT 'not_allowed',
    allowed_for_now_expires_at TIMESTAMPTZ,    -- TTL enforcement for allowed_for_now
    -- Constraint: allowed_for_now MUST have an expiry timestamp
    CONSTRAINT chk_allowed_for_now_expires
        CHECK (permission_state != 'allowed_for_now' OR allowed_for_now_expires_at IS NOT NULL),
    -- Constraint: never_allowed must NOT have an expiry (it's permanent)
    CONSTRAINT chk_never_allowed_no_expiry
        CHECK (permission_state != 'never_allowed' OR allowed_for_now_expires_at IS NULL),
    description     TEXT,                       -- Human-readable description of what this action does
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Step 3: Index for fast lookups by action_name
CREATE INDEX IF NOT EXISTS agent_permissions_action_name_idx
    ON agent_permissions (action_name);

-- Step 4: Index to find expired allowed_for_now rows (for cleanup cron)
CREATE INDEX IF NOT EXISTS agent_permissions_expires_idx
    ON agent_permissions (allowed_for_now_expires_at)
    WHERE permission_state = 'allowed_for_now';

-- Step 5: Index for filtering by permission state
CREATE INDEX IF NOT EXISTS agent_permissions_state_idx
    ON agent_permissions (permission_state);

-- Step 6: Auto-update updated_at on row change
CREATE OR REPLACE FUNCTION update_agent_permissions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_agent_permissions_updated_at
    ON agent_permissions;

CREATE TRIGGER trigger_update_agent_permissions_updated_at
    BEFORE UPDATE ON agent_permissions
    FOR EACH ROW EXECUTE FUNCTION update_agent_permissions_updated_at();

-- Step 7: Row Level Security — only service role / admin can manage
ALTER TABLE agent_permissions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role can manage all permissions"
    ON agent_permissions
    FOR ALL
    TO service_role, authenticated
    USING (true)
    WITH CHECK (true);

-- Step 8: Seed default permissions (always_allowed for safe tasks only)
-- Everything else defaults to not_allowed per the plan
INSERT INTO agent_permissions (action_name, permission_state, description)
VALUES
    -- Safe, always_allowed actions (Pillar 0 spec: basic safe tasks)
    ('read_files',              'always_allowed',  'Read files from the workspace (AI can execute without asking)'),
    ('lint_code',               'always_allowed',  'Run linter on workspace files'),
    ('update_index_md',         'always_allowed',  'Update _INDEX.md files in directories'),
    ('update_checkpoint_md',    'always_allowed',  'Update CHECKPOINT.md'),
    ('update_lessons_learned',  'always_allowed',  'Append to LESSONS_LEARNED.md'),
    ('memory_write',            'always_allowed',  'Write to ai_memory (pgvector)'),

    -- Restricted actions — not_allowed by default, AI must ask Admin
    ('sandbox_execute',         'not_allowed',     'Execute code in sandbox (Python subprocess / Docker)'),
    ('sandbox_docker',          'not_allowed',     'Execute code in Docker isolated container'),
    ('deploy_main',             'never_allowed',   'Direct push to main branch — permanently blocked'),
    ('db_migration',            'not_allowed',     'Run database migrations'),
    ('core_logic_change',       'not_allowed',     'Modify core backend logic files'),
    ('open_pr',                 'not_allowed',     'Open a new Pull Request to main'),
    ('restart_server',          'not_allowed',     'Restart backend/server processes in production')
ON CONFLICT (action_name) DO NOTHING;

-- Step 9: Cleanup cron — expire allowed_for_now rows past their TTL
-- (Run via Supabase Cron Job or a periodic background task)
-- DELETE FROM agent_permissions
-- WHERE permission_state = 'allowed_for_now'
--   AND allowed_for_now_expires_at < NOW();

-- =====================================================
-- Verification:
-- =====================================================
-- SELECT action_name, permission_state FROM agent_permissions ORDER BY action_name;
-- SELECT * FROM agent_permissions WHERE action_name = 'sandbox_execute';
-- SELECT COUNT(*) FROM agent_permissions WHERE permission_state = 'not_allowed';