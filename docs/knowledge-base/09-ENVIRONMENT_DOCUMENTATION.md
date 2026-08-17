# SupremeAI 2.0 — Environment Documentation

**Version**: 2.0.0  
**Last Updated**: 2025-01-04  
**Status**: Living Document  
**Classification**: Internal  

---

## 🌍 Environment Overview

This document provides a comprehensive registry of all environment variables used in the SupremeAI 2.0 project, including their purpose, type, default values, and security classification.

### Environment Management

**Tool**: Pydantic Settings + python-dotenv

**Environments**:
- **local**: Local development
- **staging**: Staging environment
- **production**: Production environment

**Configuration Files**:
- `.env` - Main environment file (git-ignored)
- `.env.example` - Template for environment variables
- `.env.local` - Local overrides (git-ignored)
- `.env.staging` - Staging config
- `.env.production` - Production config (not committed)

---

## 🔐 Environment Variable Registry

### Critical Variables (Required in Production)

These variables MUST be set in production. The application will fail to start without them.

| Variable | Type | Purpose | Default | Security Level |
|----------|------|---------|---------|----------------|
| `SECRET_KEY` | string | JWT signing key | None | 🔴 Critical |
| `DATABASE_URL` | string | PostgreSQL connection | None | 🔴 Critical |
| `REDIS_URL` | string | Redis connection | None | 🔴 Critical |
| `NEO4J_URL` | string | Neo4j connection | None | 🟡 High |
| `NEO4J_PASSWORD` | string | Neo4j password | None | 🔴 Critical |
| `QDRANT_URL` | string | Qdrant connection | None | 🟡 High |

**Example**:
```env
SECRET_KEY=your-secret-key-here-min-32-chars
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/supremeai
REDIS_URL=redis://:password@host:6379
NEO4J_URL=neo4j://host:7687
NEO4J_PASSWORD=your-neo4j-password
QDRANT_URL=https://cluster.qdrant.tech
```

---

### AI/LLM Variables

| Variable | Type | Purpose | Default | Security Level |
|----------|------|---------|---------|----------------|
| `OPENAI_API_KEY` | string | OpenAI API key | "" | 🔴 Critical |
| `OPENAI_ORG_ID` | string | OpenAI organization ID | "" | 🟡 High |
| `ANTHROPIC_API_KEY` | string | Anthropic API key | "" | 🔴 Critical |
| `LITELLM_API_KEY` | string | LiteLLM API key | "" | 🔴 Critical |

**Example**:
```env
OPENAI_API_KEY=sk-...
OPENAI_ORG_ID=org-...
ANTHROPIC_API_KEY=sk-ant-...
LITELLM_API_KEY=sk-...
```

---

### Cloud Services Variables

| Variable | Type | Purpose | Default | Security Level |
|----------|------|---------|---------|----------------|
| `FIREBASE_CREDENTIALS` | string | Firebase service account JSON | "" | 🔴 Critical |
| `FIREBASE_PROJECT_ID` | string | Firebase project ID | "" | 🟡 High |
| `GOOGLE_CLOUD_PROJECT` | string | GCP project ID | "" | 🟡 High |
| `GOOGLE_APPLICATION_CREDENTIALS` | string | GCP service account path | "" | 🔴 Critical |
| `GOOGLE_CLOUD_STORAGE_BUCKET` | string | GCS bucket name | "" | 🟡 High |
| `AWS_ACCESS_KEY_ID` | string | AWS access key | "" | 🔴 Critical |
| `AWS_SECRET_ACCESS_KEY` | string | AWS secret key | "" | 🔴 Critical |
| `AWS_REGION` | string | AWS region | "us-east-1" | 🟢 Low |
| `AWS_S3_BUCKET` | string | S3 bucket name | "" | 🟡 High |

**Example**:
```env
FIREBASE_CREDENTIALS={"type":"service_account",...}
FIREBASE_PROJECT_ID=my-project
GOOGLE_CLOUD_PROJECT=my-project
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
AWS_S3_BUCKET=my-bucket
```

