# SupremeAI × Existing Team Supabase Integration Checklist

**Goal:** Connect SupremeAI codebase to your existing team Supabase project safely, without creating a new database or modifying production data before verification.

**Timeline:** 30–45 minutes for team admin + developer.

**Outcome:** Environment variables verified, schema audited, and ready for Phase 1 safe migration (embedding dimension fix).

---

## Step 1: Team Admin — Verify project access and export credentials

**Who:** Supabase project owner or admin with role management permissions.  
**When:** First, before developer touches code.

### 1.1 Verify existing project is healthy

1. Go to https://supabase.com/dashboard
2. Locate your existing team project (not creating a new one)
3. Check **Project Settings** → **General**:
   - Status: **Active** (green)
   - Database: **Healthy** (green)
   - API: **Available** (green)

### 1.2 Note project reference ID

In **Project Settings** → **General**, copy:

```text
Project Reference: <PROJECT_REF>
```

Example: `abcd1234efgh5678ijkl`

### 1.3 Generate API keys (or find existing)

Go to **Project Settings** → **API**:

1. Copy **Project URL**:
   ```text
   https://<PROJECT_REF>.supabase.co
   ```

2. Under **API Keys**, find or generate:
   - **anon public** key (safe for frontend)
   - **service_role** key (secret, backend-only)

**Warning:** Service role key must NOT be committed to Git or exposed in frontend code.

### 1.4 Add developer as team member

Go to **Project Settings** → **Team**:

1. Click **Add member**
2. Invite developer's email
3. Role: **Developer** (or **Admin** if preferred)
4. Developer accepts invite in their email

---

## Step 2: Developer — Validate environment variable setup

**Who:** Developer integrating SupremeAI codebase.  
**When:** After team admin has shared credentials.

### 2.1 Verify environment variables are available

Check Vercel project settings (top right → Settings → Vars):

Look for:

```text
SUPABASE_URL
SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY
```

If missing, ask team admin to add them to the Vercel project (not to Git):

```text
SUPABASE_URL=https://<PROJECT_REF>.supabase.co
SUPABASE_ANON_KEY=<copy from API Keys>
SUPABASE_SERVICE_ROLE_KEY=<copy from API Keys>
```

Also verify (already should exist):

```text
NEXT_PUBLIC_DEV_SUPABASE_REDIRECT_URL
```

### 2.2 Test local connection

From project root:

```bash
export SUPABASE_URL="https://<PROJECT_REF>.supabase.co"
export SUPABASE_ANON_KEY="<anon_key>"
export SUPABASE_SERVICE_ROLE_KEY="<service_role_key>"

# Test connection
python -c "
from supabase import create_client
import os

url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_ANON_KEY')
client = create_client(url, key)
result = client.table('profiles').select('count', count='exact').execute()
print(f'✓ Connected. Table count: {result.count}')
" 2>&1 || echo "✗ Connection failed"
```

**Expected output:**
```text
✓ Connected. Table count: <some number>
```

If error, check:
- URL format is correct
- Keys are not truncated
- Project is active (step 1.1)

---

## Step 3: Developer — Audit existing schema

**Who:** Developer.  
**When:** After connection test passes.

### 3.1 Inventory existing tables

Go to Supabase Dashboard → **SQL Editor** or use CLI:

```bash
supabase db list --linked
```

Expected output: list of tables in your project.

**Common tables to look for:**

```text
auth.users           (Supabase auth, auto-managed)
public.profiles      (likely exists)
public.conversations (if chat exists)
public.agents        (if agents table exists)
public.ai_memory     (what we need to verify/add)
```

### 3.2 Check ai_memory table structure

In Supabase Dashboard → **Table Editor**, find `ai_memory`:

**Check columns exist:**

```sql
id              UUID (primary key)
user_id         UUID (not null, foreign key to auth.users)
tenant_id       UUID (may be null if single-tenant)
content         TEXT (not null)
embedding       vector(384)  ← THIS IS CRITICAL
memory_type     TEXT
importance_score NUMERIC
created_at      TIMESTAMPTZ
updated_at      TIMESTAMPTZ
expires_at      TIMESTAMPTZ
```

**If embedding column is wrong type:**

- `TEXT` → needs migration to `vector(384)`
- `vector(1536)` → needs migration to `vector(384)`
- Does not exist → needs to be added

### 3.3 Check for vector extension

Go to Supabase Dashboard → **Database** → **Extensions**:

Look for `pgvector` (should be enabled).

If not, enable it:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 3.4 List existing RLS policies

In **SQL Editor**, run:

```sql
SELECT tablename, policyname, qual, with_check
FROM pg_policies
WHERE tablename = 'ai_memory';
```

**Record output for Phase 1 planning.**

---

## Step 4: Check for existing migrations or version lock

**Who:** Developer.  
**When:** Before any schema modification.

### 4.1 Inspect migration history

Go to Supabase Dashboard → **SQL Editor** → run:

```sql
SELECT version, success, executed_at
FROM schema_migrations
ORDER BY executed_at DESC
LIMIT 10;
```

This shows which migrations have been applied.

### 4.2 Check codebase migration state

From project root:

```bash
ls -la backend/alembic_migrations/versions/ | head -20
```

**Note the most recent migration number** (e.g., `001_initial_schema.py`).

---

## Step 5: Verify auth configuration

**Who:** Developer or team auth lead.  
**When:** Before login/signup testing.

### 5.1 Check auth enabled

Go to Supabase Dashboard → **Authentication** → **Providers**:

- Email/Password: **Enabled** (required for MVP)
- OAuth/Magic Link: Optional for MVP

