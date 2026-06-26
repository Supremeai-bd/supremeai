# SupremeAI 2.0 — API Key Management System
## Complete Production Plan

---

## 📋 Executive Summary

A secure, self-service API key generation system that allows users to:
- Generate multiple API keys with custom names and scopes
- View usage analytics (requests, tokens, costs)
- Rotate/revoke keys instantly
- Set rate limits and expiration dates
- Receive alerts on abnormal usage

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Studio Admin │  │ Web Chat     │  │ Mobile App   │              │
│  │ (React/Vite) │  │ (React)      │  │ (Flutter)    │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
└─────────┼─────────────────┼─────────────────┼──────────────────────┘
          │                 │                 │
          └─────────────────┼─────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      API GATEWAY LAYER                               │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  FastAPI Backend  →  ZeroTrustAuthMiddleware                │   │
│  │  ├─ /api/v1/auth/*       (Firebase/JWT auth)                 │   │
│  │  ├─ /api/v1/keys/*       (API Key CRUD)                    │   │
│  │  ├─ /api/v1/usage/*      (Usage analytics)                 │   │
│  │  ├─ /api/v1/billing/*    (Quota & billing)                 │   │
│  │  └─ /api/v1/admin/keys/* (Admin key management)            │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      DATA LAYER                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ PostgreSQL   │  │ Redis        │  │ Firestore    │              │
│  │ (Primary DB) │  │ (Cache/Rate  │  │ (Audit Logs) │              │
│  │              │  │  Limiting)   │  │              │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   BACKGROUND SERVICES                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Celery       │  │ Prometheus   │  │ Discord/     │              │
│  │ Workers      │  │ Metrics      │  │ Slack Bot    │              │
│  │ (Key expiry, │  │ (Key usage   │  │ (Alerts)     │              │
│  │  rotation)   │  │  tracking)   │  │              │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🗄️ Database Schema (PostgreSQL)

### Table: `api_keys`
```sql
CREATE TABLE api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id       UUID REFERENCES tenants(id) ON DELETE SET NULL,

    -- Key identification
    name            VARCHAR(100) NOT NULL,
    description     TEXT,
    key_prefix      VARCHAR(8) NOT NULL,        -- e.g., "sk_live_"
    key_hash        VARCHAR(255) NOT NULL,       -- bcrypt hash of full key

    -- Scopes & permissions
    scopes          JSONB NOT NULL DEFAULT '["inference"]',
    -- ["inference", "training", "admin", "billing", "read_only"]

    -- Rate limiting
    rate_limit_rpm  INTEGER NOT NULL DEFAULT 60,  -- requests per minute
    rate_limit_rpd  INTEGER NOT NULL DEFAULT 1000, -- requests per day

    -- Quota & billing
    monthly_quota   BIGINT NOT NULL DEFAULT 1000000, -- tokens per month
    quota_used      BIGINT NOT NULL DEFAULT 0,
    quota_reset_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Expiration & lifecycle
    expires_at      TIMESTAMPTZ,
    last_used_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Status
    status          VARCHAR(20) NOT NULL DEFAULT 'active',
    -- ["active", "revoked", "expired", "suspended"]
    revoked_reason  TEXT,
    revoked_at      TIMESTAMPTZ,
    revoked_by      UUID REFERENCES users(id),

    -- Metadata
    metadata        JSONB DEFAULT '{}',
    ip_whitelist    JSONB DEFAULT '[]',         -- ["192.168.1.0/24"]

    -- Indexes
    CONSTRAINT valid_status CHECK (status IN ('active', 'revoked', 'expired', 'suspended')),
    CONSTRAINT valid_scopes CHECK (jsonb_array_length(scopes) > 0)
);

CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX idx_api_keys_tenant_id ON api_keys(tenant_id);
CREATE INDEX idx_api_keys_status ON api_keys(status) WHERE status = 'active';
CREATE INDEX idx_api_keys_expires_at ON api_keys(expires_at) WHERE status = 'active';
CREATE INDEX idx_api_keys_key_prefix ON api_keys(key_prefix);

-- GIN index for JSONB scopes query
CREATE INDEX idx_api_keys_scopes ON api_keys USING GIN(scopes);
```

### Table: `api_key_usage`
```sql
CREATE TABLE api_key_usage (
    id              BIGSERIAL PRIMARY KEY,
    key_id          UUID NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Request details
    request_id      VARCHAR(64) NOT NULL UNIQUE,
    endpoint        VARCHAR(255) NOT NULL,
    method          VARCHAR(10) NOT NULL,

    -- Usage metrics
    tokens_input    INTEGER NOT NULL DEFAULT 0,
    tokens_output   INTEGER NOT NULL DEFAULT 0,
    tokens_total    INTEGER GENERATED ALWAYS AS (tokens_input + tokens_output) STORED,

    -- Cost tracking (in smallest currency unit, e.g., cents)
    cost_usd        DECIMAL(10, 6) NOT NULL DEFAULT 0,

    -- Performance
    latency_ms      INTEGER,
    status_code     INTEGER NOT NULL,

    -- Context
    model_used      VARCHAR(100),
    provider_used   VARCHAR(50),

    -- Client info
    ip_address      INET,
    user_agent      TEXT,
    country         VARCHAR(2),  -- ISO country code

    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Partitioning by month for performance
    -- PARTITION BY RANGE (created_at)
);

-- Monthly partitioning
CREATE TABLE api_key_usage_2026_06 PARTITION OF api_key_usage
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

CREATE INDEX idx_api_key_usage_key_id ON api_key_usage(key_id);
CREATE INDEX idx_api_key_usage_user_id ON api_key_usage(user_id);
CREATE INDEX idx_api_key_usage_created_at ON api_key_usage(created_at);
CREATE INDEX idx_api_key_usage_endpoint ON api_key_usage(endpoint);
```

### Table: `api_key_events` (Audit Log)
```sql
CREATE TABLE api_key_events (
    id              BIGSERIAL PRIMARY KEY,
    key_id          UUID REFERENCES api_keys(id) ON DELETE SET NULL,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    event_type      VARCHAR(50) NOT NULL,
    -- ["created", "viewed", "rotated", "revoked", "suspended", 
    --  "quota_exceeded", "rate_limited", "expired", "reactivated"]

    event_data      JSONB NOT NULL DEFAULT '{}',
    ip_address      INET,
    user_agent      TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_api_key_events_key_id ON api_key_events(key_id);
CREATE INDEX idx_api_key_events_user_id ON api_key_events(user_id);
CREATE INDEX idx_api_key_events_type ON api_key_events(event_type);
CREATE INDEX idx_api_key_events_created_at ON api_key_events(created_at);
```

---

## 🔐 Security Model

### Key Generation Algorithm
```
Format: sk_<env>_<prefix>_<random>_<checksum>
Example: sk_live_abc123def_xxxxxxxxxxxxxxxx_xxxx

Components:
- sk_       : Standard prefix (like OpenAI)
- <env>     : live | test | dev
- <prefix>  : First 8 chars of UUID (stored in DB, shown to user)
- <random>  : 32-char crypto-random base62 string
- <checksum>: 4-char CRC32 of prefix+random (tamper detection)

Storage: Only bcrypt hash of full key is stored
Display: Only prefix is shown after creation ("sk_live_abc123...xxxx")
```

### Authentication Flow
```
1. User sends request with header: Authorization: Bearer sk_live_abc123...xxxx
2. Middleware extracts key, splits into prefix + full_key
3. Lookup by prefix in Redis (cached) or PostgreSQL
4. Verify bcrypt(full_key) == stored_hash
5. Check: status==active, not expired, not rate-limited, quota available
6. Check: IP whitelist (if configured)
7. Attach user_id, scopes, rate_limit to request.state
8. Log usage asynchronously (Firestor + async DB write)
9. Route to appropriate handler
```

### Rate Limiting (Redis + Sliding Window)
```
Keys:
  rate:<key_id>:rpm  → ZSET of timestamps (last 60s)
  rate:<key_id>:rpd  → ZSET of timestamps (last 24h)
  quota:<key_id>:month → current month usage (counter)

Algorithm:
  1. ZREMRANGEBYSCORE rate:<key_id>:rpm 0 (now - 60s)
  2. ZCARD rate:<key_id>:rpm → current RPM
  3. If > limit: return 429
  4. ZADD rate:<key_id>:rpm now
  5. EXPIRE rate:<key_id>:rpm 120

Same for RPD with 86400s window.
```

---

## 📊 Quota & Billing Model

### Free Tier (Default)
| Feature | Limit |
|---------|-------|
| Keys per user | 3 |
| Monthly quota | 1M tokens |
| Rate limit | 60 RPM / 1000 RPD |
| Max key lifetime | 90 days |
| Scopes | inference only |

### Pro Tier
| Feature | Limit |
|---------|-------|
| Keys per user | 20 |
| Monthly quota | 10M tokens |
| Rate limit | 600 RPM / 50K RPD |
| Max key lifetime | 365 days |
| Scopes | inference, training, read_only |

### Enterprise Tier
| Feature | Limit |
|---------|-------|
| Keys per user | Unlimited |
| Monthly quota | Custom |
| Rate limit | Custom |
| Max key lifetime | Unlimited |
| Scopes | All + admin |
| IP Whitelist | Yes |
| Audit log retention | 2 years |

---

## 🔔 Alert System

### Alert Types
1. **Quota 80%** → Email + Discord DM
2. **Quota 100%** → Email + Discord + Auto-suspend key
3. **Rate limit hit 5x** → Email warning
4. **Key unused 30 days** → Email warning (auto-expire in 7 days)
5. **Suspicious usage** (10x normal) → Email + Auto-suspend + Admin alert
6. **Key from new IP** → Email notification
7. **Key expired** → Email 7 days before, 1 day before, on expiry

### Alert Channels
- In-app notifications (Firestore realtime)
- Email (SendGrid/Resend)
- Discord DM (bot)
- Slack webhook (enterprise)
- SMS (critical only, enterprise)

---

## 🔄 Maintenance Tasks

### Daily (Celery Beat)
- [ ] Expire keys past `expires_at`
- [ ] Reset monthly quotas (1st of month)
- [ ] Send quota warning emails (80%, 100%)
- [ ] Prune old Redis rate limit data

### Weekly
- [ ] Rotate keys approaching expiry (notify owners)
- [ ] Generate usage reports per tenant
- [ ] Clean up `api_key_usage` partitions older than 13 months
- [ ] Audit log integrity check

### Monthly
- [ ] Cost reconciliation (actual vs tracked)
- [ ] Key security review (unused keys, excessive permissions)
- [ ] Performance review (slow queries, index usage)
- [ ] Backup verification

### On-Demand
- [ ] Emergency key revocation (admin)
- [ ] Bulk key rotation (security incident)
- [ ] Quota override (support)

---

## 🚀 Deployment Plan

### Phase 1: Backend (Week 1)
- [ ] Database migration (Alembic)
- [ ] API endpoints (CRUD + auth)
- [ ] Middleware (key validation, rate limiting)
- [ ] Redis integration
- [ ] Unit tests (pytest)

### Phase 2: Frontend (Week 2)
- [ ] Studio admin panel (key management UI)
- [ ] Usage dashboard (charts)
- [ ] Key creation wizard
- [ ] Settings page (scopes, limits)

### Phase 3: Integration (Week 3)
- [ ] Hook into existing auth system
- [ ] Replace hardcoded API keys with user keys
- [ ] Add key usage to billing system
- [ ] Alert system integration

### Phase 4: Production (Week 4)
- [ ] Load testing (1000 req/s)
- [ ] Security audit (penetration test)
- [ ] Documentation (API docs, user guide)
- [ ] Monitoring (Sentry, Prometheus)
- [ ] Gradual rollout (10% → 50% → 100%)

---

## 📈 Success Metrics

| Metric | Target |
|--------|--------|
| Key generation time | < 500ms |
| Key validation time | < 10ms (cached) |
| Rate limit enforcement | < 5ms |
| API uptime | 99.99% |
| False positive rate (alerts) | < 1% |
| User satisfaction (key mgmt) | > 4.5/5 |

---

## 🛡️ Compliance & Security

- **GDPR**: Right to deletion (cascade delete all key data)
- **SOC 2**: Audit logs retained 2 years, immutable
- **PCI DSS**: Keys never logged in plaintext, only prefix
- **ISO 27001**: Key rotation policy, access controls
- **HIPAA**: PHI data never in key metadata (enforced by schema)