---

### Monitoring & Analytics Variables

| Variable | Type | Purpose | Default | Security Level |
|----------|------|---------|---------|----------------|
| `SENTRY_DSN` | string | Sentry error tracking DSN | "" | 🟡 High |
| `SENTRY_ENVIRONMENT` | string | Sentry environment | "production" | 🟢 Low |
| `SENTRY_TRACES_SAMPLE_RATE` | float | Sentry trace sampling | 0.1 | 🟢 Low |
| `POSTHOG_API_KEY` | string | PostHog analytics key | "" | 🟡 High |
| `POSTHOG_HOST` | string | PostHog host | "https://app.posthog.com" | 🟢 Low |

**Example**:
```env
SENTRY_DSN=https://...@sentry.io/...
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1
POSTHOG_API_KEY=phc_...
POSTHOG_HOST=https://app.posthog.com
```

---

### Application Variables

| Variable | Type | Purpose | Default | Security Level |
|----------|------|---------|---------|----------------|
| `ENV` | string | Environment (local/staging/production) | "local" | 🟢 Low |
| `SERVICE_ROLE` | string | Service role (user/admin) | "user" | 🟢 Low |
| `APP_NAME` | string | Application name | "SupremeAI 2.0" | 🟢 Low |
| `VERSION` | string | Application version | "2.0.0" | 🟢 Low |
| `PORT` | int | Server port | 8000 | 🟢 Low |
| `HOST` | string | Server host | "127.0.0.1" | 🟢 Low |
| `DEBUG` | bool | Debug mode | false | 🟡 High |

**Example**:
```env
ENV=production
SERVICE_ROLE=user
APP_NAME=SupremeAI 2.0
VERSION=2.0.0
PORT=8000
HOST=0.0.0.0
DEBUG=false
```

---

### Security Variables

| Variable | Type | Purpose | Default | Security Level |
|----------|------|---------|---------|----------------|
| `ALGORITHM` | string | JWT algorithm | "HS256" | 🟢 Low |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | int | JWT expiration | 60 | 🟢 Low |
| `API_KEY_HASH_ALGORITHM` | string | API key hashing | "HMAC-SHA256" | 🟢 Low |
| `CORS_ORIGINS` | list | Allowed CORS origins | ["http://localhost:3000"] | 🟡 High |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | int | Rate limit per minute | 60 | 🟢 Low |
| `RATE_LIMIT_REQUESTS_PER_HOUR` | int | Rate limit per hour | 1000 | 🟢 Low |
| `RATE_LIMIT_REQUESTS_PER_DAY` | int | Rate limit per day | 10000 | 🟢 Low |

**Example**:
```env
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
API_KEY_HASH_ALGORITHM=HMAC-SHA256
CORS_ORIGINS=["https://example.com","https://app.example.com"]
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_REQUESTS_PER_HOUR=1000
RATE_LIMIT_REQUESTS_PER_DAY=10000
```

---

### Database Variables

| Variable | Type | Purpose | Default | Security Level |
|----------|------|---------|---------|----------------|
| `DB_POOL_SIZE` | int | Connection pool size | 5 | 🟢 Low |
| `DB_MAX_OVERFLOW` | int | Max overflow connections | 10 | 🟢 Low |
| `DB_POOL_RECYCLE` | int | Pool recycle time (seconds) | 3600 | 🟢 Low |
| `DB_POOL_PRE_PING` | bool | Enable pool pre-ping | true | 🟢 Low |
| `REDIS_MAX_CONNECTIONS` | int | Redis max connections | 50 | 🟢 Low |
| `REDIS_SOCKET_TIMEOUT` | int | Redis socket timeout | 5 | 🟢 Low |
| `NEO4J_USER` | string | Neo4j username | "neo4j" | 🟢 Low |
| `QDRANT_API_KEY` | string | Qdrant API key | "" | 🟡 High |
| `QDRANT_COLLECTION_NAME` | string | Qdrant collection | "default" | 🟢 Low |

