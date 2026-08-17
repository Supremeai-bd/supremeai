# Configuration Management

## Overview

SupremeAI 2.0 uses a **three-layer configuration architecture** to manage settings across different scopes and lifecycles. This document explains each layer, how they interact, and best practices for configuration management.

## Configuration Layers

### Layer 1: Static Application Settings (`config.py`)

**File:** `backend/core/config.py` (980 lines)
**Purpose:** Application-wide static configuration loaded from environment variables at startup
**Scope:** Global, per-deployment
**Lifecycle:** Loaded once at startup, immutable during runtime

The `Settings` class (Pydantic `BaseSettings`) is the single source of truth for:
- API endpoints and versioning
- LLM gateway timeouts and connection limits
- Circuit breaker thresholds
- Authentication settings (JWT, docs auth)
- Database connection strings
- Redis configuration
- Feature flags

**Key Principles:**
- **Fail-Fast**: Missing required env vars cause startup crash (`sys.exit(1)`)
- **Zero Hardcode**: All values come from env vars or GCP Secret Manager
- **Environment-Aware**: Different defaults for `local`, `staging`, `production`

**Example:**
```python
from core.config import settings

# Access configuration
api_version = settings.API_V1_STR
timeout = settings.LLM_READ_TIMEOUT
```

### Layer 2: Runtime Config Cache (`config_cache.py`)

**File:** `backend/core/config_cache.py` (229 lines)
**Purpose:** TTL-based cache for database-driven runtime configuration
**Scope:** Global, per-deployment
**Lifecycle:** Loaded at startup, refreshed periodically (TTL-based)

The `ConfigCache` class provides:
- In-memory caching of DB-driven config values
- TTL-based cache invalidation
- Fallback to default values when DB is unavailable
- Real-time cache invalidation via Supabase Realtime

**Key Features:**
- **Default Configs**: Built-in defaults for all config keys
- **TTL Refresh**: Automatic cache refresh after TTL expires
- **DB Persistence**: Changes persist to Supabase
- **Event-Driven Invalidation**: Cache invalidated on DB changes

**Example:**
```python
from core.config_cache import config_cache

# Get cached config value
threshold = config_cache.get("cache_threshold_code", default=0.95)

# Force refresh
config_cache.refresh()
```

### Layer 3: Tenant-Specific Dynamic Config (`config_proxy.py`)

**File:** `backend/core/config_proxy.py` (92 lines)
**Purpose:** Tenant-specific dynamic configuration with per-tenant caching
**Scope:** Per-tenant
**Lifecycle:** Loaded per-request, cached with 1-minute TTL

The `DynamicConfigProxy` class provides:
- Per-tenant configuration isolation
- Firestore-backed config storage
- 1-minute TTL caching per tenant
- Fallback to defaults

**Example:**
```python
from core.config_proxy import DynamicConfigProxy

# Create proxy for a tenant
proxy = DynamicConfigProxy(tenant_id="tenant_123", db=firestore_db)

# Get tenant-specific config
value = await proxy.get("some_setting", default="default_value")
```

## Configuration Data Files

Static configuration data is stored in JSON files under `backend/config/`:

| File | Purpose |
|------|---------|
| `backend/config/byoc_limits.json` | BYOC (Bring Your Own Cloud) resource limits |
| `backend/config/constitutional_rules.json` | AI constitutional rules and constraints |
| `backend/config/pricing_tiers.json` | Pricing tier definitions |
| `backend/config/routing_policy.json` | LLM provider routing policies |

## Environment Variables

### Required Environment Variables

| Variable | Layer | Description |
|----------|-------|-------------|
| `GEMINI_API_KEY` | 1 | Google Gemini API key |
| `OPENAI_API_KEY` | 1 | OpenAI API key |
| `REDIS_URL` | 1 | Redis connection string |
| `DATABASE_URL` | 1 | PostgreSQL connection string |

### Optional Environment Variables

| Variable | Layer | Default | Description |
|----------|-------|---------|-------------|
| `ENV` | 1 | `local` | Environment (local/staging/production) |
| `DEBUG` | 1 | `True` | Enable debug mode |
| `LLM_CONNECT_TIMEOUT` | 1 | `5.0` | LLM connection timeout (seconds) |
| `LLM_READ_TIMEOUT` | 1 | `30.0` | LLM read timeout (seconds) |
| `CIRCUIT_FAILURE_THRESHOLD` | 1 | `5` | Circuit breaker failure threshold |
| `CIRCUIT_COOLDOWN_SECONDS` | 1 | `30.0` | Circuit breaker cooldown (seconds) |

## Best Practices

### 1. Use the Right Layer

- **Layer 1 (config.py)**: For deployment-wide static settings (API keys, timeouts, thresholds)
- **Layer 2 (config_cache.py)**: For runtime-configurable settings that may change without restart
- **Layer 3 (config_proxy.py)**: For tenant-specific settings in multi-tenant scenarios

### 2. Never Hardcode Values

```python
# ❌ Bad
timeout = 30

# ✅ Good
timeout = settings.LLM_READ_TIMEOUT
```

### 3. Provide Defaults

Always provide sensible defaults:

```python
# Layer 1
timeout: float = Field(default=30.0, validation_alias="LLM_READ_TIMEOUT")

# Layer 2
threshold = config_cache.get("cache_threshold_code", default=0.95)

# Layer 3
value = await proxy.get("some_setting", default="default_value")
```

### 4. Fail Fast in Production

Layer 1 settings should fail fast if required env vars are missing:

```python
# config.py enforces this automatically
# Missing GEMINI_API_KEY in production → sys.exit(1)
```

### 5. Use Secret Vault for Sensitive Data

```python
from core.security.secret_vault import secret_vault

# Fetch secrets from GCP Secret Manager
api_key = secret_vault.get("GEMINI_API_KEY")
```

## Configuration Consolidation Roadmap

### Phase 1: Documentation (Completed)
- ✅ Created this configuration management guide
- ✅ Documented all three layers and their interactions

### Phase 2: Code-Level Consolidation
- **Sub-config Classes**: Split `config.py` into `DatabaseConfig`, `SecurityConfig`, `LLMConfig` sub-classes
- **Unified Interface**: Create a `ConfigManager` that wraps all three layers
- **Magic Number Elimination**: Move hardcoded thresholds to `constants.py`

### Phase 3: Runtime Optimization
- **Lazy Loading**: Load config layers on-demand
- **Cache Coalescing**: Prevent thundering herd on cache refresh
- **Config Validation**: Add schema validation for DB-driven configs

## Related Files

| File | Layer | Description |
|------|-------|-------------|
| `backend/core/config.py` | 1 | Static application settings |
| `backend/core/config_cache.py` | 2 | Runtime config cache |
| `backend/core/config_proxy.py` | 3 | Tenant-specific config |
| `backend/core/constants.py` | - | Dynamic constants via proxy |
| `backend/config/*.json` | - | Static config data files |
| `backend/core/security/secret_vault.py` | - | Secret management |
