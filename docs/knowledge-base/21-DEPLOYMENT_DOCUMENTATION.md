# SupremeAI 2.0 — Deployment Documentation

**Version**: 2.0.0  
**Last Updated**: 2025-01-04  
**Status**: Living Document  
**Classification**: Internal  

---

## 🚀 Deployment Overview

SupremeAI 2.0 uses a **multi-platform deployment strategy** optimized for zero-cost operation while maintaining high availability and reliability. The system deploys across Render, Vercel, Firebase, and Cloudflare, with automated CI/CD pipelines via GitHub Actions.

### Deployment Principles

1. **Zero-Cost First**: All services run on free tiers
2. **Automated**: CI/CD pipelines handle all deployments
3. **Immutable**: Docker images are immutable and versioned
4. **Blue-Green**: Zero-downtime deployments
5. **Observable**: Comprehensive monitoring and logging
6. **Reversible**: Quick rollback capability

---

## 🏗️ Deployment Architecture

```mermaid
graph TB
    subgraph "Source Control"
        GITHUB[GitHub Repository]
        MAIN[Main Branch]
    end

    subgraph "CI/CD Pipeline"
        ACTIONS[GitHub Actions]
        TEST[Run Tests]
        BUILD[Build Docker]
        PUSH[Push to GHCR]
    end

    subgraph "Container Registry"
        GHCR[GitHub Container Registry]
        IMAGE_USER[Image: user-service]
        IMAGE_ADMIN[Image: admin-service]
    end

    subgraph "Backend Deployment"
        RENDER_USER[Render - User Service]
        RENDER_ADMIN[Render - Admin Service]
    end

    subgraph "Frontend Deployment"
        VERCEL[Vercel - User Portal]
        FIREBASE[Firebase - Admin Portal]
    end

    subgraph "Edge Layer"
        CF[Cloudflare Worker]
    end

    GITHUB --> MAIN
    MAIN --> ACTIONS
    ACTIONS --> TEST
    TEST --> BUILD
    BUILD --> PUSH
    PUSH --> GHCR
    GHCR --> IMAGE_USER
    GHCR --> IMAGE_ADMIN
    IMAGE_USER --> RENDER_USER
    IMAGE_ADMIN --> RENDER_ADMIN
    RENDER_USER --> CF
    RENDER_ADMIN --> CF
    CF --> VERCEL
    CF --> FIREBASE
```

---

## 🐳 Docker Configuration

### Production Dockerfile

**Location**: `backend/Dockerfile`

```dockerfile
# Multi-stage build for smaller image
FROM python:3.11-slim AS builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Poetry
RUN pip install poetry

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser

# Set working directory
WORKDIR /app

# Copy dependencies from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Run application
CMD ["uvicorn", "core.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### CI Dockerfile

**Location**: `backend/Dockerfile.ci`

```dockerfile
FROM python:3.11-slim

# Install all dependencies including dev
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install poetry

COPY pyproject.toml poetry.lock ./

# Install with dev dependencies for testing
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

COPY . .

CMD ["pytest", "tests/", "-v"]
```

### Docker Compose (Local Development)

**Location**: `docker-compose.yml`

```yaml
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - ENV=local
      - DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/supremeai
      - REDIS_URL=redis://redis:6379
      - NEO4J_URL=neo4j://neo4j:7687
      - QDRANT_URL=http://qdrant:6333
    depends_on:
      - postgres
      - redis
      - neo4j
      - qdrant
    volumes:
      - ./backend:/app
    command: uvicorn core.app:app --host 0.0.0.0 --port 8000 --reload

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=supremeai
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  neo4j:
    image: neo4j:5-community
    environment:
      - NEO4J_AUTH=neo4j/password
    ports:
      - "7474:7474"
      - "7687:7687"
    volumes:
      - neo4j_data:/data

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage

volumes:
  postgres_data:
  redis_data:
  neo4j_data:
  qdrant_data:
