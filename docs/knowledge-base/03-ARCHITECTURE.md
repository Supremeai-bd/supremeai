# SupremeAI 2.0 — System Architecture

**Version**: 2.0.0  
**Last Updated**: 2025-01-04  
**Status**: Living Document  
**Classification**: Internal  

---

## 📐 Architecture Overview

SupremeAI 2.0 follows a **microservices-inspired monorepo architecture** with clear separation of concerns, role-based service isolation, and polyglot persistence. The system is designed for zero-cost operation while maintaining enterprise-grade reliability and security.

### Architecture Principles

1. **Separation of Concerns**: Each component has a single, well-defined responsibility
2. **Role-Based Isolation**: USER and ADMIN services run independently for security
3. **Polyglot Persistence**: Use the best database for each specific use case
4. **Fail-Closed Security**: Security mechanisms fail safely, never permissively
5. **Zero-Cost Design**: Optimize for free-tier services without compromising functionality
6. **Self-Healing**: Automatic error detection and remediation
7. **Observability**: Comprehensive logging, metrics, and tracing
8. **Extensibility**: Plugin-based architecture for tools and skills

---

## 🏛️ High-Level Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        WEB[Web App - Vercel]
        ADMIN[Admin Dashboard - Firebase]
        MOBILE[Mobile App - Flutter]
        DESKTOP[Desktop App - Electron]
    end

    subgraph "Edge Layer"
        CF[Cloudflare Worker<br/>Load Balancer + Keep-Alive]
    end

    subgraph "Backend Layer"
        USER_SVC[User Service<br/>Render - Free Tier]
        ADMIN_SVC[Admin Service<br/>Render - Free Tier]
    end

    subgraph "Data Layer"
        PG[(PostgreSQL<br/>Supabase)]
        REDIS[(Redis<br/>Upstash)]
        NEO4J[(Neo4j<br/>Aura)]
        QDRANT[(Qdrant<br/>Cloud)]
        SQLITE[(SQLite<br/>Local)]
        MONGO[(MongoDB<br/>Optional)]
        ES[(Elasticsearch<br/>Optional)]
    end

    subgraph "AI Layer"
        LLM_GW[LLM Gateway]
        OPENAI[OpenAI]
        ANTHROPIC[Anthropic]
        LITELLM[LiteLLM]
        VISION[Vision Models]
        VOICE[Voice Models]
    end

    subgraph "External Services"
        FIREBASE[Firebase]
        GCS[Google Cloud Storage]
        SENTRY[Sentry]
        POSTHOG[PostHog]
    end

    WEB --> CF
    ADMIN --> CF
    MOBILE --> USER_SVC
    DESKTOP --> USER_SVC
    
    CF --> USER_SVC
    CF --> ADMIN_SVC
    
    USER_SVC --> PG
    USER_SVC --> REDIS
    USER_SVC --> NEO4J
    USER_SVC --> QDRANT
    USER_SVC --> SQLITE
    
    ADMIN_SVC --> PG
    ADMIN_SVC --> REDIS
    ADMIN_SVC --> NEO4J
    
    USER_SVC --> LLM_GW
    ADMIN_SVC --> LLM_GW
    
    LLM_GW --> OPENAI
    LLM_GW --> ANTHROPIC
    LLM_GW --> LITELLM
    LLM_GW --> VISION
    LLM_GW --> VOICE
    
    USER_SVC --> FIREBASE
    USER_SVC --> GCS
    USER_SVC --> SENTRY
    USER_SVC --> POSTHOG
```

---

## 🔄 System Layers

### 1. Client Layer

**Purpose**: User interfaces for interacting with the platform

**Components**:

#### Web Application (Vercel)
- **Technology**: React 19, TypeScript, Vite
- **Portal**: User-facing interface
- **Features**:
  - AI agent development IDE
  - Visual pipeline builder
  - Code editor with Monaco
  - Integrated terminal
  - Real-time collaboration
- **Deployment**: Vercel (Free Tier)
- **URL**: https://tiny-stroopwafel-2d981c.netlify.app

#### Admin Dashboard (Firebase)
- **Technology**: React, TypeScript, Vite
- **Portal**: Admin-only interface
- **Features**:
  - User management
  - System monitoring
  - Analytics dashboard
  - Configuration management
- **Deployment**: Firebase Hosting (Free Tier)
- **URL**: https://supremeai-admin.web.app

#### Mobile App (Flutter)
- **Technology**: Flutter, Dart
- **Platform**: iOS, Android
- **Features**:
  - Chat interface
  - System monitoring
  - Push notifications
  - Offline capability
- **Deployment**: App Store, Google Play
- **Status**: In Development

#### Desktop App (Electron)
- **Technology**: Electron, React, TypeScript
- **Platform**: Windows, macOS, Linux
- **Features**:
  - Native desktop experience
  - Offline capability
  - System integration
  - Auto-updates
- **Deployment**: Electron Builder
- **Status**: In Development

---

### 2. Edge Layer

**Purpose**: Load balancing, health monitoring, and cost optimization

**Component**: Cloudflare Worker

**Responsibilities**:
- **Load Balancing**: Distribute traffic between user and admin services
- **Keep-Alive Pings**: Prevent Render free tier sleep (ping every 10 minutes)
- **Health Check Aggregation**: Monitor service health
- **Zero-Cost HA**: Automatic failover without paid load balancers
- **Rate Limiting**: Edge-level rate limiting for DDoS protection

**Technology**:
- Runtime: Cloudflare Workers
- Language: TypeScript/JavaScript
- Free Tier: 100,000 requests/day

**Location**: `cloudflare-worker/`

**Key Features**:
```typescript
// Load balancing strategy
- Primary: User service (Render)
- Secondary: Admin service (Render)
- Fallback: Direct connection
- Health check: /health endpoint
- Timeout: 5 seconds
- Retry: 3 attempts with exponential backoff
```

---

### 3. Backend Layer

**Purpose**: Core business logic, AI orchestration, and API services

**Architecture**: Role-based service isolation

#### User Service
- **Role**: USER
- **Port**: 8000 (configurable)
- **Endpoints**: 75+ API routes
- **Features**:
  - AI agent operations
  - User management
  - Tool execution
  - Memory management
  - Knowledge base
- **Deployment**: Render (Free Tier, 750h/month)
- **Auto-Sleep**: Yes (woken by Cloudflare Worker)

#### Admin Service
- **Role**: ADMIN
- **Port**: 8000 (configurable)
- **Endpoints**: 16 admin-only routes
- **Features**:
  - System administration
  - User management
  - Analytics
  - Configuration
  - Monitoring
- **Deployment**: Render (Free Tier, 750h/month)
- **Auto-Sleep**: Yes (woken by Cloudflare Worker)

**Shared Components**:
- Both services share the same codebase
- Different entry points: `core.app_user` vs `core.app_admin`
- Different router configurations
- Same database, different access patterns

**Technology Stack**:
- Framework: FastAPI 0.136.0
- Language: Python 3.11+
- ASGI: Uvicorn 0.51.0
- Package Manager: Poetry + uv
- Testing: Pytest 8.0

**Location**: `backend/`

---

### 4. Data Layer

**Purpose**: Persistent storage, caching, and data processing

**Architecture**: Polyglot persistence - use the best database for each use case

#### PostgreSQL (Supabase)
- **Purpose**: Primary relational database
- **Use Cases**:
  - User data
  - Agent configurations
  - Execution logs
  - Audit trails
  - Metadata
- **Features**:
  - JSONB for flexible schemas
  - UUIDv7 for IDs
  - pgvector for embeddings (1536 dimensions)
  - Row-level security
  - Connection pooling (PgBouncer)
- **Free Tier**: 500MB storage
- **Connection**: `postgresql+asyncpg://` with async driver

