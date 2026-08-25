# SupremeAI - Technical Specification Document
## Version 1.0.0 | Production-Ready Architecture

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture Overview](#system-architecture-overview)
3. [Component Specifications](#component-specifications)
4. [Data Flow Architecture](#data-flow-architecture)
5. [API Design Specifications](#api-design-specifications)
6. [Database Schema Specifications](#database-schema-specifications)
7. [AI Agent System Specifications](#ai-agent-system-specifications)
8. [Security Architecture](#security-architecture)
9. [Performance Requirements](#performance-requirements)
10. [Scalability & High Availability](#scalability--high-availability)
11. [Monitoring & Observability](#monitoring--observability)
12. [Deployment Architecture](#deployment-architecture)

---

## Executive Summary

SupremeAI is a production-grade AI Agent platform that enables organizations to build, deploy, and manage autonomous AI agents with human-in-the-loop (HITL) capabilities. The system provides a comprehensive infrastructure for multi-agent orchestration, memory management, tool execution, and secure AI operations.

### Key Technical Highlights

| Aspect | Technology Stack | Version |
|--------|------------------|---------|
| Backend Framework | FastAPI (Python) | 0.104+ |
| Database Engine | PostgreSQL + pgvector | 15+ |
| ORM Layer | SQLAlchemy (Async) | 2.0+ |
| Data Validation | Pydantic v2 | 2.0+ |
| Authentication | JWT (python-jose) | 3.3.0 |
| Vector Operations | pgvector | 0.2.0 |
| Frontend Framework | React 18+ with TypeScript | 5.0+ |
| Build Tool | Vite | 5.0+ |
| State Management | Zustand | 4.0+ |
| Styling | Tailwind CSS | 3.4+ |
| Container Runtime | Docker | 24+ |
| Orchestration | Kubernetes (Optional) | 1.28+ |

---

## System Architecture Overview

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SUPREMEAI PLATFORM                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐      │
│  │   React Frontend │◄──►│   API Gateway    │◄──►│   Admin Panel    │      │
│  │   (Vite/TS/TW)   │    │   (FastAPI)      │    │   (React)        │      │
│  └──────────────────┘    └────────┬─────────┘    └──────────────────┘      │
│                                   │                                         │
│                    ┌──────────────┼──────────────┐                          │
│                    ▼              ▼              ▼                          │
│           ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                  │
│           │ Auth Service│ │Agent Engine │ │Memory Svc   │                  │
│           │(JWT/RBAC)   │ │(Orchestrator)│ │(pgvector)   │                  │
│           └──────┬──────┘ └──────┬──────┘ └──────┬──────┘                  │
│                  │               │               │                          │
│                  └───────────────┼───────────────┘                          │
│                                  ▼                                          │
│                    ┌─────────────────────────┐                              │
│                    │     HITL Engine          │                              │
│                    │  (Human-in-the-Loop)     │                              │
│                    └────────────┬────────────┘                              │
│                                 │                                           │
│  ┌──────────────────────────────┼──────────────────────────────┐          │
│  │                              ▼                               │          │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │          │
│  │  │ PostgreSQL  │  │    Redis    │  │ LLM Providers│         │          │
│  │  │ (+pgvector) │  │   (Cache)   │  │(OpenAI/etc) │         │          │
│  │  └─────────────┘  └─────────────┘  └─────────────┘         │          │
│  └────────────────────────────────────────────────────────────┘          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Microservice Boundaries

The system follows a **modular monolith** architecture with clear service boundaries:

| Service | Responsibility | Communication Pattern |
|---------|---------------|----------------------|
| **Auth Service** | User authentication, JWT tokens, RBAC | Internal function calls |
| **Agent Engine** | Agent lifecycle, task execution, tool dispatch | Async event queue |
| **Memory Service** | Vector storage, semantic search, memory retrieval | Direct DB access |
| **HITL Engine** | Approval workflows, escalation, audit logging | Event-driven |
| **LLM Gateway** | Provider abstraction, rate limiting, fallback | HTTP client |
| **Tool Executor** | Sandboxed code execution, API integrations | Isolated processes |

---

## Component Specifications

### 1. Authentication Service

```python
# Technical Specification for Auth Module

class AuthServiceSpec:
    """
    Authentication service implementing JWT-based auth with RBAC.
    
    Token Structure:
    - Access Token: 15-minute expiry, contains user_id, roles, permissions
    - Refresh Token: 7-day expiry, rotated on each use, stored in DB
    - Scope-limited tokens for agent operations
    
    Security Features:
    - Password hashing with bcrypt (cost factor = 12)
    - Account lockout after 5 failed attempts (15-min cooldown)
    - MFA support via TOTP (optional)
    - Session concurrency limits
    """
    
    # Configuration Constants
    ACCESS_TOKEN_EXPIRY_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRY_DAYS: int = 7
    PASSWORD_HASH_COST: int = 12
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15
    MAX_CONCURRENT_SESSIONS: int = 5
    
    # Role Hierarchy
    ROLES: dict = {
        "user": {"permissions": ["read:own", "write:own"]},
        "agent_operator": {
            "permissions": [
                "read:own", "write:own",
                "read:agents", "execute:agents",
                "approve:hitl"
            ]
        },
        "admin": {
            "permissions": [
                "*",  # Full access
                "manage:users", "manage:system",
                "view:audit_logs", "configure:agents"
            ]
        }
    }
```

### 2. Agent Engine Specification

```python
class AgentEngineSpec:
    """
    Multi-agent orchestration engine specification.
    
    Lifecycle States:
    created → configured → active → paused → terminated
    
    Execution Model:
    - Each agent runs in isolated async context
    - Tool execution via sandboxed subprocess
    - Memory integration for context awareness
    - HITL checkpoints for sensitive operations
    """
    
    # Agent Types
    AGENT_TYPES: dict = {
        "conversational": {
            "description": "Chat-based interaction agents",
            "max_context_tokens": 8192,
            "supported_tools": ["web_search", "calculator", "code_executor"]
        },
        "task_agent": {
            "description": "Goal-oriented task execution",
            "max_iterations": 50,
            "planning_enabled": True,
            "supported_tools": ["*"]  # All tools available
        },
        "analyst": {
            "description": "Data analysis and reporting",
            "data_sources": ["database", "api", "file_upload"],
            "output_formats": ["report", "chart", "dataset"]
        },
        "orchestrator": {
            "description": "Multi-agent coordination",
            "can_spawn_subagents": True,
            "max_subagents": 10,
            "delegation_patterns": ["parallel", "sequential", "conditional"]
        }
    }
    
    # Resource Limits
    RESOURCE_LIMITS: dict = {
        "max_execution_time_seconds": 300,
        "max_memory_mb": 512,
        "max_api_calls_per_execution": 100,
        "max_tool_calls_per_execution": 50,
        "context_window_tokens": 128000
    }
    
    # Retry Policy
    RETRY_POLICY: dict = {
        "max_retries": 3,
        "backoff_strategy": "exponential",
        "initial_delay_ms": 1000,
        "max_delay_ms": 30000,
        "retryable_errors": ["rate_limit", "timeout", "server_error"]
    }
```

### 3. Memory Service Specification

```python
class MemoryServiceSpec:
    """
    Three-tier memory system for AI agents.
    
    Memory Tiers:
    1. Working Memory: Current conversation context (ephemeral)
    2. Episodic Memory: Past experiences stored as vectors (pgvector)
    3. Procedural Memory: Learned patterns and best practices
    
    Vector Configuration:
    - Embedding model: text-embedding-3-small (1536 dimensions)
    - Index type: IVFFlat (for approximate search)
    - Distance metric: Cosine similarity
    - Index probes: 10 (balance speed vs accuracy)
    """
    
    # Working Memory Config
    WORKING_MEMORY: dict = {
        "max_messages": 100,
        "context_summary_threshold": 20,  # Summarize after 20 messages
        "ttl_minutes": 60  # Auto-expire after 1 hour
    }
    
    # Episodic Memory (Vector Store) Config
    EPISODIC_MEMORY: dict = {
        "embedding_dimensions": 1536,
        "index_type": "ivfflat",
        "distance_metric": "cosine",
        "index_lists": 100,
        "index_probes": 10,
        "max_vectors_per_collection": 10000000,
        "similarity_threshold": 0.75
    }
    
    # Procedural Memory Config
    PROCEDURAL_MEMORY: dict = {
        "pattern_types": ["success_pattern", "failure_pattern", "optimization"],
        "min_occurrences_for_learning": 3,
        "confidence_threshold": 0.85,
        "auto_apply_confidence": 0.95
    }
```

### 4. HITL Engine Specification

```python
class HITLEngineSpec:
    """
    Human-in-the-Loop approval engine specification.
    
    Approval Workflow:
    Request → Risk Assessment → Queue Assignment → 
    Human Review → Decision → Execute/Escalate
    
    Risk Levels:
    - LOW: Auto-approve with logging
    - MEDIUM: Queue for review within 1 hour
    - HIGH: Immediate notification, block execution
    - CRITICAL: Require multi-person approval
    """
    
    RISK_LEVELS: dict = {
        "LOW": {
            "auto_approve": True,
            "notification": False,
            "sla_minutes": None
        },
        "MEDIUM": {
            "auto_approve": False,
            "notification": True,
            "sla_minutes": 60
        },
        "HIGH": {
            "auto_approve": False,
            "notification": True,
            "urgent": True,
            "sla_minutes": 15
        },
        "CRITICAL": {
            "auto_approve": False,
            "multi_approval_required": True,
            "min_approvers": 2,
            "sla_minutes": 5
        }
    }
    
    # Escalation Rules
    ESCALATION_RULES: list = [
        {
            "condition": "pending_time > sla_minutes * 2",
            "action": "escalate_to_admin",
            "notify": ["team_lead", "security_team"]
        },
        {
            "condition": "rejection_count >= 2",
            "action": "require_security_review",
            "block_execution": True
        }
    ]
```

---

## Data Flow Architecture

### Request Processing Pipeline

```
Client Request
       │
       ▼
┌──────────────┐
│  Rate Limiter │ ← Redis-based sliding window
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Auth Middleware│ ← JWT validation + RBAC check
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Input Sanitizer│ ← XSS, injection prevention
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ PII Detector  │ ← Identify sensitive data
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Route Handler │ ← Business logic execution
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Response     │ ← Format, cache headers, CORS
└──────────────┘
```

### Agent Execution Flow

```
User Task Input
       │
       ▼
┌──────────────────┐
│ Task Parser      │ ← Extract intent, entities, constraints
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Planner Agent    │ ← Generate execution plan
└──────┬───────────┘
       │
       ▼
┌──────────────────┐     ┌─────────────────┐
│ Tool Selector    │────►│ HITL Checkpoint  │ ← If risky action
└──────┬───────────┘     └────────┬────────┘
       │                          │
       ▼                          ▼
┌──────────────────┐     ┌─────────────────┐
│ Tool Executor    │     │ Approval Queue   │
└──────┬───────────┘     └─────────────────┘
       │
       ▼
┌──────────────────┐
│ Result Processor │ ← Format output, update memory
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Memory Updater   │ ← Store experience vectors
└──────┬───────────┘
       │
       ▼
Response to User
```

---

## API Design Specifications

### RESTful API Conventions

| Convention | Example | Description |
|------------|---------|-------------|
| URL Naming | `/api/v1/agents/{id}` | kebab-case, plural nouns |
| HTTP Methods | GET, POST, PUT, DELETE | Standard REST semantics |
| Status Codes | 200, 201, 400, 401, 403, 404, 422, 500 | Semantic use |
| Pagination | `?page=1&size=20` | Zero-indexed pages |
| Filtering | `?status=active&type=task` | Query parameters |
| Sorting | `?sort=created_at&order=desc` | Field-based sorting |
| Versioning | URL path `/api/v1/` | Path-based versioning |

### Response Envelope Standard

```json
{
  "success": true,
  "data": {},
  "meta": {
    "request_id": "uuid",
    "timestamp": "ISO8601",
    "pagination": {
      "page": 1,
      "size": 20,
      "total": 150,
      "pages": 8
    }
  },
  "errors": []
}
```

### Error Response Standard

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "field": "email",
        "message": "Invalid email format",
        "code": "INVALID_FORMAT"
      }
    ],
    "request_id": "uuid",
    "timestamp": "ISO8601"
  }
}
```

---

## Database Schema Specifications

### Core Tables

```sql
-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'user' CHECK (role IN ('user', 'admin', 'agent_operator')),
    is_active BOOLEAN DEFAULT TRUE,
    mfa_secret VARCHAR(255),
    mfa_enabled BOOLEAN DEFAULT FALSE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Agents table
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL,
    config JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'created' CHECK (status IN ('created', 'active', 'paused', 'terminated')),
    system_prompt TEXT,
    model_config JSONB NOT NULL DEFAULT '{}',
    tool_permissions JSONB NOT NULL DEFAULT '[]',
    hitl_policy JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Conversations table
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID REFERENCES agents(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(500),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Messages table
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content TEXT NOT NULL,
    token_count INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Memory vectors table (pgvector)
CREATE TABLE memory_vectors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID REFERENCES agents(id) ON DELETE CASCADE,
    memory_type VARCHAR(50) NOT NULL CHECK (memory_type IN ('episodic', 'procedural', 'semantic')),
    content TEXT NOT NULL,
    embedding VECTOR(1536),  -- pgvector column
    metadata JSONB DEFAULT '{}',
    importance_score FLOAT DEFAULT 0.5,
    access_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

-- Create IVFFlat index for vector similarity search
CREATE INDEX idx_memory_vectors_embedding ON memory_vectors 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- HITL approvals table
CREATE TABLE hitl_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID REFERENCES agents(id),
    request_type VARCHAR(50) NOT NULL,
    request_payload JSONB NOT NULL,
    risk_level VARCHAR(20) NOT NULL CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    status VARCHAR(30) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'escalated', 'expired')),
    requested_by UUID REFERENCES users(id),
    reviewed_by UUID REFERENCES users(id),
    review_notes TEXT,
    decision_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## AI Agent System Specifications

### Agent Configuration Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AgentConfiguration",
  "type": "object",
  "required": ["name", "type", "model"],
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 255,
      "pattern": "^[a-zA-Z0-9_-]+$"
    },
    "type": {
      "type": "string",
      "enum": ["conversational", "task_agent", "analyst", "orchestrator"]
    },
    "model": {
      "type": "object",
      "properties": {
        "provider": {"type": "string", "enum": ["openai", "anthropic", "local"]},
        "name": {"type": "string"},
        "temperature": {"type": "number", "minimum": 0, "maximum": 2},
        "max_tokens": {"type": "integer", "minimum": 1, "maximum": 128000},
        "top_p": {"type": "number", "minimum": 0, "maximum": 1}
      }
    },
    "system_prompt": {
      "type": "string",
      "maxLength": 10000
    },
    "tools": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "hitl_policy": {
      "type": "object",
      "properties": {
        "enabled": {"type": "boolean"},
        "auto_approve_patterns": {"type": "array", "items": {"type": "string"}},
        "require_approval_patterns": {"type": "array", "items": {"type": "string"}},
        "escalation_timeout_minutes": {"type": "number"}
      }
    },
    "memory_config": {
      "type": "object",
      "properties": {
        "working_memory_size": {"type": "integer"},
        "enable_episodic_memory": {"type": "boolean"},
        "enable_procedural_memory": {"type": "boolean"},
        "retention_days": {"type": "integer"}
      }
    },
    "rate_limits": {
      "type": "object",
      "properties": {
        "requests_per_minute": {"type": "integer"},
        "tokens_per_minute": {"type": "integer"},
        "daily_token_limit": {"type": "integer"}
      }
    }
  }
}
```

---

## Security Architecture

### Defense in Depth Strategy

```
Layer 1: Network Security
├── TLS 1.3 encryption everywhere
├── WAF rules (OWASP ModSecurity CRS)
└── DDoS protection (Cloudflare/AWS Shield)

Layer 2: Application Security  
├── Input validation & sanitization
├── SQL injection prevention (parameterized queries)
├── XSS protection (CSP headers, output encoding)
├── CSRF protection (SameSite cookies, tokens)
└── Rate limiting (sliding window algorithm)

Layer 3: Authentication & Authorization
├── JWT with RS256 signing
├── RBAC with principle of least privilege
├── Session management (rotation, expiration)
├── MFA support (TOTP)
└── Audit logging (all auth events)

Layer 4: Data Protection
├── Encryption at rest (AES-256)
├── Encryption in transit (TLS 1.3)
├── PII detection & redaction
├── Data retention policies
└── GDPR compliance features

Layer 5: AI-Specific Security
├── Prompt injection detection
├── Output filtering & safety checks
├── Tool execution sandboxing
├── HITL for high-risk operations
└── Usage monitoring & anomaly detection
```

---

## Performance Requirements

### SLA Targets

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| API Response Time (P50) | < 200ms | Prometheus histogram |
| API Response Time (P95) | < 500ms | Prometheus histogram |
| API Response Time (P99) | < 1000ms | Prometheus histogram |
| Error Rate | < 0.1% | Success/error counters |
| Availability | 99.9% Uptime | Uptime monitoring |
| Agent Execution Start | < 2s | Time to first response |
| Vector Search Latency | < 100ms (P95) | Memory service metrics |

### Throughput Targets

| Operation | Target RPS | Peak Capacity |
|-----------|-----------|---------------|
| API Requests | 1000 RPS | 5000 RPS |
| Agent Executions | 100/min | 500/min |
| Message Send/Receive | 500 RPS | 2000 RPS |
| Vector Searches | 200 RPS | 1000 RPS |
| HITL Approvals | 50/min | 200/min |

---

## Scalability & High Availability

### Horizontal Scaling Strategy

```
                    ┌─────────────┐
                    │   Load      │
                    │  Balancer   │
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   ┌────────────┐  ┌────────────┐  ┌────────────┐
   │  Backend   │  │  Backend   │  │  Backend   │
   │  Instance  │  │  Instance  │  │  Instance  │
   │     1      │  │     2      │  │     3      │
   └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
         │               │               │
         └───────────────┼───────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
   ┌────────────┐  ┌────────────┐  ┌────────────┐
   │ PostgreSQL │  │   Redis    │  │ Object     │
   │  Primary   │  │   Cluster  │  │ Storage    │
   │  + Replica │  │            │  │ (S3/GCS)   │
   └────────────┘  └────────────┘  └────────────┘
```

### Database Scaling Approach

1. **Read Replicas**: Offload read-heavy queries to replicas
2. **Connection Pooling**: PgBouncer for efficient connection management
3. **Partitioning**: Time-based partitioning for messages/memory tables
4. **Caching Strategy**: Multi-layer caching (Redis CDN Browser)

---

## Monitoring & Observability

### Three Pillars Implementation

#### 1. Metrics (Prometheus + Grafana)

- **RED Method**: Rate, Errors, Duration for all endpoints
- **USE Method**: Utilization, Saturation, Errors for resources
- **Custom Metrics**: Agent executions, HITL approvals, vector operations

#### 2. Tracing (OpenTelemetry + Jaeger)

- **Distributed Tracing**: End-to-end request tracing
- **Span Attributes**: User ID, Agent ID, Request ID
- **Sampling Strategy**: 100% for errors, 10% for success

#### 3. Logging (Structured JSON)

- **Log Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Correlation IDs**: Trace ID in all log entries
- **Sensitive Data**: Automatic PII redaction

---

## Deployment Architecture

### Environment Strategy

| Environment | Purpose | Data | Scale |
|-------------|---------|------|-------|
| Development | Local development | Mock/seeded | Single instance |
| Staging | Pre-production testing | Anonymized copy | Minimal HA |
| Production | Live traffic | Real data | Full HA |

### CI/CD Pipeline

```
Code Push → Unit Tests → Integration Tests → 
Security Scan → Build Image → Push to Registry → 
Deploy to Staging → Smoke Tests → 
Manual Approval → Deploy to Production → 
Health Checks → Monitor Rollback
```

---

## Appendix: Configuration Reference

### Environment Variables

```bash
# Application
APP_NAME=supremeai
APP_ENV=production
DEBUG=false
SECRET_KEY=<generated-secret>

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/supremeai
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=<jwt-secret>
JWT_ALGORITHM=RS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# LLM Providers
OPENAI_API_KEY=<key>
ANTHROPIC_API_KEY=<key>
DEFAULT_MODEL=gpt-4-turbo

# Monitoring
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
ENABLE_METRICS=true
ENABLE_TRACING=true

# Security
CORS_ORIGINS=https://app.supremeai.com
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=100
```

---

*Document Version: 1.0.0*
*Last Updated: 2024*
*Maintained by: SupremeAI Platform Team*