```

---

## ☁️ Render Deployment

### Configuration

**Location**: `render.yaml`

```yaml
services:
  # User Service
  - type: web
    name: supremeai-backend
    runtime: docker
    plan: free
    region: singapore
    branch: main
    dockerfile: backend/Dockerfile
    dockerContext: .
    healthCheckPath: /health
    autoDeploy: true
    envVars:
      - key: SERVICE_ROLE
        value: user
      - key: ENV
        value: production
      - key: DATABASE_URL
        fromDatabase:
          name: supremeai-db
          property: connectionString
      - key: REDIS_URL
        fromService:
          type: redis
          name: supremeai-redis
          property: connectionString
      - key: NEO4J_URL
        fromService:
          type: neo4j
          name: supremeai-neo4j
          property: connectionString
      - key: QDRANT_URL
        fromService:
          type: qdrant
          name: supremeai-qdrant
          property: connectionString
      - key: SECRET_KEY
        generateValue: true
      - key: OPENAI_API_KEY
        sync: false
      - key: ANTHROPIC_API_KEY
        sync: false

  # Admin Service
  - type: web
    name: supremeai-admin
    runtime: docker
    plan: free
    region: singapore
    branch: main
    dockerfile: backend/Dockerfile
    dockerContext: .
    healthCheckPath: /health
    autoDeploy: true
    envVars:
      - key: SERVICE_ROLE
        value: admin
      - key: ENV
        value: production
      - key: DATABASE_URL
        fromDatabase:
          name: supremeai-db
          property: connectionString
      - key: REDIS_URL
        fromService:
          type: redis
          name: supremeai-redis
          property: connectionString
      - key: SECRET_KEY
        generateValue: true

databases:
  - name: supremeai-db
    plan: free
    region: singapore

services:
  - type: redis
    name: supremeai-redis
    plan: free
    region: singapore

  - type: neo4j
    name: supremeai-neo4j
    plan: free
    region: singapore

  - type: qdrant
    name: supremeai-qdrant
    plan: free
    region: singapore
```

### Deployment Process

**Automated Deployment**:
1. Push to `main` branch
2. GitHub Actions builds Docker image
3. Image pushed to GHCR
4. Render auto-deploys from GHCR
5. Health check performed
6. Deployment verified

**Manual Deployment**:
```bash
# Trigger manual deploy
curl -X POST https://api.render.com/deploy/srv-d9d3n58js32c738n79k0 \
  -H "Authorization: Bearer $RENDER_API_KEY"
```

### Rollback Procedure

**Automatic Rollback**:
- Render automatically rolls back if health check fails
- Previous version retained for 7 days

**Manual Rollback**:
```bash
# List deployments
curl -X GET https://api.render.com/v1/services/srv-d9d3n58js32c738n79k0/deploys \
  -H "Authorization: Bearer $RENDER_API_KEY"

# Rollback to specific deployment
curl -X POST https://api.render.com/v1/services/srv-d9d3n58js32c738n79k0/deploys/{deploy_id}/rollback \
  -H "Authorization: Bearer $RENDER_API_KEY"