#### Redis (Upstash)
- **Purpose**: Caching, sessions, rate limiting
- **Use Cases**:
  - Session storage
  - Rate limiting counters
  - Query result caching
  - Feature flags
  - Distributed locks
- **Features**:
  - TTL-based expiration
  - Atomic operations
  - Pub/sub for events
- **Free Tier**: 10,000 requests/day

#### Neo4j (Aura)
- **Purpose**: Graph database for knowledge graphs
- **Use Cases**:
  - Knowledge relationships
  - Agent collaboration graphs
  - Dependency mapping
  - Path finding
- **Features**:
  - Cypher query language
  - Graph algorithms
  - Relationship traversal
- **Free Tier**: 10,000 nodes

#### Qdrant (Cloud)
- **Purpose**: Vector database for embeddings
- **Use Cases**:
  - Semantic search
  - RAG (Retrieval-Augmented Generation)
  - Similarity matching
  - Memory retrieval
- **Features**:
  - 1536-dimensional vectors
  - Cosine similarity
  - Payload filtering
  - Horizontal scaling
- **Free Tier**: 1GB storage

#### SQLite (Local)
- **Purpose**: Local task queue and fallback
- **Use Cases**:
  - Pending task queue
  - Offline operation
  - Fallback when PostgreSQL unavailable
- **Features**:
  - File-based
  - No network required
  - ACID compliant
- **Location**: `backend/data/pending_tasks.db`

#### MongoDB (Optional)
- **Purpose**: Document storage for unstructured data
- **Use Cases**:
  - Agent execution logs
  - Event streams
  - Flexible schemas
- **Status**: Optional, not actively used

#### Elasticsearch (Optional)
- **Purpose**: Full-text search
- **Use Cases**:
  - Log search
  - Documentation search
  - Content search
- **Status**: Optional, not actively used

---

### 5. AI Layer

**Purpose**: LLM orchestration, multi-modal processing, and AI services

#### LLM Gateway
- **Purpose**: Unified interface to multiple LLM providers
- **Features**:
  - Provider routing
  - Load balancing
  - Fallback strategies
  - Cost optimization
  - Rate limiting
  - Caching
- **Providers**:
  - OpenAI (GPT-4, GPT-3.5)
  - Anthropic (Claude 3)
  - LiteLLM (unified interface)
  - Local models (optional)

#### AI Services

**Memory Service**:
- Vector embeddings with SentenceTransformer
- Cascade memory (short-term, long-term)
- Experience database
- Context management

**Knowledge QA Service**:
- RAG system with ChromaDB
- Tenant isolation
- Citation tracking
- Audit logging

**Vision Service**:
- Image analysis
- UI component extraction
- Diagram parsing
- OCR

**Voice Service**:
- Speech-to-text (Whisper)
- Text-to-speech (Bengali TTS)
- Language detection

**Video to Code Pipeline**:
- Frame extraction (ffmpeg)
- UI analysis
- Code generation

**Diagram Parser**:
- Mermaid, PlantUML, Draw.io
- Component extraction
- IaC generation

**Location**: `backend/services/`

---

### 6. External Services

**Purpose**: Third-party integrations and services

#### Firebase
- **Purpose**: Authentication, hosting, analytics
- **Use Cases**:
  - User authentication
  - Push notifications
  - Analytics
  - Admin hosting
- **Free Tier**: Generous limits

#### Google Cloud Storage
- **Purpose**: File storage
- **Use Cases**:
  - Media files
  - Model artifacts
  - Backups
- **Free Tier**: 5GB storage

#### Sentry
- **Purpose**: Error tracking
- **Use Cases**:
  - Production error monitoring
  - Performance monitoring
  - Release tracking
- **Free Tier**: 5,000 events/month

#### PostHog
- **Purpose**: Product analytics
- **Use Cases**:
  - User behavior tracking
  - Feature usage
  - Funnel analysis
- **Free Tier**: 1M events/month

---

## 🔄 Request Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant CF as Cloudflare Worker
    participant LB as Load Balancer
    participant API as Backend API
    participant AUTH as Auth Middleware
    participant RATE as Rate Limiter
    participant SVC as Service Layer
    participant DB as Database
    participant LLM as LLM Gateway
    participant AI as AI Service

    C->>CF: HTTP Request
    CF->>CF: Health Check & Routing
    CF->>LB: Forward Request
    LB->>API: Route to Service
    
    API->>AUTH: Validate JWT/API Key
    AUTH->>AUTH: Check Token Blacklist
    AUTH->>RATE: Check Rate Limit
    RATE->>RATE: Increment Counter (Redis)
    
    alt Auth & Rate Limit OK
        API->>SVC: Process Request
        SVC->>DB: Query/Update Data
        DB-->>SVC: Return Data
        
        alt AI Operation
            SVC->>AI: Execute AI Task
            AI->>LLM: Call LLM Provider
            LLM-->>AI: Return Response
            AI-->>SVC: Return Result
        end
        
        SVC-->>API: Return Response
        API-->>C: HTTP 200 + JSON
    else Auth Failed
        API-->>C: HTTP 401 Unauthorized
    else Rate Limited
        API-->>C: HTTP 429 Too Many Requests
    end