### 5.2 Check email templates

Go to **Authentication** → **Email Templates**:

- Confirm signup email: exists
- Password reset email: exists
- Change email: exists

If missing, Supabase auto-generates defaults.

### 5.3 Check redirect URLs

Go to **Project Settings** → **Authentication**:

Under **Redirect URLs**, add:

```text
localhost:3000
localhost:3001
https://<your-vercel-preview-domain>/*
https://<your-vercel-production-domain>/*
```

Each on a new line.

---

## Step 6: Database security check

**Who:** Developer.  
**When:** Before first production use.

### 6.1 Verify RLS is enabled on exposed tables

In **SQL Editor**, run:

```sql
SELECT tablename, rowsecurity
FROM pg_class
WHERE schemaname = 'public'
AND rowsecurity = true;
```

**All user-owned tables MUST have RLS enabled.**

### 6.2 Verify no service_role key in frontend code

Search codebase:

```bash
grep -r "SUPABASE_SERVICE_ROLE_KEY" frontend/ app/ || echo "✓ service_role not in frontend"
```

**Expected:** No matches.

### 6.3 Verify no hardcoded secrets in code

```bash
grep -r "supabase.co" backend/ frontend/ app/ | grep -v ".env" | grep -v "SUPABASE_URL" || echo "✓ No hardcoded URLs"
```

---

## Step 7: Connectivity and performance baseline

**Who:** Developer.  
**When:** Before starting Phase 1 schema work.

### 7.1 Query execution baseline

In **SQL Editor**, run:

```sql
SELECT version();
```

Record the Postgres version (should be 12+).

### 7.2 Connection pool status

In **Project Settings** → **Database** → **Connection Pooling**:

- Mode: **Transaction** (recommended for most workloads)
- Max client connections: default or custom

### 7.3 Test a simple read

In **SQL Editor**:

```sql
SELECT 
  current_database(),
  current_user,
  now() as current_time;
```

**Expected:** Returns database name, user, and current timestamp.

---

## Step 8: Document findings and hand off to Phase 1

**Who:** Developer.  
**When:** After all checks pass.

### 8.1 Create a summary document

Create `docs/SUPABASE_INTEGRATION_SUMMARY.md` with:

```markdown
# Supabase Integration Summary

## Project Details
- **Project Reference:** <PROJECT_REF>
- **Project URL:** https://<PROJECT_REF>.supabase.co
- **Region:** <region>

## Schema Audit
- **Tables found:** [list]
- **ai_memory table:** [exists/missing]
- **ai_memory.embedding type:** [TEXT/vector(384)/vector(1536)]
- **pgvector extension:** [enabled/not found]
- **RLS status:** [enabled/missing on X tables]

## Auth Configuration
- **Email/Password:** [enabled/disabled]
- **Redirect URLs:** [count]

## Migration Status
- **Last migration applied:** <date>
- **Pending migrations:** [count]

## Connection Test
- **Date tested:** <date>
- **Result:** [✓ pass / ✗ fail]
- **Latency (p50):** ~50ms

## Next Steps
1. Phase 1: Fix embedding dimension
2. Phase 1: Ensure ai_memory RLS policies
3. Phase 2: Queue persistence schema
```

### 8.2 Ready for Phase 1

At this point:

- ✓ Environment variables confirmed
- ✓ Existing project is healthy
- ✓ Schema audit completed
- ✓ Auth configured
- ✓ RLS status known
- ✓ Connection baseline established

**Do NOT proceed to schema migration** until all steps are documented and reviewed by team.

---

## Troubleshooting

### Connection refused

```text
Error: connect ECONNREFUSED 127.0.0.1:5432
```

**Cause:** Local database running, not Supabase.

**Fix:** Ensure environment variables point to Supabase URL (https://<PROJECT_REF>.supabase.co), not localhost.

### 401 Unauthorized

```text
Error: Unauthorized. Please check your API key.
```

**Cause:** Invalid or expired key.

**Fix:** Copy anon key again from **Project Settings** → **API**. Do not use service_role key for client requests.

### RLS denies access

```text
Error: <TableName> policy violation
```

**Cause:** RLS policy is too strict, or user not properly authenticated.

**Fix:** Review policies in **Project Settings** → **RLS**. Ensure policy allows authenticated users to read/write their own rows.

### Table not found / PGRST116

```text
Error: Table <table> does not exist
```

**Cause:** Table exists in database but not exposed via API, or wrong table name.

**Fix:** Go to **Project Settings** → **API** → **Exposed schemas**. Ensure `public` is exposed and `anon`/`authenticated` roles have GRANT access.

---

## Rollback and escape hatches

If schema migration fails or causes data issues:

### Immediate rollback

1. Go to **Project Settings** → **Backups**
2. Click **Restore** to a point before the migration
3. All tables and data revert

### Manual schema fix

If rollback not available, ask team admin to:

1. Check **SQL Editor** for error messages
2. Run `SELECT * FROM schema_migrations WHERE success = false;`
3. Manually adjust tables or run recovery SQL

---

## Sign-off checklist

Before marking this integration as complete:

- [ ] Project reference ID confirmed
- [ ] API keys copied to Vercel project
- [ ] Local connection test passes
- [ ] ai_memory table structure verified
- [ ] pgvector extension enabled
- [ ] RLS status documented
- [ ] Auth configuration checked
- [ ] Redirect URLs configured
- [ ] No service_role key in frontend code
- [ ] Summary document created
- [ ] Team reviewed and approved

Once all boxes are checked, you are ready for **Phase 1: Fix embedding dimension and tenant isolation**.
