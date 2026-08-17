# SupremeAI 2.0 — Configuration Documentation

**Version**: 2.0.0  
**Last Updated**: 2025-01-04  
**Status**: Living Document  
**Classification**: Internal  

---

## ⚙️ Configuration Overview

SupremeAI 2.0 uses a **hierarchical configuration system** that supports multiple environments (local, staging, production) with environment-specific overrides. Configuration is managed through environment variables, configuration files, and secret vaults.

### Configuration Principles

1. **Environment-Based**: Different configs for different environments
2. **Fail-Closed**: Default to secure settings
3. **Secret Management**: Sensitive data in vaults, not code
4. **Type Safety**: Pydantic settings for validation
5. **Override Hierarchy**: Env vars > Config files > Defaults

---

## 📁 Configuration Files

### Backend Configuration

**Location**: `backend/core/config.py`

**Type**: Pydantic Settings

**Purpose**: Central configuration management

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    # Environment
    ENV: str = "local"
    SERVICE_ROLE: str = "user"
    
    # Application
    APP_NAME: str = "SupremeAI 2.0"
    VERSION: str = "2.0.0"
    PORT: int = 8000
    HOST: str = "127.0.0.1"
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # Database
    DATABASE_URL: str
    REDIS_URL: str
    NEO4J_URL: str
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str
    QDRANT_URL: str
    QDRANT_API_KEY: str = ""
    
    # LLM Providers
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    LITELLM_API_KEY: str = ""
    
    # External Services
    FIREBASE_CREDENTIALS: str = ""
    GOOGLE_CLOUD_PROJECT: str = ""
    SENTRY_DSN: str = ""
    POSTHOG_API_KEY: str = ""
    STRIPE_API_KEY: str = ""
    
    # Feature Flags
    VOICE_ENABLED: bool = True
    VIDEO_ENABLED: bool = True
    SWARM_ENABLED: bool = True
    EVOLUTION_ENABLED: bool = True
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_REQUESTS_PER_HOUR: int = 1000
    RATE_LIMIT_REQUESTS_PER_DAY: int = 10000
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    
    # Observability
    ENABLE_METRICS: bool = True
    ENABLE_TRACING: bool = True
    OTEL_EXPORTER_ENDPOINT: str = ""

settings = Settings()
```

### Frontend Configuration

**Location**: `apps/studio-client/.env`

**Type**: Environment variables

**Purpose**: Frontend configuration

```env
# API URLs
VITE_API_URL=https://supremeai-backend-08zd.onrender.com
VITE_ADMIN_API_URL=https://supremeai-backend-secondary.onrender.com

# Firebase
VITE_FIREBASE_API_KEY=xxx
VITE_FIREBASE_AUTH_DOMAIN=xxx
VITE_FIREBASE_PROJECT_ID=xxx
VITE_FIREBASE_STORAGE_BUCKET=xxx
VITE_FIREBASE_MESSAGING_SENDER_ID=xxx
VITE_FIREBASE_APP_ID=xxx

# Features
VITE_VOICE_ENABLED=true
VITE_VIDEO_ENABLED=true
VITE_SWARM_ENABLED=true

# Environment
VITE_ENV=production
VITE_PORTAL_TYPE=user
```

### Mobile Configuration

**Location**: `apps/mobile/lib/config/app_config.dart`

**Type**: Dart constants

**Purpose**: Mobile app configuration

```dart
class AppConfig {
  // API
  static const String apiUrl = String.fromEnvironment(
    'API_URL',
    defaultValue: 'https://supremeai-backend-08zd.onrender.com',
  );
  
  // Firebase
  static const String firebaseApiKey = String.fromEnvironment('FIREBASE_API_KEY');
  static const String firebaseProjectId = String.fromEnvironment('FIREBASE_PROJECT_ID');
  
  // Features
  static const bool voiceEnabled = bool.fromEnvironment('VOICE_ENABLED', defaultValue: true);
  static const bool videoEnabled = bool.fromEnvironment('VIDEO_ENABLED', defaultValue: true);
}
```

---

## 🔧 Configuration Categories

### 1. Application Configuration

**Purpose**: Core application settings

**Settings**:
```python
# Application
APP_NAME: str = "SupremeAI 2.0"
VERSION: str = "2.0.0"
ENV: str = "local"  # local, staging, production
SERVICE_ROLE: str = "user"  # user, admin
PORT: int = 8000
HOST: str = "127.0.0.1"
DEBUG: bool = False
```

**Usage**:
```python
from core.config import settings