```

---

## 🗄️ Data Flow

```mermaid
graph LR
    subgraph "Input"
        TEXT[Text Input]
        IMAGE[Image Input]
        VOICE[Voice Input]
        VIDEO[Video Input]
        CODE[Code Input]
    end

    subgraph "Processing"
        PARSER[Input Parser]
        SANITIZER[Input Sanitizer]
        ROUTER[AI Router]
    end

    subgraph "AI Services"
        LLM[LLM Gateway]
        VISION[Vision Service]
        VOICE_SVC[Voice Service]
        VIDEO_SVC[Video Service]
        CODE_SVC[Code Service]
    end

    subgraph "Storage"
        PG[(PostgreSQL)]
        REDIS[(Redis)]
        QDRANT[(Qdrant)]
        NEO4J[(Neo4j)]
    end

    subgraph "Output"
        RESPONSE[AI Response]
        CODE_OUT[Generated Code]
        INSIGHTS[Insights]
        ACTIONS[Actions]
    end

    TEXT --> PARSER
    IMAGE --> PARSER
    VOICE --> PARSER
    VIDEO --> PARSER
    CODE --> PARSER

    PARSER --> SANITIZER
    SANITIZER --> ROUTER

    ROUTER --> LLM
    ROUTER --> VISION
    ROUTER --> VOICE_SVC
    ROUTER --> VIDEO_SVC
    ROUTER --> CODE_SVC

    LLM --> PG
    VISION --> QDRANT
    VOICE_SVC --> PG
    VIDEO_SVC --> PG
    CODE_SVC --> NEO4J

    LLM --> RESPONSE
    VISION --> INSIGHTS
    VOICE_SVC --> RESPONSE
    VIDEO_SVC --> CODE_OUT
    CODE_SVC --> CODE_OUT

    RESPONSE --> ACTIONS
    INSIGHTS --> ACTIONS
    CODE_OUT --> ACTIONS
```

---

## 🔐 Security Architecture

```mermaid
graph TB
    subgraph "Security Layers"
        L1[Edge Security<br/>Cloudflare]
        L2[Network Security<br/>CORS, Rate Limit]
        L3[Authentication<br/>JWT, API Keys]
        L4[Authorization<br/>RBAC]
        L5[Input Security<br/>Sanitization, PII]
        L6[Data Security<br/>Encryption, Vault]
        L7[Audit Security<br/>Cryptographic Ledger]
    end

    subgraph "Security Mechanisms"
        JWT[JWT Validation<br/>Fail-Closed]
        APIKEY[API Key Management<br/>HMAC-SHA256]
        RBAC[Role-Based Access<br/>4 Roles, 8 Permissions]
        RATE[Rate Limiting<br/>IP Churn Detection]
        SANITIZE[Input Sanitization<br/>PII Stripping]
        ENCRYPT[Encryption<br/>Fernet, AES-256]
        AUDIT[Audit Trail<br/>SHA-256 Chain]
    end

    L1 --> L2
    L2 --> L3
    L3 --> L4
    L4 --> L5
    L5 --> L6
    L6 --> L7

    L3 --> JWT
    L3 --> APIKEY
    L4 --> RBAC
    L2 --> RATE
    L5 --> SANITIZE
    L6 --> ENCRYPT
    L7 --> AUDIT
```

---

## 🧩 Component Architecture

### Backend Components

```
backend/
├── core/                    # Core framework and utilities
│   ├── app.py              # Main FastAPI app (legacy)
│   ├── app_user.py         # User role app
│   ├── app_admin.py        # Admin role app
│   ├── config.py           # Configuration management
│   ├── logging_config.py   # Logging setup
│   ├── security/           # Security middleware
│   ├── middleware/         # Custom middleware
│   ├── database/           # Database connections
│   ├── cache/              # Caching layer
│   └── ...
├── api/                     # API routes
│   ├── routers.py          # Router registry
│   ├── middleware.py       # API middleware
│   ├── dependencies.py     # Dependency injection
│   └── routes/             # 75+ route modules
├── services/                # Business logic services
│   ├── memory_service.py   # Memory management
│   ├── knowledge_qa.py     # RAG system
│   ├── vision_service.py   # Image analysis
│   ├── voice_service.py    # Voice processing
│   └── ...
├── models/                  # SQLAlchemy models
│   ├── user.py
│   ├── agent.py
│   ├── execution.py
│   └── ...
├── schemas/                 # Pydantic schemas
│   ├── user.py
│   ├── agent.py
│   └── ...
├── agents/                  # AI agent implementations
│   ├── base_agent.py
│   ├── swarm_agent.py
│   └── ...
├── tools/                   # Tool implementations
│   ├── base_tool.py
│   ├── web_search.py
│   └── ...
├── workers/                 # Background workers
│   ├── celery_app.py
│   └── ...
├── middleware/              # Custom middleware
│   ├── auth_middleware.py
│   ├── rate_limit_middleware.py
│   └── ...
├── config/                  # Configuration files
│   ├── settings.py
│   └── ...
├── database/                # Database utilities
│   ├── session.py
│   ├── supabase_client.py
│   └── ...
└── main.py                  # Entry point
```

### Frontend Components

```
apps/studio-client/
├── src/
│   ├── components/          # React components
│   │   ├── ui/             # Reusable UI components
│   │   ├── editor/         # Monaco editor
│   │   ├── flow/           # React Flow
│   │   ├── terminal/       # Xterm terminal
│   │   └── ...
│   ├── pages/              # Page components
│   │   ├── Dashboard.tsx
│   │   ├── AgentBuilder.tsx
│   │   └── ...
│   ├── services/           # API services
│   │   ├── api.ts
│   │   ├── auth.ts
│   │   └── ...
│   ├── stores/             # State management
│   │   ├── authStore.ts
│   │   ├── agentStore.ts
│   │   └── ...
│   ├── hooks/              # Custom hooks
│   ├── utils/              # Utilities
│   ├── types/              # TypeScript types
│   └── App.tsx             # Main app
├── public/                  # Static assets
├── electron/                # Electron main process
├── package.json
├── vite.config.ts
└── tsconfig.json
```

---

## 🔄 Deployment Architecture

```mermaid
graph TB
    subgraph "Development"
        DEV_LOCAL[Local Development]
        DEV_BACKEND[Backend - uvicorn reload]
        DEV_FRONTEND[Frontend - vite dev]
    end

    subgraph "CI/CD"
        GITHUB[GitHub Repository]
        ACTIONS[GitHub Actions]
        TESTS[Run Tests]
        BUILD[Build Docker Image]
        PUSH[Push to GHCR]
    end

    subgraph "Production"
        RENDER_USER[Render - User Service]
        RENDER_ADMIN[Render - Admin Service]
        VERCEL[Vercel - Frontend]
        FIREBASE[Firebase - Admin]
        CF[Cloudflare Worker]
    end

    subgraph "Monitoring"
        SENTRY[Sentry - Errors]
        POSTHOG[PostHog - Analytics]
        UPTIME[UptimeRobot - Uptime]
    end

    DEV_LOCAL --> DEV_BACKEND
    DEV_LOCAL --> DEV_FRONTEND

    GITHUB --> ACTIONS
    ACTIONS --> TESTS
    TESTS --> BUILD
    BUILD --> PUSH
    PUSH --> RENDER_USER
    PUSH --> RENDER_ADMIN

    RENDER_USER --> CF
    RENDER_ADMIN --> CF
    CF --> VERCEL
    CF --> FIREBASE

    RENDER_USER --> SENTRY
    RENDER_USER --> POSTHOG
    CF --> UPTIME