```

---

## ▲ Vercel Deployment

### Configuration

**Location**: `vercel.json`

```json
{
  "version": 2,
  "builds": [
    {
      "src": "apps/studio-client/package.json",
      "use": "@vercel/static-build",
      "config": {
        "distDir": "dist"
      }
    }
  ],
  "routes": [
    {
      "src": "/api/(.*)",
      "dest": "https://supremeai-backend-08zd.onrender.com/api/$1"
    },
    {
      "src": "/admin-api/(.*)",
      "dest": "https://supremeai-backend-secondary.onrender.com/admin-api/$1"
    },
    {
      "src": "/(.*)",
      "dest": "apps/studio-client/dist/$1"
    }
  ],
  "env": {
    "VITE_API_URL": "https://supremeai-backend-08zd.onrender.com"
  }
}
```

### Deployment Process

**Automated Deployment**:
1. Push to `main` branch
2. Vercel detects changes
3. Builds frontend
4. Deploys to CDN
5. Verifies deployment

**Manual Deployment**:
```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
cd apps/studio-client
vercel --prod
```

### Environment Variables

**Configuration**: Vercel Dashboard → Settings → Environment Variables

```env
VITE_API_URL=https://supremeai-backend-08zd.onrender.com
VITE_ADMIN_API_URL=https://supremeai-backend-secondary.onrender.com
VITE_FIREBASE_API_KEY=xxx
VITE_FIREBASE_AUTH_DOMAIN=xxx
VITE_FIREBASE_PROJECT_ID=xxx
```

---

## 🔥 Firebase Deployment

### Configuration

**Location**: `firebase.json`

```json
{
  "hosting": {
    "site": "supremeai-admin",
    "public": "apps/studio-client/dist-admin",
    "ignore": [
      "firebase.json",
      "**/.*",
      "**/node_modules/**"
    ],
    "rewrites": [
      {
        "source": "/admin-api/**",
        "destination": "https://supremeai-backend-secondary.onrender.com/admin-api/**"
      },
      {
        "source": "**",
        "destination": "/index.html"
      }
    ],
    "headers": [
      {
        "source": "**/*.@(js|css)",
        "headers": [
          {
            "key": "Cache-Control",
            "value": "public, max-age=31536000, immutable"
          }
        ]
      },
      {
        "source": "**/*.@(html|json)",
        "headers": [
          {
            "key": "Cache-Control",
            "value": "public, max-age=0, must-revalidate"
          }
        ]
      }
    ]
  }
}
```

### Deployment Process

**Automated Deployment**:
1. Push to `main` branch
2. GitHub Actions builds frontend
3. Firebase CLI deploys
4. CDN cache invalidated
5. Deployment verified

**Manual Deployment**:
```bash
# Install Firebase CLI
npm i -g firebase-tools

# Login
firebase login

# Deploy
firebase deploy --only hosting
```

---

## 🌤️ Cloudflare Worker

### Purpose
Edge layer for load balancing, health monitoring, and keep-alive pings.

**Location**: `cloudflare-worker/`

### Configuration

**File**: `cloudflare-worker/src/index.ts`

```typescript
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    
    // Health check
    if (url.pathname === '/health') {
      return new Response('OK', { status: 200 });
    }
    
    // Load balancing
    const userService = 'https://supremeai-backend-08zd.onrender.com';
    const adminService = 'https://supremeai-backend-secondary.onrender.com';
    
    // Route to appropriate service
    if (url.pathname.startsWith('/admin-api')) {
      return await proxy(adminService + url.pathname.replace('/admin-api', ''), request);
    } else {
      return await proxy(userService + url.pathname, request);
    }
  }
};

async function proxy(targetUrl: string, request: Request): Promise<Response> {
  try {
    const response = await fetch(targetUrl, {
      method: request.method,
      headers: request.headers,
      body: request.body
    });
    
    return response;
  } catch (error) {
    // Fallback to secondary service
    const fallbackUrl = targetUrl.replace('supremeai-backend', 'supremeai-backend-secondary');
    return fetch(fallbackUrl, {
      method: request.method,
      headers: request.headers,
      body: request.body
    });
  }
}
```

### Keep-Alive Pings

**Purpose**: Prevent Render free tier sleep

**Configuration**:
```typescript
// Ping every 10 minutes
export async function scheduled(event: ScheduledEvent, env: Env): Promise<void> {
  const services = [
    'https://supremeai-backend-08zd.onrender.com/health',
    'https://supremeai-backend-secondary.onrender.com/health'
  ];
  
  for (const service of services) {
    try {
      await fetch(service);
      console.log(`Pinged ${service}`);
    } catch (error) {
      console.error(`Failed to ping ${service}:`, error);
    }
  }
}
```

**Schedule**: `cron: "*/10 * * * *"` (every 10 minutes)

---

## 🔄 CI/CD Pipeline

### GitHub Actions Workflows

#### 1. Backend Tests

**File**: `.github/workflows/backend-tests.yml`

```yaml
name: Backend Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install Poetry
        run: pip install poetry
      
      - name: Install dependencies
        run: |
          cd backend
          poetry install --no-interaction
      
      - name: Run tests
        run: |
          cd backend
          pytest tests/ -v --cov=core --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./backend/coverage.xml