print(f"Running {settings.APP_NAME} v{settings.VERSION}")
print(f"Environment: {settings.ENV}")
```

---

### 2. Security Configuration

**Purpose**: Authentication and authorization settings

**Settings**:
```python
# JWT
SECRET_KEY: str  # Must be set in production
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

# API Keys
API_KEY_HASH_ALGORITHM: str = "HMAC-SHA256"
API_KEY_PREFIX_LENGTH: int = 20

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
RATE_LIMIT_REQUESTS_PER_HOUR: int = 1000
RATE_LIMIT_REQUESTS_PER_DAY: int = 10000

# CORS
CORS_ORIGINS: list[str] = ["http://localhost:3000"]
CORS_ALLOW_CREDENTIALS: bool = True
CORS_ALLOW_METHODS: list[str] = ["*"]
CORS_ALLOW_HEADERS: list[str] = ["*"]
```

**Usage**:
```python
# JWT token creation
from core.security.auth_middleware import create_access_token

token = create_access_token(
    data={"sub": user_id},
    expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
)
```

---

### 3. Database Configuration

**Purpose**: Database connection settings

**Settings**:
```python
# PostgreSQL
DATABASE_URL: str  # postgresql+asyncpg://user:pass@host:5432/db

# Connection Pool
DB_POOL_SIZE: int = 5
DB_MAX_OVERFLOW: int = 10
DB_POOL_RECYCLE: int = 3600
DB_POOL_PRE_PING: bool = True

# Redis
REDIS_URL: str  # redis://:password@host:6379
REDIS_MAX_CONNECTIONS: int = 50
REDIS_SOCKET_TIMEOUT: int = 5

# Neo4j
NEO4J_URL: str  # neo4j://host:7687
NEO4J_USER: str = "neo4j"
NEO4J_PASSWORD: str

# Qdrant
QDRANT_URL: str  # https://cluster.qdrant.tech
QDRANT_API_KEY: str = ""
QDRANT_COLLECTION_NAME: str = "default"
```

**Usage**:
```python
from core.database.session import get_session

async with get_session() as session:
    # Use session
    pass
```

---

### 4. LLM Configuration

**Purpose**: LLM provider settings

**Settings**:
```python
# OpenAI
OPENAI_API_KEY: str
OPENAI_ORG_ID: str = ""
OPENAI_DEFAULT_MODEL: str = "gpt-4-turbo-preview"
OPENAI_FALLBACK_MODEL: str = "gpt-3.5-turbo"
OPENAI_MAX_TOKENS: int = 4096
OPENAI_TEMPERATURE: float = 0.7
OPENAI_TIMEOUT: int = 60

# Anthropic
ANTHROPIC_API_KEY: str
ANTHROPIC_DEFAULT_MODEL: str = "claude-3-sonnet-20240229"
ANTHROPIC_FALLBACK_MODEL: str = "claude-3-haiku-20240307"
ANTHROPIC_MAX_TOKENS: int = 4096
ANTHROPIC_TIMEOUT: int = 60

# LiteLLM
LITELLM_API_KEY: str
LITELLM_DEFAULT_MODEL: str = "gpt-4-turbo-preview"

# Gateway
LLM_CACHE_TTL: int = 3600  # 1 hour
LLM_FALLBACK_ENABLED: bool = True
LLM_COST_TRACKING_ENABLED: bool = True
```

**Usage**:
```python
from core.llm.gateway import LLMGateway

gateway = LLMGateway()

response = await gateway.generate(
    provider="openai",
    model=settings.OPENAI_DEFAULT_MODEL,
    messages=[...]
)
```

---

### 5. Feature Flags

**Purpose**: Enable/disable features

**Settings**:
```python
# AI Features
VOICE_ENABLED: bool = True
VIDEO_ENABLED: bool = True
SWARM_ENABLED: bool = True
EVOLUTION_ENABLED: bool = True
ADAPTIVE_ENGINE_ENABLED: bool = True