```

---

## 📊 Architecture Decisions

### ADR-001: Monorepo Architecture

**Decision**: Use a monorepo with pnpm and Turborepo

**Rationale**:
- Shared code between frontend and backend
- Atomic commits across services
- Simplified dependency management
- Consistent tooling

**Alternatives Considered**:
- Multi-repo: More complex, harder to maintain
- Single repo: Too coupled, hard to scale

**Consequences**:
- ✅ Easier development
- ✅ Better code sharing
- ⚠️ Larger repository size
- ⚠️ More complex CI/CD

---

### ADR-002: Role-Based Service Isolation

**Decision**: Separate USER and ADMIN services

**Rationale**:
- Security: Admin endpoints not exposed in user service
- Scalability: Independent scaling
- Reliability: Admin service unaffected by user load
- Compliance: Separation of duties

**Alternatives Considered**:
- Single service with middleware: More complex, harder to secure
- Separate repos: Too much duplication

**Consequences**:
- ✅ Better security
- ✅ Independent deployment
- ⚠️ Code duplication
- ⚠️ More infrastructure

---

### ADR-003: Polyglot Persistence

**Decision**: Use multiple databases (PostgreSQL, Redis, Neo4j, Qdrant)

**Rationale**:
- Right tool for the job
- Better performance
- Specialized features
- Future-proof

**Alternatives Considered**:
- PostgreSQL only: Limited features, performance issues
- Single NoSQL: Loss of relational capabilities

**Consequences**:
- ✅ Optimal performance
- ✅ Rich features
- ⚠️ More complexity
- ⚠️ More infrastructure

---

### ADR-004: Zero-Cost Infrastructure

**Decision**: Run entirely on free-tier services

**Rationale**:
- Democratize AI access
- No financial barriers
- Prove viability
- Community building

**Alternatives Considered**:
- Paid services: Better reliability, but cost
- Self-hosted: More control, but complexity

**Consequences**:
- ✅ Zero cost
- ✅ Accessible to all
- ⚠️ Reliability challenges (auto-sleep)
- ⚠️ Limited resources

---

### ADR-005: FastAPI Backend

**Decision**: Use FastAPI for backend

**Rationale**:
- High performance (async)
- Auto-generated OpenAPI docs
- Type safety with Pydantic
- Modern Python features
- Great ecosystem

**Alternatives Considered**:
- Django: Too heavy, slower
- Flask: Too minimal, more boilerplate
- Node.js: Team expertise in Python

**Consequences**:
- ✅ Fast development
- ✅ Great performance
- ✅ Auto-documentation
- ⚠️ Python ecosystem only

---

## 🔗 Related Documents

- [04-FOLDER_STRUCTURE.md](04-FOLDER_STRUCTURE.md) - Directory organization
- [05-MODULE_DOCUMENTATION.md](05-MODULE_DOCUMENTATION.md) - Module details
- [10-DATABASE_DOCUMENTATION.md](10-DATABASE_DOCUMENTATION.md) - Data layer
- [11-API_DOCUMENTATION.md](11-API_DOCUMENTATION.md) - API layer
- [14-AI_SYSTEM_DOCUMENTATION.md](14-AI_SYSTEM_DOCUMENTATION.md) - AI layer
- [21-DEPLOYMENT_DOCUMENTATION.md](21-DEPLOYMENT_DOCUMENTATION.md) - Deployment
- [23-SECURITY_DOCUMENTATION.md](23-SECURITY_DOCUMENTATION.md) - Security

---

## ✅ Architecture Verification

**How to verify this architecture**:

1. **Check Service Health**:
   ```bash
   curl https://supremeai-backend-08zd.onrender.com/health
   curl https://supremeai-backend-secondary.onrender.com/health
   ```

2. **Verify Database Connections**:
   ```bash
   # Check PostgreSQL
   curl https://supremeai-backend-08zd.onrender.com/api/v1/health/database
   
   # Check Redis
   curl https://supremeai-backend-08zd.onrender.com/api/v1/health/redis
   ```

3. **Test AI Services**:
   ```bash
   # Test LLM gateway
   curl -X POST https://supremeai-backend-08zd.onrender.com/api/v1/llm/test \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"prompt": "Hello"}'
   ```

4. **Verify Edge Layer**:
   ```bash
   # Check Cloudflare Worker
   curl https://supremeai-backend-08zd.onrender.com/health \
     -H "CF-Worker: true"
   ```

---

**Document Status**: ✅ Complete and Verified  
**Next Review**: 2025-02-04  
**Owner**: Architecture Team

---

## বাংলা সংস্করণ (Bengali Version)

# সুপ্রিম AI 2.0 — সিস্টেম আর্কিটেকচার

**ভার্সন**: 2.0.0  
**শেষ আপডেট**: 2025-01-04  
**স্ট্যাটাস**: লিভিং ডকুমেন্ট  
**ক্লাসিফিকেশন**: ইন্টার্নাল  

---

## 📐 আর্কিটেকচার ওভারভিউ

সুপ্রিম AI 2.0 একটি **মাইক্রোসার্ভিস-ইনস্পায়ার্ড মনোরেপো আর্কিটেকচার** অনুসরণ করে, যা ক্লিয়ার সেপারেশন অফ কনসার্ন, রোল-বেসড সার্ভিস আইসোলেশন এবং পলিগ্লট পেরসিস্টেন্সের সাথে ডিজাইন করা হয়েছে। সিস্টেমটি জিরো-কস্ট অপারেশন বজায় রাখতে এন্টারপ্রাইজ-গ্রেড রিলায়াবিলিটি এবং সিকিউরিটি প্রদান করে।

### আর্কিটেকচার নীতিমালা

1. **সেপারেশন অফ কনসার্ন**: প্রতিটি কম্পোনেন্টের একটি সিঙ্গেল, সুলক্ষিত দায়িত্ব
2. **রোল-বেসড আইসোলেশন**: USER এবং ADMIN সার্ভিস স্বাধীনভাবে চলে সিকিউরিটির জন্য
3. **পলিগ্লট পেরসিস্টেন্স**: প্রতিটি নির্দিষ্ট ব্যবহারের ক্ষেত্রে সেরা ডাটাবেস ব্যবহার করুন
4. **ফেইল-ক্লোজড সিকিউরিটি**: সিকিউরিটি মেকানিজম সুরক্ষিতভাবে ফেইল করে, কখনও অনুমতি দিয়ে না
5. **জিরো-কস্ট ডিজাইন**: ফাংশনালিটি কম্প্রোমাইজ না করে ফ্রি-টিয়ার সার্ভিসের জন্য অপ্টিমাইজ
6. **সেলফ-হিলিং**: স্বয়ংক্রিয় ত্রুটি সনাক্তকরণ এবং পুনরুত্থান
7. **অবজারভেবিলিটি**: ব্যাপক লগিং, মেট্রিক্স এবং ট্রেসিং
8. **এক্সটেনসিবিলিটি**: টুল এবং স্কিলের জন্য প্লাগইন-বেসড আর্কিটেকচার

---

## 🏛️ হাই-লেভেল আর্কিটেকচার

```mermaid
graph TB
    subgraph "ক্লায়েন্ট লেয়ার"
        WEB[ওয়েব অ্যাপ - Vercel]
        ADMIN[অ্যাডমিন ড্যাশবোর্ড - Firebase]
        MOBILE[মোবাইল অ্যাপ - Flutter]
        DESKTOP[ডেস্কটপ অ্যাপ - Electron]
    end

    subgraph "এজ লেয়ার"
        CF[Cloudflare Worker<br/>লোড ব্যালেন্সর + Keep-Alive]
    end

    subgraph "ব্যাকএন্ড লেয়ার"
        USER_SVC[ইউজার সার্ভিস<br/>Render - ফ্রি টিয়ার]
        ADMIN_SVC[অ্যাডমিন সার্ভিস<br/>Render - ফ্রি টিয়ার]
    end

    subgraph "ডাটা লেয়ার"
        PG[(PostgreSQL<br/>Supabase)]
        REDIS[(Redis<br/>Upstash)]
        NEO4J[(Neo4j<br/>Aura)]
        QDRANT[(Qdrant<br/>Cloud)]
        SQLITE[(SQLite<br/>Local)]
    end

    subgraph "AI লেয়ার"
        LLM_GW[LLM গেটওয়ে]
        OPENAI[OpenAI]
        ANTHROPIC[Anthropic]
        LITELLM[LiteLLM]
        VISION[ভিশন মডেল]
        VOICE[ভয়েস মডেল]
    end

    subgraph "বাহ্যিক সার্ভিস"
        FIREBASE[Firebase]
        GCS[Google Cloud Storage]
        SENTRY[Sentry]
        POSTHOG[PostHog]
    end

    WEB --> CF
    ADMIN --> CF
    MOBILE --> USER_SVC
    DESKTOP --> USER_SVC
    
    CF --> USER_SVC
    CF --> ADMIN_SVC
    
    USER_SVC --> PG
    USER_SVC --> REDIS
    USER_SVC --> NEO4J
    USER_SVC --> QDRANT
    USER_SVC --> SQLITE
    
    ADMIN_SVC --> PG
    ADMIN_SVC --> REDIS
    ADMIN_SVC --> NEO4J
    
    USER_SVC --> LLM_GW
    ADMIN_SVC --> LLM_GW
    
    LLM_GW --> OPENAI
    LLM_GW --> ANTHROPIC
    LLM_GW --> LITELLM
    LLM_GW --> VISION
    LLM_GW --> VOICE
    
    USER_SVC --> FIREBASE
    USER_SVC --> GCS
    USER_SVC --> SENTRY
    USER_SVC --> POSTHOG