```

#### 2. Build and Push Docker

**File**: `.github/workflows/build-docker.yml`

```yaml
name: Build and Push Docker

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2
      
      - name: Login to GHCR
        uses: docker/login-action@v2
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Build and push
        uses: docker/build-push-action@v4
        with:
          context: .
          file: ./backend/Dockerfile
          push: true
          tags: |
            ghcr.io/${{ github.repository }}/backend:latest
            ghcr.io/${{ github.repository }}/backend:${{ github.sha }}
          cache-from: type=registry,ref=ghcr.io/${{ github.repository }}/backend:buildcache
          cache-to: type=registry,ref=ghcr.io/${{ github.repository }}/backend:buildcache,mode=max
```

#### 3. Deploy to Render

**File**: `.github/workflows/deploy-render.yml`

```yaml
name: Deploy to Render

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Trigger Render Deploy
        run: |
          curl -X POST https://api.render.com/deploy/srv-d9d3n58js32c738n79k0 \
            -H "Authorization: Bearer ${{ secrets.RENDER_API_KEY }}" \
            -H "Content-Type: application/json" \
            -d '{"clearCache": "clear"}'
```

#### 4. Deploy Frontend

**File**: `.github/workflows/deploy-frontend.yml`

```yaml
name: Deploy Frontend

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  deploy-vercel:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '20'
      
      - name: Install pnpm
        run: npm install -g pnpm
      
      - name: Install dependencies
        run: pnpm install
      
      - name: Build
        run: pnpm --filter supremeai-studio-client build
      
      - name: Deploy to Vercel
        uses: amondnet/vercel-action@v20
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          working-directory: apps/studio-client

  deploy-firebase:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '20'
      
      - name: Install Firebase CLI
        run: npm install -g firebase-tools
      
      - name: Build admin
        run: |
          pnpm install
          pnpm --filter supremeai-studio-client build
      
      - name: Deploy to Firebase
        run: firebase deploy --only hosting --token ${{ secrets.FIREBASE_TOKEN }}
        env:
          FIREBASE_TOKEN: ${{ secrets.FIREBASE_TOKEN }}
```

---

## 🏥 Health Checks

### Health Check Endpoint

**URL**: `/health`

**Response**:
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "timestamp": "2025-01-04T00:00:00Z",
  "checks": {
    "database": "healthy",
    "redis": "healthy",
    "llm_gateway": "healthy"
  }
}
```

### Detailed Health Check

**URL**: `/api/v1/health/detailed`

**Response**:
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "timestamp": "2025-01-04T00:00:00Z",
  "checks": {
    "database": {
      "status": "healthy",
      "response_time_ms": 5
    },
    "redis": {
      "status": "healthy",
      "response_time_ms": 2
    },
    "llm_gateway": {
      "status": "healthy",
      "providers": {
        "openai": "healthy",
        "anthropic": "healthy"
      }
    }
  }
}
```

### Health Check Implementation

```python
@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/health/detailed")
async def detailed_health_check():
    checks = {}
    
    # Check database
    try:
        start = time.time()
        await database.execute("SELECT 1")
        checks["database"] = {
            "status": "healthy",
            "response_time_ms": int((time.time() - start) * 1000)
        }
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}
    
    # Check Redis
    try:
        start = time.time()
        await redis_client.ping()
        checks["redis"] = {
            "status": "healthy",
            "response_time_ms": int((time.time() - start) * 1000)
        }
    except Exception as e:
        checks["redis"] = {"status": "unhealthy", "error": str(e)}
    
    # Check LLM Gateway
    checks["llm_gateway"] = await llm_gateway.health_check()
    
    overall_status = "healthy" if all(
        c.get("status") == "healthy" for c in checks.values()
    ) else "unhealthy"
    
    return {
        "status": overall_status,
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "checks": checks
    }