**Example**:
```env
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_RECYCLE=3600
DB_POOL_PRE_PING=true
REDIS_MAX_CONNECTIONS=50
REDIS_SOCKET_TIMEOUT=5
NEO4J_USER=neo4j
QDRANT_API_KEY=...
QDRANT_COLLECTION_NAME=default
```

---

### Feature Flags

| Variable | Type | Purpose | Default | Security Level |
|----------|------|---------|---------|----------------|
| `VOICE_ENABLED` | bool | Enable voice features | true | 🟢 Low |
| `VIDEO_ENABLED` | bool | Enable video features | true | 🟢 Low |
| `SWARM_ENABLED` | bool | Enable swarm agents | true | 🟢 Low |
| `EVOLUTION_ENABLED` | bool | Enable evolution engine | true | 🟢 Low |
| `ADAPTIVE_ENGINE_ENABLED` | bool | Enable adaptive engine | true | 🟢 Low |
| `PROMPT_FIREWALL_ENABLED` | bool | Enable prompt firewall | true | 🟡 High |
| `INPUT_SANITIZATION_ENABLED` | bool | Enable input sanitization | true | 🟡 High |
| `AUDIT_LOGGING_ENABLED` | bool | Enable audit logging | true | 🟡 High |
| `CACHE_ENABLED` | bool | Enable caching | true | 🟢 Low |
| `CIRCUIT_BREAKER_ENABLED` | bool | Enable circuit breaker | true | 🟢 Low |
| `RATE_LIMITING_ENABLED` | bool | Enable rate limiting | true | 🟡 High |

**Example**:
```env
VOICE_ENABLED=true
VIDEO_ENABLED=true
SWARM_ENABLED=true
EVOLUTION_ENABLED=true
ADAPTIVE_ENGINE_ENABLED=true
PROMPT_FIREWALL_ENABLED=true
INPUT_SANITIZATION_ENABLED=true
AUDIT_LOGGING_ENABLED=true
CACHE_ENABLED=true
CIRCUIT_BREAKER_ENABLED=true
RATE_LIMITING_ENABLED=true
```

---

### Logging Variables

| Variable | Type | Purpose | Default | Security Level |
|----------|------|---------|---------|----------------|
| `LOG_LEVEL` | string | Log level (DEBUG/INFO/WARNING/ERROR) | "INFO" | 🟢 Low |
| `LOG_FORMAT` | string | Log format (json/text) | "json" | 🟢 Low |
| `LOG_FILE` | string | Log file path | "logs/app.log" | 🟢 Low |
| `LOG_ROTATION` | string | Log rotation size | "100 MB" | 🟢 Low |
| `LOG_RETENTION` | string | Log retention period | "30 days" | 🟢 Low |
| `UVICORN_LOG_LEVEL` | string | Uvicorn log level | "info" | 🟢 Low |
| `UVICORN_ACCESS_LOG` | bool | Enable access log | true | 🟢 Low |
| `UVICORN_KEEP_ALIVE_TIMEOUT` | int | Keep alive timeout | 30 | 🟢 Low |

**Example**:
```env
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE=logs/app.log
LOG_ROTATION=100 MB
LOG_RETENTION=30 days
UVICORN_LOG_LEVEL=info
UVICORN_ACCESS_LOG=true
UVICORN_KEEP_ALIVE_TIMEOUT=30
```

---

### Observability Variables

| Variable | Type | Purpose | Default | Security Level |
|----------|------|---------|---------|----------------|
| `ENABLE_METRICS` | bool | Enable Prometheus metrics | true | 🟢 Low |
| `METRICS_PORT` | int | Metrics server port | 9090 | 🟢 Low |
| `ENABLE_TRACING` | bool | Enable OpenTelemetry tracing | true | 🟢 Low |
| `OTEL_EXPORTER_ENDPOINT` | string | OTLP exporter endpoint | "" | 🟢 Low |
| `OTEL_SERVICE_NAME` | string | Service name for tracing | "supremeai-backend" | 🟢 Low |
| `OTEL_SERVICE_VERSION` | string | Service version | "2.0.0" | 🟢 Low |