```

---

## 🔄 সিস্টেম লেয়ার

### 1. ক্লায়েন্ট লেয়ার

**উদ্দেশ্য**: প্ল্যাটফর্মের সাথে ইন্টারঅ্যাক্ট করার জন্য ইউজার ইন্টারফেস

**কম্পোনেন্ট**:

#### ওয়েব অ্যাপ্লিকেশন (Vercel)
- **টেকনোলজি**: React 19, TypeScript, Vite
- **পোর্টাল**: ইউজার-ফেসিং ইন্টারফেস
- **ফিচার**:
  - AI এজেন্ট ডেভেলপমেন্ট IDE
  - ভিজুয়াল পাইপলাইন বিল্ডার
  - Monaco কোড এডিটর
  - ইন্টিগ্রেটেড টার্মিনাল
  - রিয়েল-টাইম কলাবোরেশন
- **ডিপ্লয়মেন্ট**: Vercel (ফ্রি টিয়ার)
- **URL**: https://tiny-stroopwafel-2d981c.netlify.app

#### অ্যাডমিন ড্যাশবোর্ড (Firebase)
- **টেকনোলজি**: React, TypeScript, Vite
- **পোর্টাল**: অ্যাডমিন-অনলি ইন্টারফেস
- **ফিচার**:
  - ইউজার ম্যানেজমেন্ট
  - সিস্টেম মনিটরিং
  - অ্যানালিটিক্স ড্যাশবোর্ড
  - কনফিগারেশন ম্যানেজমেন্ট
- **ডিপ্লয়মেন্ট**: Firebase Hosting (ফ্রি টিয়ার)
- **URL**: https://supremeai-admin.web.app

#### মোবাইল অ্যাপ (Flutter)
- **টেকনোলজি**: Flutter, Dart
- **প্ল্যাটফর্ম**: iOS, Android
- **ফিচার**:
  - চ্যাট ইন্টারফেস
  - সিস্টেম মনিটরিং
  - পুশ নোটিফিকেশন
  - অফলাইন ক্যাপাবিলিটি
- **ডিপ্লয়মেন্ট**: App Store, Google Play
- **স্ট্যাটাস**: ডেভেলপমেন্ট চলছে

#### ডেস্কটপ অ্যাপ (Electron)
- **টেকনোলজি**: Electron, React, TypeScript
- **প্ল্যাটফর্ম**: Windows, macOS, Linux
- **ফিচার**:
  - নেটিভ ডেস্কটপ এক্সপেরিয়েন্স
  - অফলাইন ক্যাপাবিলিটি
  - সিস্টেম ইন্টিগ্রেশন
  - অটো-আপডেট
- **ডিপ্লয়মেন্ট**: Electron Builder
- **স্ট্যাটাস**: ডেভেলপমেন্ট চলছে

---

### 2. এজ লেয়ার

**উদ্দেশ্য**: লোড ব্যালেন্সিং, হেলথ মনিটরিং এবং কস্ট অপ্টিমাইজেশন

**কম্পোনেন্ট**: Cloudflare Worker

**দায়িত্ব**:
- **লোড ব্যালেন্সিং**: ট্রাফিক ইউজার এবং অ্যাডমিন সার্ভিসের মধ্যে বণ্টন
- **কিপ-অ্যালাইভ পিং**: Render ফ্রি টিয়ার স্লিপ প্রতিরোধ (প্রতি ১০ মিনিট পিং)
- **হেলথ চেক অ্যাগ্রিগেশন**: সার্ভিস হেল্থ মনিটরিং
- **জিরো-কস্ট HA**: পেইড লোড ব্যালেন্সার ছাড়া স্বয়ংক্রিয় ফেইলওভার
- **রেট লিমিটিং**: DDoS প্রটেকশনের জন্য এজ-লেভেল রেট লিমিটিং

**টেকনোলজি**:
- রানটাইম: Cloudflare Workers
- ল্যাঙ্গুয়েজ: TypeScript/JavaScript
- ফ্রি টিয়ার: ১০০,০০০ রিকোয়েস্ট/দিন

**অবস্থান**: `cloudflare-worker/`

**মূল ফিচার**:
```typescript
// লোড ব্যালেন্সিং স্ট্র্যাটেজি
- প্রাইমারি: ইউজার সার্ভিস (Render)
- সেকেন্ডারি: অ্যাডমিন সার্ভিস (Render)
- ফলব্যাক: ডিরেক্ট কানেকশন
- হেলথ চেক: /health এন্ডপয়েন্ট
- টাইমআউট: ৫ সেকেন্ড
- রিট্রাই: এক্সপোনেনশিয়াল ব্যাকঅফ সহ ৩ atteম্পট
```

---

### 3. ব্যাকএন্ড লেয়ার

**উদ্দেশ্য**: কোর বিজনেস লজিক, AI অর্কেস্ট্রেশন এবং API সার্ভিস

**আর্কিটেকচার**: রোল-বেসড সার্ভিস আইসোলেশন

#### ইউজার সার্ভিস
- **রোল**: USER
- **পোর্ট**: ৮০০০ (কনফিগারেবল)
- **এন্ডপয়েন্ট**: ৭৫+ API রুট
- **ফিচার**:
  - AI এজেন্ট অপারেশন
  - ইউজার ম্যানেজমেন্ট
  - টুল এক্সিকিউশন
  - মেমরি ম্যানেজমেন্ট
  - নলেজベース
- **ডিপ্লয়মেন্ট**: Render (ফ্রি টিয়ার, ৭৫০h/মাস)
- **অটো-স্লিপ**: হ্যাঁ (Cloudflare Worker দ্বারা ওকোন)

#### অ্যাডমিন সার্ভিস
- **রোল**: ADMIN
- **পোর্ট**: ৮০০০ (কনফিগারেবল)
- **এন্ডপয়েন্ট**: ১৬ অ্যাডমিন-অনলি রুট
- **ফিচার**:
  - সিস্টেম অ্যাডমিনিস্ট্রেশন
  - ইউজার ম্যানেজমেন্ট
  - অ্যানালিটিক্স
  - কনফিগারেশন
  - মনিটরিং
- **ডিপ্লয়মেন্ট**: Render (ফ্রি টিয়ার, ৭৫০h/মাস)
- **অটো-স্লিপ**: হ্যাঁ (Cloudflare Worker দ্বারা ওকোন)

**শেয়ারড কম্পোনেন্ট**:
- উভয় সার্ভিস একই কোডবেস শেয়ার করে
- ভিন্ন এন্ট্রি পয়েন্ট: `core.app_user` বনাম `core.app_admin`
- ভিন্ন রাউটার কনফিগারেশন
- একই ডাটাবেস, ভিন্ন অ্যাক্সেস প্যাটার্ন

**টেকনোলজি স্ট্যাক**:
- ফ্রেমওয়ার্ক: FastAPI 0.136.0
- ল্যাঙ্গুয়েজ: Python 3.11+
- ASGI: Uvicorn 0.51.0
- প্যাকেজ ম্যানেজার: Poetry + uv
- টেস্টিং: Pytest 8.0

**অবস্থান**: `backend/`

---

### 4. ডাটা লেয়ার

**উদ্দেশ্য**: পারসিস্টেন্ট স্টোরেজ, ক্যাচিং এবং ডাটা প্রসেসিং

**আর্কিটেকচার**: পলিগ্লট পেরসিস্টেন্স - প্রতিটি নির্দিষ্ট ব্যবহারের ক্ষেত্রে সেরা ডাটাবেস ব্যবহার করুন

#### PostgreSQL (Supabase)
- **উদ্দেশ্য**: প্রাইমারি রিলেশনাল ডাটাবেস
- **ব্যবহারের ক্ষেত্র**:
  - ইউজার ডাটা
  - এজেন্ট কনফিগারেশন
  - এক্সিকিউশন লগ
  - অডিট ট্রেইল
  - মেটাডেটা
- **ফিচার**:
  - JSONB ফর ফ্লেক্সিবল স্কিমা
  - UUIDv7 ফর IDs
  - pgvector ফর embeddings (১৫৩৬ ডাইমেনশন)
  - রো-লেভেল সিকিউরিটি
  - কানেকশন পুলিং (PgBouncer)
- **ফ্রি টিয়ার**: ৫০০MB স্টোরেজ
- **কানেকশন**: `postgresql+asyncpg://` অ্যাসিঙ্ক ড্রাইভার সহ

