# Supabase and Upstash Redis Setup

## Supabase (PostgreSQL)

### 1. Project Creation
- Go to https://supabase.com and create a new project.
- Note the project URL and `anon` / `service_role` keys.

### 2. Connection String
Use the provided "Connection string" in Supabase Dashboard:
```
postgresql://postgres:[password]@aws-0-<region>.pooler.supabase.com:6543/postgres
```

### 3. Required Tables
Execute in the Supabase SQL Editor (adjust to your schema):
```sql
CREATE TABLE IF NOT EXISTS verification_queue (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  status TEXT NOT NULL DEFAULT 'pending',
  payload JSONB NOT NULL,
  metadata JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_verification_queue_status ON verification_queue(status);
CREATE INDEX IF NOT EXISTS idx_verification_queue_updated_at ON verification_queue(updated_at);
```

### 4. Realtime (optional)
Enable in Dashboard: Database -> Replication -> `verification_queue` -> Enable realtime.

## Upstash Redis

### 1. Create Redis Database
- Go to https://upstash.com and create a Redis database.
- Set TLS to `true`.
- Copy the connection URL:
```
rediss://:<PASSWORD>@<UUID>.upstash.io:6379
```

### 2. Configure APP
Set in `.env`:
- `UPSTASH_REDIS_URL=rediss://default:<PASSWORD>@<UUID>.upstash.io:6379`

### 3. TTL / Eviction
Recommended settings (Upstash Dashboard):
- "Eviction": `allkeys-lru`
- "Max memory": choose plan

## Environment Variables

| Variable | Source | Description |
|---|---|---|
| `SUPABASE_URL` | Supabase Dashboard | Supabase project URL |
| `SUPABASE_KEY` | Supabase Dashboard | Anon or service_role key |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase Dashboard | Admin access |
| `UPSTASH_REDIS_URL` | Upstash Dashboard | Redis TLS connection string |
| `REDIS_URL` | Local or Upstash | Fallback / localhost Redis |
| `GCP_FIRESTORE_COLLECTION` | GCP Project | Shared state collection |

## Local Verification
```bash
curl $SUPABASE_URL/rest/v1/ -H "apikey: $SUPABASE_KEY"
redis-cli -u $UPSTASH_REDIS_URL ping
```