**Example**:
```env
ENABLE_METRICS=true
METRICS_PORT=9090
ENABLE_TRACING=true
OTEL_EXPORTER_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=supremeai-backend
OTEL_SERVICE_VERSION=2.0.0
```

---

### Deployment Variables

| Variable | Type | Purpose | Default | Security Level |
|----------|------|---------|---------|----------------|
| `RENDER` | bool | Running on Render | false | 🟢 Low |
| `RENDER_SERVICE_ID` | string | Render service ID | "" | 🟢 Low |
| `RENDER_API_KEY` | string | Render API key | "" | 🔴 Critical |
| `VERCEL_TOKEN` | string | Vercel API token | "" | 🔴 Critical |
| `FIREBASE_TOKEN` | string | Firebase CLI token | "" | 🔴 Critical |
| `GITHUB_TOKEN` | string | GitHub API token | "" | 🔴 Critical |
| `UVICORN_WORKERS` | int | Number of Uvicorn workers | 1 | 🟢 Low |

**Example**:
```env
RENDER=true
RENDER_SERVICE_ID=srv-d9d3n58js32c738n79k0
RENDER_API_KEY=...
VERCEL_TOKEN=...
FIREBASE_TOKEN=...
GITHUB_TOKEN=...
UVICORN_WORKERS=1
```

---

### Payment Variables (Future)

| Variable | Type | Purpose | Default | Security Level |
|----------|------|---------|---------|----------------|
| `STRIPE_API_KEY` | string | Stripe API key | "" | 🔴 Critical |
| `STRIPE_WEBHOOK_SECRET` | string | Stripe webhook secret | "" | 🔴 Critical |
| `STRIPE_PRICE_ID_FREE` | string | Stripe free tier price ID | "" | 🟡 High |
| `STRIPE_PRICE_ID_PRO` | string | Stripe pro tier price ID | "" | 🟡 High |
| `STRIPE_PRICE_ID_ENTERPRISE` | string | Stripe enterprise price ID | "" | 🟡 High |

**Example**:
```env
STRIPE_API_KEY=sk_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID_FREE=price_...
STRIPE_PRICE_ID_PRO=price_...
STRIPE_PRICE_ID_ENTERPRISE=price_...
```

---

## 📋 Environment Variable Templates

### Complete .env.example

**Location**: `.env.example`