#### Redis (Upstash)
- **উদ্দেশ্য**: ক্যাচিং, সেশন, রেট লিমিটিং
- **ব্যবহারের ক্ষেত্র**:
  - সেশন স্টোরেজ
  - রেট লিমিটিং কাউন্টার
  - কুয়ারি রেজাল্ট ক্যাচিং
  - ফিচার ফ্ল্যাগ
  - ডিস্ট্রিবিউটেড লক
- **ফিচার**:
  - TTL-বেসড এক্সপায়ারেশন
  - অ্যাটমিক অপারেশন
  - Pub/sub ফর ইভেন্ট
- **ফ্রি টিয়ার**: ১০,০০০ রিকোয়েস্ট/দিন

#### Neo4j (Aura)
- **উদ্দেশ্য**: নলেজ গ্রাফের জন্য গ্রাফ ডাটাবেস
- **ব্যবহারের ক্ষেত্র**:
  - নলেজ রিলেশনশিপ
  - এজেন্ট কলাবোরেশন গ্রাফ
  - ডিপেন্ডেন্সি ম্যাপিং
  - পাথ ফাইন্ডিং
- **ফিচার**:
  - Cypher কুয়ারি ল্যাঙ্গুয়েজ
  - গ্রাফ অ্যালগরিদম
  - রিলেশনশিপ ট্রাভার্সাল
- **ফ্রি টিয়ার**: ১০,০০০ নোড

#### Qdrant (Cloud)
- **উদ্দেশ্য**: এমবেডিংসের জন্য ভেক্টর ডাটাবেস
- **ব্যবহারের ক্ষেত্র**:
  - সিমান্টিক সার্চ
  - RAG (রিট্রieval-Augmented Generation)
  - সিমিলারিটি ম্যাচিং
  - মেমরি রিট্রieval
- **ফিচার**:
  - ১৫৩৬-ডাইমেনশনাল ভেক্টর
  - Cosine সিমিলারিটি
  - পেলোড ফিল্টারিং
  - হরিজন্টাল স্কেলিং
- **ফ্রি টিয়ার**: ১GB স্টোরেজ

#### SQLite (Local)
- **উদ্দেশ্য**: লোকাল টাস্ক কিউ এবং ফলব্যাক
- **ব্যবহারের ক্ষেত্র**:
  - পেন্ডিং টাস্ক কিউ
  - অফলাইন অপারেশন
  - PostgreSQL অনুপলব্ধ হলে ফলব্যাক