# Security Features
PROMPT_FIREWALL_ENABLED: bool = True
INPUT_SANITIZATION_ENABLED: bool = True
AUDIT_LOGGING_ENABLED: bool = True

# Performance Features
CACHE_ENABLED: bool = True
CIRCUIT_BREAKER_ENABLED: bool = True
RATE_LIMITING_ENABLED: bool = True

# Monitoring
METRICS_ENABLED: bool = True
TRACING_ENABLED: bool = True
HEALTH_CHECKS_ENABLED: bool = True
```

**Usage**:
```python
if settings.VOICE_ENABLED:
    # Enable voice features
    pass
```

---

### 6. Logging Configuration

**Purpose**: Logging settings

**Settings**:
```python
# Logging
LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT: str = "json"  # json, text
LOG_FILE: str = "logs/app.log"
LOG_ROTATION: str = "100 MB"
LOG_RETENTION: str = "30 days"

# Loguru
LOGURU_FORMAT: str = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
```

**Usage**:
```python
from loguru import logger

logger.info("Application started")
logger.debug("Debug message")
logger.error("Error occurred", exc_info=True)
```

---

### 7. Observability Configuration

**Purpose**: Monitoring and tracing

**Settings**:
```python
# Metrics
ENABLE_METRICS: bool = True
METRICS_PORT: int = 9090
PROMETHEUS_MULTIPROC_DIR: str = "/tmp"

# Tracing
ENABLE_TRACING: bool = True
OTEL_EXPORTER_ENDPOINT: str = "http://localhost:4317"
OTEL_SERVICE_NAME: str = "supremeai-backend"
OTEL_SERVICE_VERSION: str = "2.0.0"

# Sentry
SENTRY_DSN: str = ""
SENTRY_ENVIRONMENT: str = "production"
SENTRY_TRACES_SAMPLE_RATE: float = 0.1

# PostHog
POSTHOG_API_KEY: str = ""
POSTHOG_HOST: str = "https://app.posthog.com"
```

---

### 8. External Services Configuration

**Purpose**: Third-party service settings

**Settings**:
```python
# Firebase
FIREBASE_CREDENTIALS: str  # JSON string or file path
FIREBASE_PROJECT_ID: str = ""

# Google Cloud
GOOGLE_CLOUD_PROJECT: str = ""
GOOGLE_APPLICATION_CREDENTIALS: str = ""
GOOGLE_CLOUD_STORAGE_BUCKET: str = ""

# AWS
AWS_ACCESS_KEY_ID: str = ""
AWS_SECRET_ACCESS_KEY: str = ""
AWS_REGION: str = "us-east-1"
AWS_S3_BUCKET: str = ""

# Stripe
STRIPE_API_KEY: str = ""
STRIPE_WEBHOOK_SECRET: str = ""

# GitHub
GITHUB_TOKEN: str = ""
GITHUB_WEBHOOK_SECRET: str = ""
```

---

## 🔄 Configuration Hierarchy

### Override Order

1. **Environment Variables** (highest priority)
2. **`.env` file**
3. **Configuration files** (JSON, YAML)
4. **Default values** (lowest priority)

### Example

```python
# Default in code
DATABASE_URL: str = "postgresql://localhost/supremeai"

# Override in .env
DATABASE_URL=postgresql://user:pass@host:5432/supremeai