```env
# ============================================
# APPLICATION
# ============================================
ENV=local
SERVICE_ROLE=user
APP_NAME=SupremeAI 2.0
VERSION=2.0.0
PORT=8000
HOST=127.0.0.1
DEBUG=false

# ============================================
# SECURITY (REQUIRED IN PRODUCTION)
# ============================================
SECRET_KEY=your-secret-key-here-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
API_KEY_HASH_ALGORITHM=HMAC-SHA256

# ============================================
# DATABASE (REQUIRED IN PRODUCTION)
# ============================================
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/supremeai
REDIS_URL=redis://localhost:6379
NEO4J_URL=neo4j://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=

# ============================================
# AI/LLM PROVIDERS
# ============================================
OPENAI_API_KEY=
OPENAI_ORG_ID=
ANTHROPIC_API_KEY=
LITELLM_API_KEY=

# ============================================
# CLOUD SERVICES
# ============================================
FIREBASE_CREDENTIALS=
FIREBASE_PROJECT_ID=
GOOGLE_CLOUD_PROJECT=
GOOGLE_APPLICATION_CREDENTIALS=
GOOGLE_CLOUD_STORAGE_BUCKET=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1
AWS_S3_BUCKET=

# ============================================
# MONITORING & ANALYTICS
# ============================================
SENTRY_DSN=
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1
POSTHOG_API_KEY=
POSTHOG_HOST=https://app.posthog.com

# ============================================
# FEATURE FLAGS
# ============================================
VOICE_ENABLED=true
VIDEO_ENABLED=true
SWARM_ENABLED=true
EVOLUTION_ENABLED=true
ADAPTIVE_ENGINE_ENABLED=true
PROMPT_FIREWALL_ENABLED=true
INPUT_SANITIZATION_ENABLED=true
AUDIT_LOGGING_ENABLED=true
CACHE_ENABLED=true
CIRCUIT_BREAKER_ENABLED=true
RATE_LIMITING_ENABLED=true

# ============================================
# SECURITY
# ============================================
CORS_ORIGINS=["http://localhost:3000"]
CORS_ALLOW_CREDENTIALS=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_REQUESTS_PER_HOUR=1000
RATE_LIMIT_REQUESTS_PER_DAY=10000

# ============================================
# LOGGING
# ============================================
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE=logs/app.log
LOG_ROTATION=100 MB
LOG_RETENTION=30 days
UVICORN_LOG_LEVEL=info
UVICORN_ACCESS_LOG=true
UVICORN_KEEP_ALIVE_TIMEOUT=30

# ============================================
# OBSERVABILITY
# ============================================
ENABLE_METRICS=true
METRICS_PORT=9090
ENABLE_TRACING=true
OTEL_EXPORTER_ENDPOINT=
OTEL_SERVICE_NAME=supremeai-backend
OTEL_SERVICE_VERSION=2.0.0

# ============================================
# DEPLOYMENT
# ============================================
RENDER=false
RENDER_SERVICE_ID=
RENDER_API_KEY=
VERCEL_TOKEN=
FIREBASE_TOKEN=
GITHUB_TOKEN=
UVICORN_WORKERS=1

# ============================================
# PAYMENT (FUTURE)
# ============================================
STRIPE_API_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_ID_FREE=
STRIPE_PRICE_ID_PRO=
STRIPE_PRICE_ID_ENTERPRISE=
```

---

## 🔒 Security Classification

### 🔴 Critical (Must be protected)

These variables contain sensitive data that could compromise security if exposed:

- `SECRET_KEY` - JWT signing key
- `DATABASE_URL` - Database credentials
- `REDIS_URL` - Redis credentials
- `NEO4J_PASSWORD` - Neo4j password
- `OPENAI_API_KEY` - OpenAI API key
- `ANTHROPIC_API_KEY` - Anthropic API key
- `LITELLM_API_KEY` - LiteLLM API key
- `FIREBASE_CREDENTIALS` - Firebase service account
- `GOOGLE_APPLICATION_CREDENTIALS` - GCP service account
- `AWS_ACCESS_KEY_ID` - AWS access key
- `AWS_SECRET_ACCESS_KEY` - AWS secret key
- `RENDER_API_KEY` - Render API key
- `VERCEL_TOKEN` - Vercel API token
- `FIREBASE_TOKEN` - Firebase CLI token
- `GITHUB_TOKEN` - GitHub API token
- `STRIPE_API_KEY` - Stripe API key
- `STRIPE_WEBHOOK_SECRET` - Stripe webhook secret

**Protection Measures**:
- Never commit to version control
- Store in secret vault (Infisical)
- Rotate regularly (90 days)
- Use environment-specific values
- Audit access

### 🟡 High (Should be protected)

These variables contain sensitive data that should be protected:

- `OPENAI_ORG_ID` - OpenAI organization
- `NEO4J_URL` - Neo4j connection
- `QDRANT_URL` - Qdrant connection
- `QDRANT_API_KEY` - Qdrant API key
- `FIREBASE_PROJECT_ID` - Firebase project
- `GOOGLE_CLOUD_PROJECT` - GCP project
- `GOOGLE_CLOUD_STORAGE_BUCKET` - GCS bucket
- `AWS_S3_BUCKET` - S3 bucket
- `SENTRY_DSN` - Sentry DSN
- `POSTHOG_API_KEY` - PostHog API key
- `CORS_ORIGINS` - CORS configuration
- `PROMPT_FIREWALL_ENABLED` - Security feature
- `INPUT_SANITIZATION_ENABLED` - Security feature
- `AUDIT_LOGGING_ENABLED` - Security feature
- `RATE_LIMITING_ENABLED` - Security feature