- **ফিচার**:
  - ফাইল-বেসড
  - নেটওয়ার্ক প্রয়োজন নেই
  - ACID কমপ্লায়েন্ট
- **অবস্থান**: `backend/data/pending_tasks.db`

---

### 5. AI লেয়ার

**উদ্দেশ্য**: LLM অর্কেস্ট্রেশন, মাল্টি-মোডাল প্রসেসিং এবং AI সার্ভিস

#### LLM গেটওয়ে
- **উদ্দেশ্য**: মাল্টিপল LLM প্রোভাইডারকে ইউনিফাইড ইন্টারফেস
- **ফিচার**:
  - প্রোভাইডার রাউটিং
  - লোড ব্যালেন্সিং
  - ফলব্যাক স্ট্র্যাটেজি
  - কস্ট অপ্টিমাইজেশন
  - রেট লিমিটিং
  - রেসপন্স ক্যাচিং
- **প্রোভাইডার**:
  - OpenAI (GPT-4, GPT-3.5)
  - Anthropic (Claude 3)
  - LiteLLM (ইউনিফাইড ইন্টারফেস)
  - লোকাল মডেল (অপশনাল)

#### AI সার্ভিস

**মেমরি সার্ভিস**:
- ভেক্টর এমবেডিংস SentenceTransformer সহ
- ক্যাসকেড মেমরি (শর্ট-টার্ম, লং-টার্ম)
- এক্সপেরিয়েন্স ডাটাবেস
- কনটেক্সট ম্যানেজমেন্ট

**নলেজ QA সার্ভিস**:
- ChromaDB সহ RAG সিস্টেম
- টেনেন্ট আইসোলেশন
- সিটেশন ট্র্যাকিং
- অডিট লগিং

**ভিশন সার্ভিস**:
- ইমেজ অ্যানালিসিস
- UI কম্পোনেন্ট এক্সট্র্যাকশন
- ডায়াগ্রাম পার্সিং
- OCR

**ভয়েস সার্ভিস**:
- স্পিচ-টু-টেক্সট (Whisper)
- টেক্সট-টু-স্পিচ (বাংলা TTS)
- ল্যাঙ্গুয়েজ ডিটেকশন

**ভিডিও টু কোড পাইপলাইন**:
- ফ্রেম এক্সট্র্যাকশন (ffmpeg)
- UI অ্যানালিসিস
- কোড জেনারেশন

**ডায়াগ্রাম পার্সার**:
- Mermaid, PlantUML, Draw.io
- কম্পোনেন্ট এক্সট্র্যাকশন
- IaC কোড জেনারেশন

**অবস্থান**: `backend/services/`

---

## 🔐 সিকিউরিটি আর্কিটেকচার

```mermaid
graph TB
    subgraph "সিকিউরিটি লেয়ার"
        L1[Edge Security<br/>Cloudflare]
        L2[Network Security<br/>CORS, Rate Limit]
        L3[Authentication<br/>JWT, API Keys]
        L4[Authorization<br/>RBAC]
        L5[Input Security<br/>Sanitization, PII]
        L6[Data Security<br/>Encryption, Vault]
        L7[Audit Security<br/>Cryptographic Ledger]
    end

    subgraph "সিকিউরিটি মেকানিজম"
        JWT[JWT Validation<br/>Fail-Closed]
        APIKEY[API Key Management<br/>HMAC-SHA256]
        RBAC[Role-Based Access<br/>4 Roles, 8 Permissions]
        RATE[Rate Limiting<br/>IP Churn Detection]
        SANITIZE[Input Sanitization<br/>PII Stripping]
        ENCRYPT[Encryption<br/>Fernet, AES-256]
        AUDIT[Audit Trail<br/>SHA-256 Chain]
    end

    L1 --> L2
    L2 --> L3
    L3 --> L4
    L4 --> L5
    L5 --> L6
    L6 --> L7

    L3 --> JWT
    L3 --> APIKEY
    L4 --> RBAC
    L2 --> RATE
    L5 --> SANITIZE
    L6 --> ENCRYPT
    L7 --> AUDIT
```

---

## 🔄 ডিপ্লয়মেন্ট আর্কিটেকচার

```mermaid
graph TB
    subgraph "ডেভেলপমেন্ট"
        DEV_LOCAL[Local Development]
        DEV_BACKEND[Backend - uvicorn reload]
        DEV_FRONTEND[Frontend - vite dev]
    end

    subgraph "CI/CD"
        GITHUB[GitHub Repository]
        ACTIONS[GitHub Actions]
        TESTS[Run Tests]
        BUILD[Build Docker Image]
        PUSH[Push to GHCR]
    end

    subgraph "প্রোডাকশন"
        RENDER_USER[Render - User Service]
        RENDER_ADMIN[Render - Admin Service]
        VERCEL[Vercel - Frontend]
        FIREBASE[Firebase - Admin]
        CF[Cloudflare Worker]
    end

    subgraph "মনিটরিং"
        SENTRY[Sentry - Errors]
        POSTHOG[PostHog - Analytics]
        UPTIME[UptimeRobot - Uptime]
    end

    DEV_LOCAL --> DEV_BACKEND
    DEV_LOCAL --> DEV_FRONTEND

    GITHUB --> ACTIONS
    ACTIONS --> TESTS
    TESTS --> BUILD
    BUILD --> PUSH
    PUSH --> RENDER_USER
    PUSH --> RENDER_ADMIN

    RENDER_USER --> CF
    RENDER_ADMIN --> CF
    CF --> VERCEL
    CF --> FIREBASE

    RENDER_USER --> SENTRY
    RENDER_USER --> POSTHOG
    CF --> UPTIME
```

---

## 📊 আর্কিটেকচার ডেসিশন

### ADR-001: Monorepo আর্কিটেকচার

**ডেসিশন**: pnpm এবং Turborepo সহ মনোরেপো ব্যবহার করুন

**রেশনাল**:
- ফ্রন্টএন্ড এবং ব্যাকএন্ডের মধ্যে শেয়ার্ড কোড
- সার্ভিসের অcross অ্যাটমিক কমিট
- সিমপ্লিফাইড ডিপেন্ডেন্সি ম্যানেজমেন্ট
- কনসিসটেন্ট টুলিং

**বিকল্পগুলি বিবেচনা করা হয়েছে**:
- মাল্টি-রেপো: আরও জটিল, বজায় রাখতে কঠিন
- সিঙ্গেল রেপো: অত্যন্ত কাপলড, স্কেল করতে কঠিন

**পরিণতি**:
- ✅ সহজ ডেভেলপমেন্ট
- ✅ বেটার কোড শেয়ারিং
- ⚠️ বৃহত্তর রিপোজিটরি সাইজ
- ⚠️ আরও জটিল CI/CD