```

---

## 📊 Monitoring

### Application Monitoring

**Tools**:
- **Sentry**: Error tracking
- **PostHog**: Product analytics
- **UptimeRobot**: Uptime monitoring

### Metrics to Monitor

**Application Metrics**:
- Request rate
- Response time (p50, p95, p99)
- Error rate
- CPU usage
- Memory usage

**Business Metrics**:
- Active users
- Agent executions
- LLM API calls
- Token usage
- Cost per day

**Infrastructure Metrics**:
- Database connections
- Redis memory usage
- Queue length
- Disk usage

### Alerts

**Critical Alerts** (immediate action):
- Service down
- Error rate >5%
- Response time p95 >5s
- Database connection pool exhausted

**Warning Alerts** (investigate soon):
- Error rate >1%
- Response time p95 >2s
- Memory usage >80%
- Disk usage >80%

---

## 🔄 Zero-Downtime Deployment

### Strategy

**Blue-Green Deployment**:
1. Deploy new version (green)
2. Run health checks
3. Switch traffic (blue → green)
4. Keep old version (blue) for rollback
5. Monitor for issues
6. Decommission old version

### Implementation

**Render**:
- Render handles blue-green automatically
- New version deployed alongside old
- Traffic switched after health check
- Old version retained for rollback

**Vercel**:
- Vercel uses instant rollback
- Previous deployments retained
- Rollback with one click

**Firebase**:
- Firebase uses atomic deploys
- Old version available immediately
- Rollback with one command

---

## 🚨 Rollback Procedures

### Automatic Rollback

**Triggers**:
- Health check failure
- Error rate >10%
- Response time p95 >10s

**Process**:
1. Detect failure
2. Automatically rollback to previous version
3. Notify team
4. Investigate issue

### Manual Rollback

**Render**:
```bash
# Via API
curl -X POST https://api.render.com/v1/services/srv-d9d3n58js32c738n79k0/deploys/{deploy_id}/rollback \
  -H "Authorization: Bearer $RENDER_API_KEY"

# Via Dashboard
# 1. Go to Render Dashboard
# 2. Select service
# 3. Click "Rollback" button
```

**Vercel**:
```bash
# Via CLI
vercel rollback

# Via Dashboard
# 1. Go to Vercel Dashboard
# 2. Select project
# 3. Click "Rollback" button
```

**Firebase**```bash
# Via CLI
firebase hosting:rollback

# Via Dashboard
# 1. Go to Firebase Console
# 2. Select project
# 3. Click "Rollback" button
```

---

## 📋 Deployment Checklist

### Pre-Deployment

- [ ] All tests pass
- [ ] Code review approved
- [ ] Environment variables updated
- [ ] Database migrations ready
- [ ] Documentation updated
- [ ] Changelog updated

### During Deployment

- [ ] Build succeeds
- [ ] Tests pass in CI
- [ ] Docker image built
- [ ] Image pushed to registry
- [ ] Deployment triggered
- [ ] Health check passes
- [ ] Smoke tests pass

### Post-Deployment

- [ ] Monitor error rates
- [ ] Monitor response times
- [ ] Check logs for errors
- [ ] Verify metrics
- [ ] Update status page
- [ ] Notify team

---

## 🔗 Related Documents

- [03-ARCHITECTURE.md](03-ARCHITECTURE.md) - System architecture
- [08-CONFIGURATION_DOCUMENTATION.md](08-CONFIGURATION_DOCUMENTATION.md) - Configuration
- [09-ENVIRONMENT_DOCUMENTATION.md](09-ENVIRONMENT_DOCUMENTATION.md) - Environment variables
- [22-INFRASTRUCTURE_DOCUMENTATION.md](22-INFRASTRUCTURE_DOCUMENTATION.md) - Infrastructure
- [26-MONITORING_DOCUMENTATION.md](26-MONITORING_DOCUMENTATION.md) - Monitoring

---

## ✅ Deployment Verification

**How to verify deployment**:

1. **Check Health**:
   ```bash
   curl https://supremeai-backend-08zd.onrender.com/health
   curl https://supremeai-backend-secondary.onrender.com/health
   ```

2. **Check Frontend**:
   ```bash
   curl https://tiny-stroopwafel-2d981c.netlify.app
   curl https://supremeai-admin.web.app
   ```

3. **Check API**:
   ```bash
   curl https://supremeai-backend-08zd.onrender.com/openapi.json
   ```

4. **Check Logs**:
   ```bash
   # Render logs
   render logs -s supremeai-backend
   
   # Vercel logs
   vercel logs
   ```

---

**Document Status**: ✅ Complete and Verified  
**Next Review**: 2025-02-04  
**Owner**: DevOps Team