**Protection Measures**:
- Use environment variables
- Avoid in logs
- Rotate when compromised

### 🟢 Low (Public information)

These variables contain non-sensitive configuration:

- `ENV` - Environment name
- `SERVICE_ROLE` - Service role
- `APP_NAME` - Application name
- `VERSION` - Version
- `PORT` - Port number
- `HOST` - Host address
- `DEBUG` - Debug mode
- `ALGORITHM` - JWT algorithm
- `LOG_LEVEL` - Log level
- `LOG_FORMAT` - Log format
- Feature flags
- Timeouts
- Pool sizes

**Protection Measures**:
- Can be committed to version control
- Document in README

---

## 🌍 Environment-Specific Configuration

### Local Development

**File**: `.env.local`

```env
# Application
ENV=local
SERVICE_ROLE=user
DEBUG=true
PORT=8000
HOST=127.0.0.1

# Security
SECRET_KEY=dev-secret-key-change-in-production-1234567890
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/supremeai
REDIS_URL=redis://localhost:6379
NEO4J_URL=neo4j://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
QDRANT_URL=http://localhost:6333

# LLM Providers (use test keys)
OPENAI_API_KEY=sk-test-...
ANTHROPIC_API_KEY=sk-ant-test-...

# Logging
LOG_LEVEL=DEBUG
LOG_FORMAT=text

# Features
VOICE_ENABLED=true
VIDEO_ENABLED=true
SWARM_ENABLED=true
```

### Staging

**File**: `.env.staging`

```env
# Application
ENV=staging
SERVICE_ROLE=user
DEBUG=false
PORT=8000
HOST=0.0.0.0

# Security
SECRET_KEY=${STAGING_SECRET_KEY}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Database
DATABASE_URL=${STAGING_DATABASE_URL}
REDIS_URL=${STAGING_REDIS_URL}
NEO4J_URL=${STAGING_NEO4J_URL}
NEO4J_PASSWORD=${STAGING_NEO4J_PASSWORD}
QDRANT_URL=${STAGING_QDRANT_URL}

# LLM Providers
OPENAI_API_KEY=${STAGING_OPENAI_API_KEY}
ANTHROPIC_API_KEY=${STAGING_ANTHROPIC_API_KEY}

# Monitoring
SENTRY_DSN=${STAGING_SENTRY_DSN}
POSTHOG_API_KEY=${STAGING_POSTHOG_API_KEY}

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### Production

**File**: `.env.production` (not committed)

```env
# Application
ENV=production
SERVICE_ROLE=user
DEBUG=false
PORT=8000
HOST=0.0.0.0

# Security
SECRET_KEY=${PRODUCTION_SECRET_KEY}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Database
DATABASE_URL=${PRODUCTION_DATABASE_URL}
REDIS_URL=${PRODUCTION_REDIS_URL}
NEO4J_URL=${PRODUCTION_NEO4J_URL}
NEO4J_PASSWORD=${PRODUCTION_NEO4J_PASSWORD}
QDRANT_URL=${PRODUCTION_QDRANT_URL}

# LLM Providers
OPENAI_API_KEY=${PRODUCTION_OPENAI_API_KEY}
ANTHROPIC_API_KEY=${PRODUCTION_ANTHROPIC_API_KEY}

# Monitoring
SENTRY_DSN=${PRODUCTION_SENTRY_DSN}
POSTHOG_API_KEY=${PRODUCTION_POSTHOG_API_KEY}

# Logging
LOG_LEVEL=WARNING
LOG_FORMAT=json

# Features
VOICE_ENABLED=true
VIDEO_ENABLED=true
SWARM_ENABLED=true
```

---

## 🔄 Environment Variable Management

### Setting Environment Variables

#### Local Development

**Using .env file**:
```bash
# Copy example
cp .env.example .env