# Override with env var
export DATABASE_URL=postgresql://prod:pass@prod-host:5432/supremeai
```

---

## 🌍 Environment-Specific Configuration

### Local Development

**File**: `.env.local`

```env
ENV=local
SERVICE_ROLE=user
DEBUG=true
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/supremeai
REDIS_URL=redis://localhost:6379
NEO4J_URL=neo4j://localhost:7687
QDRANT_URL=http://localhost:6333
SECRET_KEY=dev-secret-key-change-in-production
LOG_LEVEL=DEBUG
```

### Staging

**File**: `.env.staging`

```env
ENV=staging
SERVICE_ROLE=user
DEBUG=false
DATABASE_URL=postgresql+asyncpg://user:password@staging-db:5432/supremeai
REDIS_URL=redis://staging-redis:6379
NEO4J_URL=neo4j://staging-neo4j:7687
QDRANT_URL=https://staging-qdrant.qdrant.tech
SECRET_KEY=${STAGING_SECRET_KEY}
LOG_LEVEL=INFO
```

### Production

**File**: `.env.production` (not committed, use secrets)

```env
ENV=production
SERVICE_ROLE=user
DEBUG=false
DATABASE_URL=${DATABASE_URL}  # From Render
REDIS_URL=${REDIS_URL}  # From Render
NEO4J_URL=${NEO4J_URL}  # From Render
QDRANT_URL=${QDRANT_URL}  # From Render
SECRET_KEY=${SECRET_KEY}  # From secret vault
LOG_LEVEL=WARNING
```

---

## 🔐 Secret Management

### Secret Vault Integration

**Tool**: Infisical

**Purpose**: Centralized secret management

**Configuration**:
```python
INFISICAL_URL: str = "https://app.infisical.com"
INFISICAL_PROJECT_ID: str = "supremeai"
INFISICAL_ENVIRONMENT: str = "production"
INFISICAL_API_KEY: str
```

**Secrets Stored**:
- `SECRET_KEY` - JWT signing key
- `DATABASE_URL` - Database connection string
- `REDIS_URL` - Redis connection string
- `OPENAI_API_KEY` - OpenAI API key
- `ANTHROPIC_API_KEY` - Anthropic API key
- `FIREBASE_CREDENTIALS` - Firebase service account
- `STRIPE_API_KEY` - Stripe API key

**Retrieval**:
```python
from core.security.secret_vault import get_secret

secret_key = await get_secret("SECRET_KEY")
```

---

## 📝 Configuration Best Practices

### 1. Never Commit Secrets

**Bad**:
```python
SECRET_KEY = "my-secret-key"  # ❌ Never do this
```

**Good**:
```python
SECRET_KEY: str = os.getenv("SECRET_KEY")  # ✅ Use env vars
```

### 2. Use Type Hints

**Bad**:
```python
DEBUG = True  # ❌ No type hint
```

**Good**:
```python
DEBUG: bool = False  # ✅ Type-safe
```

### 3. Provide Defaults

**Bad**:
```python
PORT = int(os.getenv("PORT"))  # ❌ Crashes if not set
```

**Good**:
```python
PORT: int = int(os.getenv("PORT", "8000"))  # ✅ Has default
```

### 4. Validate Configuration

**Bad**:
```python
DATABASE_URL = os.getenv("DATABASE_URL")  # ❌ No validation
```

**Good**:
```python
DATABASE_URL: str = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is required")  # ✅ Validates
```

---

## 🔄 Configuration Changes

### Adding New Configuration

1. **Add to Settings class**:
   ```python
   class Settings(BaseSettings):
       NEW_SETTING: str
   ```

2. **Add to `.env.example`**:
   ```env
   NEW_SETTING=default_value
   ```

3. **Document in this file**

4. **Update deployment configs** (render.yaml, vercel.json, etc.)

### Changing Configuration

1. **Update code**
2. **Update `.env` files**
3. **Update deployment configs**
4. **Test in staging**
5. **Deploy to production**
6. **Update documentation**

---

## 🔗 Related Documents

- [09-ENVIRONMENT_DOCUMENTATION.md](09-ENVIRONMENT_DOCUMENTATION.md) - Environment variables
- [21-DEPLOYMENT_DOCUMENTATION.md](21-DEPLOYMENT_DOCUMENTATION.md) - Deployment
- [23-SECURITY_DOCUMENTATION.md](23-SECURITY_DOCUMENTATION.md) - Security

---

## ✅ Configuration Verification

**How to verify configuration**:

1. **Check Configuration Loads**:
   ```bash
   cd backend
   python -c "from core.config import settings; print(settings.ENV)"
   ```

2. **Verify Required Settings**:
   ```bash
   python -c "
   from core.config import settings
   required = ['SECRET_KEY', 'DATABASE_URL', 'REDIS_URL']
   for key in required:
       assert getattr(settings, key), f'{key} is required'
   print('✓ All required settings present')
   "
   ```

3. **Test Configuration in Different Environments**:
   ```bash
   # Local
   ENV=local python -c "from core.config import settings; print(settings.ENV)"
   
   # Production
   ENV=production python -c "from core.config import settings; print(settings.ENV)"
   ```

---

**Document Status**: ✅ Complete and Verified  
**Next Review**: 2025-02-04  
**Owner**: Engineering Team