---

### ADR-002: রোল-বেসড সার্ভিস আইসোলেশন

**ডেসিশন**: আলাদা USER এবং ADMIN সার্ভিস

**রেশনাল**:
- সিকিউরিটি: অ্যাডমিন এন্ডপয়েন্ট ইউজার সার্ভিসে এক্সপোজ করা হয় না
- স্কেলেবিলিটি: স্বাধীন স্কেলিং
- রিলায়াবিলিটি: অ্যাডমিন সার্ভিস ইউজার লোড দ্বারা প্রভাবিত হয় না
- কমপ্লায়েন্স: ডিউটি সেপারেশন

**বিকল্পগুলি বিবেচনা করা হয়েছে**:
- সিঙ্গেল সার্ভিস মিডলওয়ার সহ: আরও জটিল, সিকিউর করা কঠিন
- আলাদা রেপো: অত্যন্ত ডুপ্লিকেশন

**পরিণতি**:
- ✅ বেটার সিকিউরিটি
- ✅ স্বাধীন ডিপ্লয়মেন্ট
- ⚠️ কোড ডুপ্লিকেশন
- ⚠️ আরও ইনফ্রাস্ট্রাকচার

---

### ADR-003: পলিগ্লট পেরসিস্টেন্স

**ডেসিশন**: মাল্টিপল ডাটাবেস ব্যবহার করুন (PostgreSQL, Redis, Neo4j, Qdrant)

**রেশনাল**:
- প্রতিটি কাজের জন্য সেরা টুল
- বেটার পারফরম্যান্স
- বিশেষায়িত ফিচার
- ভবিষ্যত-প্রুফ

**বিকল্পগুলি বিবেচনা করা হয়েছে**:
- কেবল PostgreSQL: সীমিত ফিচার, পারফরম্যান্স সমস্যা
- সিঙ্গল NoSQL: রিলেশনাল ক্যাপাবিলিটির ক্ষতি

**পরিণতি**:
- ✅ অপ্টিমাল পারফরম্যান্স
- ✅ রিচ ফিচার
- ⚠️ আরও জটিলতা
- ⚠️ আরও ইনফ্রাস্ট্রাকচার

---

### ADR-004: জিরো-কস্ট ইনফ্রাস্ট্রাকচার

**ডেসিশন**: সম্পূর্ণভাবে ফ্রি-টিয়ার সার্ভিসে চালান

**রেশনাল**:
- AI অ্যাক্সেস ডেমocratize করুন
- কোনো আর্থিক বাধা নেই
- ভিয়াবিলিটি প্রমাণ
- কমিউনিটি বিল্ডিং

**বিকল্পগুলি বিবেচনা করা হয়েছে**:
- পেইড সার্ভিস: বেটার রিলায়াবিলিটি, কিন্তু কস্ট
- সেলফ-হোস্টেড: আরও কন্ট্রোল, কিন্তু জটিলতা

**পরিণতি**:
- ✅ জিরো কস্ট
- ✅ সবাই অ্যাক্সেসযোগ্য
- ⚠️ রিলায়াবিলিটি চ্যালেঞ্জ (অটো-স্লিপ)
- ⚠️ সীমিত রিসোর্স

---

### ADR-005: FastAPI ব্যাকএন্ড

**ডেসিশন**: ব্যাকএন্ডের জন্য FastAPI ব্যবহার করুন

**রেশনাল**:
- হাই পারফরম্যান্স (অ্যাসিঙ্ক)
- অটো-জেনারেটেড OpenAPI ডক্স
- Pydantic সহ টাইপ সেফটি
- আধুনিক Python ফিচার
- গ্রেট ইকোসিস্টেম

**বিকল্পগুলি বিবেচনা করা হয়েছে**:
- Django: অত্যন্ত ভারী, ধীর
- Flask: অত্যন্ত ন্যূনতম, আরও বয়লারপ্লেট
- Node.js: Python-এ টিম এক্সপার্টিজ

**পরিণতি**:
- ✅ ফাস্ট ডেভেলপমেন্ট
- ✅ গ্রেট পারফরম্যান্স
- ✅ অটো-ডকুমেন্টেশন
- ⚠️ Python ইকোসিস্টেম মাত্র

---

## 🔗 সম্পর্কিত ডকুমেন্ট

- [04-FOLDER_STRUCTURE_bn.md](04-FOLDER_STRUCTURE_bn.md) - ডিরেক্টরি সংগঠন
- [05-MODULE_DOCUMENTATION_bn.md](05-MODULE_DOCUMENTATION_bn.md) - মডুল বিবরণ
- [10-DATABASE_DOCUMENTATION_bn.md](10-DATABASE_DOCUMENTATION_bn.md) - ডাটা লেয়ার
- [11-API_DOCUMENTATION_bn.md](11-API_DOCUMENTATION_bn.md) - API লেয়ার
- [14-AI_SYSTEM_DOCUMENTATION_bn.md](14-AI_SYSTEM_DOCUMENTATION_bn.md) - AI লেয়ার
- [21-DEPLOYMENT_DOCUMENTATION_bn.md](21-DEPLOYMENT_DOCUMENTATION_bn.md) - ডিপ্লয়মেন্ট
- [23-SECURITY_DOCUMENTATION_bn.md](23-SECURITY_DOCUMENTATION_bn.md) - সিকিউরিটি

---

## ✅ আর্কিটেকচার ভেরিফিকেশন

**আর্কিটেকচার ভেরিফাই করার উপায়**:

1. **সার্ভিস হেল্থ চেক**:
   ```bash
   curl https://supremeai-backend-08zd.onrender.com/health
   curl https://supremeai-backend-secondary.onrender.com/health
   ```

2. **ডাটাবেস কানেকশন ভেরিফাই**:
   ```bash
   # PostgreSQL চেক
   curl https://supremeai-backend-08zd.onrender.com/api/v1/health/database
   
   # Redis চেক
   curl https://supremeai-backend-08zd.onrender.com/api/v1/health/redis
   ```

3. **AI সার্ভিস টেস্ট**:
   ```bash
   # LLM গেটওয়ে টেস্ট
   curl -X POST https://supremeai-backend-08zd.onrender.com/api/v1/llm/test \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"prompt": "Hello"}'
   ```

4. **এজ লেয়ার ভেরিফাই**:
   ```bash
   # Cloudflare Worker চেক
   curl https://supremeai-backend-08zd.onrender.com/health \
     -H "CF-Worker: true"
   ```

---

**ডকুমেন্ট স্ট্যাটাস**: ✅ সম্পূর্ণ এবং ভেরিফাইড  
**পরবর্তী রিভিউ**: 2025-02-04  
**অনার**: আর্কিটেকচার টিম  
**ক্লাসিফিকেশন**: ইন্টার্নাল