# Edit with your values
nano .env
```

**Using export**:
```bash
export SECRET_KEY=your-secret-key
export DATABASE_URL=postgresql://...
```

#### Render

**Via render.yaml**:
```yaml
envVars:
  - key: SECRET_KEY
    generateValue: true
  - key: DATABASE_URL
    fromDatabase:
      name: supremeai-db
      property: connectionString
```

**Via Dashboard**:
1. Go to Render Dashboard
2. Select service
3. Go to Environment
4. Add environment variable

#### Vercel

**Via vercel.json**:
```json
{
  "env": {
    "VITE_API_URL": "https://api.example.com"
  }
}
```

**Via Dashboard**:
1. Go to Vercel Dashboard
2. Select project
3. Go to Settings → Environment Variables
4. Add variable

---

## 🔍 Environment Variable Validation

### Validation in Code

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True
    )
    
    # Required variables
    SECRET_KEY: str = Field(..., min_length=32)
    DATABASE_URL: str
    REDIS_URL: str
    
    # Optional variables
    OPENAI_API_KEY: str = ""
    
    # Validated variables
    PORT: int = Field(default=8000, ge=1, le=65535)
    LOG_LEVEL: str = Field(default="INFO", regex="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    
    @validator("DATABASE_URL")
    def validate_database_url(cls, v):
        if not v.startswith("postgresql"):
            raise ValueError("DATABASE_URL must be PostgreSQL")
        return v

# Usage
try:
    settings = Settings()
except ValidationError as e:
    print(f"Configuration error: {e}")
```

---

## 📝 Environment Variable Best Practices

### 1. Naming Convention

**Format**: `UPPER_SNAKE_CASE`

**Good**:
```env
DATABASE_URL
REDIS_MAX_CONNECTIONS
OPENAI_API_KEY
```

**Bad**:
```env
databaseUrl  # ❌ camelCase
redis_max_connections  # ❌ snake_case
openai_api_key  # ❌ lowercase
```

### 2. Group Related Variables

**Good**:
```env
# Database
DATABASE_URL=...
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10

# Redis
REDIS_URL=...
REDIS_MAX_CONNECTIONS=50
```

### 3. Provide Defaults

**Good**:
```env
PORT=8000
LOG_LEVEL=INFO
DEBUG=false
```

### 4. Document Everything

**Good**:
```env
# Database connection string (required)
# Format: postgresql+asyncpg://user:pass@host:5432/db
DATABASE_URL=...
```

---

## 🔗 Related Documents

- [08-CONFIGURATION_DOCUMENTATION.md](08-CONFIGURATION_DOCUMENTATION.md) - Configuration
- [21-DEPLOYMENT_DOCUMENTATION.md](21-DEPLOYMENT_DOCUMENTATION.md) - Deployment
- [23-SECURITY_DOCUMENTATION.md](23-SECURITY_DOCUMENTATION.md) - Security

---

## ✅ Environment Variable Verification

**How to verify environment variables**:

1. **Check Required Variables**:
   ```bash
   cd backend
   python -c "
   from core.config import settings
   required = ['SECRET_KEY', 'DATABASE_URL', 'REDIS_URL']
   missing = [var for var in required if not getattr(settings, var)]
   if missing:
       print(f'❌ Missing: {missing}')
   else:
       print('✓ All required variables set')
   "
   ```

2. **Validate Types**:
   ```bash
   python -c "
   from core.config import settings
   print(f'PORT: {settings.PORT} (type: {type(settings.PORT).__name__})')
   print(f'DEBUG: {settings.DEBUG} (type: {type(settings.DEBUG).__name__})')
   print(f'RATE_LIMIT: {settings.RATE_LIMIT_REQUESTS_PER_MINUTE} (type: {type(settings.RATE_LIMIT_REQUESTS_PER_MINUTE).__name__})')
   "
   ```

3. **Check Environment**:
   ```bash
   python -c "from core.config import settings; print(f'Environment: {settings.ENV}')"
   ```

---

**Document Status**: ✅ Complete and Verified  
**Next Review**: 2025-02-04  
**Owner**: Engineering Team