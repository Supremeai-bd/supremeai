# SupremeAI 🚀

<p align="center">
  <strong>Production-Grade AI Agent Platform with Human-in-the-Loop Security</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-0.104+-green.svg" alt="FastAPI" />
  <img src="https://img.shields.io/badge/React-18+-61DAFB.svg" alt="React" />
  <img src="https://img.shields.io/badge/TypeScript-5.0+-3178C6.svg" alt="TypeScript" />
  <img src="https://img.shields.io/badge/PostgreSQL-pgvector-336791.svg" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License" />
</p>

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Installation Guide](#installation-guide)
- [API Documentation](#api-documentation)
- [AI Agent System](#ai-agent-system)
- [Database Schema](#database-schema)
- [Configuration](#configuration)
- [Security](#security)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Overview

SupremeAI is an enterprise-grade AI Agent platform that enables organizations to build, deploy, and manage intelligent AI agents with robust security controls. Built with modern web technologies, it provides:

- **Multi-Agent Orchestration** - Deploy specialized agents for different tasks
- **Human-in-the-Loop (HITL)** - Critical security layer for sensitive operations
- **Vector Memory System** - Persistent, searchable agent memory using pgvector
- **Zero-Cost Deployment** - Designed for free-tier cloud services
- **Full Observability** - OpenTelemetry integration for monitoring

### Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Backend** | Python 3.11+ / FastAPI | High-performance async API server |
| **Frontend** | React 18 / TypeScript / Vite | Modern SPA with type safety |
| **Database** | PostgreSQL + pgvector | Relational data + vector search |
| **Authentication** | JWT (python-jose) | Secure token-based auth |
| **AI Integration** | OpenAI-compatible APIs | LLM-powered agent intelligence |
| **Observability** | OpenTelemetry | Distributed tracing & metrics |
| **Styling** | Tailwind CSS / shadcn/ui | Utility-first UI components |

---

## Features

### 🔐 Enterprise Security
- **Role-Based Access Control (RBAC)** - Granular permissions (user, admin, agent_operator)
- **Human-in-the-Loop (HITL)** - Approval workflows for sensitive operations
- **Input Sanitization** - Protection against injection attacks
- **Audit Logging** - Complete action trail for compliance

### 🤖 Advanced AI Agents
- **Customizable System Prompts** - Tailor agent behavior per use case
- **Tool Integration** - Web search, calculator, code interpreter, SQL, file management
- **Three-Tier Memory** - Working, episodic, and procedural memory systems
- **Anti-Pattern Prevention** - Built-in guards against common AI failures

### 📊 Production Ready
- **Auto-scaling Architecture** - Horizontal scaling support
- **Circuit Breakers** - Cascade failure prevention
- **Rate Limiting** - Protect against abuse
- **Health Checks** - Comprehensive system monitoring

### 💰 Zero-Cost Friendly
- **Free-Tier Compatible** - Works on Supabase, Render, Vercel free plans
- **Optimized Resource Usage** - Efficient token management
- **Cost Alerts** - Budget monitoring and alerts

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (Vite)                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ Dashboard │  │ Agent    │  │ Chat     │  │ Admin Panel   │  │
│  │ View     │  │ Manager  │  │ Interface│  │               │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───────┬────────┘  │
│       └──────────────┴──────────────┘                │          │
└─────────────────────────────────────────────────────┼──────────┘
                                                      │ REST API
┌─────────────────────────────────────────────────────┼──────────┐
│                                              Backend (FastAPI)   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ Auth     │  │ Agent    │  │ HITL     │  │ Memory         │  │
│  │ Service  │  │ Orchestr │  │ Engine   │  │ Service        │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───────┬────────┘  │
│       └──────────────┴──────────────┘                │          │
├─────────────────────────────────────────────────────┼──────────┤
│                                                     │          │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────┴──────────┐│
│  │ PostgreSQL   │  │ Redis        │  │ AI Provider            ││
│  │ + pgvector   │  │ (Cache)      │  │ (OpenAI/Compatible)    ││
│  └──────────────┘  └──────────────┘  └────────────────────────┘│
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              OpenTelemetry Collector                     │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Core Components

1. **API Layer** - RESTful endpoints with automatic OpenAPI documentation
2. **Agent Runtime** - Manages agent lifecycle, context, and tool execution
3. **HITL Engine** - Queues, tracks, and enforces approval workflows
4. **Memory Service** - Vector storage and semantic search operations
5. **Auth Module** - JWT generation, validation, and role enforcement

---

## Quick Start

### Prerequisites

- Python 3.11 or higher
- Node.js 18+ LTS
- Git
- Docker (optional)

### Clone & Install

```bash
# Clone the repository
git clone https://github.com/SaifulHaqueNiloy/supremeai.git
cd supremeai

# Backend setup
cd backend
# Install Poetry if you don't have it
pip install poetry
poetry install
cp .env.example .env
# Edit .env with your settings

# Frontend setup (new terminal)
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

### Run Development Servers

```bash
# Terminal 1: Backend
cd backend
python main.py

# Terminal 2: Frontend  
cd frontend
npm run dev
```

Visit http://localhost:5173 for the frontend, http://localhost:8000/docs for API docs.

---

## Installation Guide

### Backend Setup (Detailed)

#### 1. Environment Configuration

Create `.env` file in `backend/` directory:

```env
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/supremeai

# Security (CHANGE THESE IN PRODUCTION!)
SECRET_KEY=your-super-secret-key-at-least-32-characters-long
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# AI Provider
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4-turbo

# Application
APP_NAME=SupremeAI
DEBUG=true
LOG_LEVEL=INFO

# CORS
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

#### 2. Database Setup

```bash
# Using Docker for local PostgreSQL with pgvector
docker run --name supremeai-db \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=supremeai \
  -p 5432:5432 \
  -d pgvector/pgvector:pg16

# Run migrations
cd backend
alembic upgrade head
```

#### 3. Start Backend

```bash
cd backend
python main.py
```

Access Swagger UI at: http://localhost:8000/docs

### Frontend Setup (Detailed)

```bash
cd frontend

# Install dependencies
npm install

# Environment configuration (.env.local)
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_APP_NAME=SupremeAI

# Start development server
npm run dev
```

Access frontend at: http://localhost:5173

### Docker Compose (All-in-One)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

---

## API Documentation

### Base URL

- **Development**: `http://localhost:8000/api/v1`
- **Production**: `https://api.yourdomain.com/api/v1`

### Authentication

All protected endpoints require Bearer token authentication:

```http
Authorization: Bearer <your-jwt-token>
```

### Endpoints Summary

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| **Authentication** |
| POST | `/auth/register` | Register new user | No |
| POST | `/auth/login` | User login | No |
| POST | `/auth/refresh` | Refresh token | Yes |
| GET | `/auth/me` | Get current user | Yes |
| **Agents** |
| GET | `/agents` | List all agents | Yes |
| POST | `/agents` | Create new agent | Yes |
| GET | `/agents/{id}` | Get agent details | Yes |
| PUT | `/agents/{id}` | Update agent | Yes |
| DELETE | `/agents/{id}` | Delete agent | Yes |
| **Conversations** |
| POST | `/agents/{id}/conversations` | Send message to agent | Yes |
| GET | `/agents/{id}/conversations/{conv_id}/messages` | Get conversation history | Yes |
| **HITL (Human-in-the-Loop)** |
| GET | `/hitl/pending` | List pending approvals | Yes |
| POST | `/hitl/actions/{id}/decision` | Approve/reject action | Yes |
| **Memory** |
| POST | `/memory/store` | Store memory vector | Yes |
| POST | `/memory/search` | Semantic memory search | Yes |
| **Admin** |
| GET | `/admin/health` | System health check | Admin |
| GET | `/admin/stats` | Usage statistics | Admin |

### Example Requests

#### Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "role": "user"
  }
}
```

#### Create Agent

```bash
curl -X POST http://localhost:8000/api/v1/agents \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "name": "Research Assistant",
    "description": "Helps with research tasks",
    "system_prompt": "You are a helpful research assistant...",
    "model": "gpt-4-turbo",
    "tools": ["web_search", "calculator"],
    "hitl_enabled": true
  }'
```

#### Send Message to Agent

```bash
curl -X POST http://localhost:8000/api/v1/agents/{agent_id}/conversations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "message": "What is the latest research on quantum computing?",
    "stream": true
  }'
```

For complete API documentation with all endpoints, request/response schemas, and examples, see the full documentation file.

---

## AI Agent System

### Agent Architecture

SupremeAI implements a sophisticated multi-agent architecture designed for production reliability:

```
┌─────────────────────────────────────────────────────────┐
│                    Agent Runtime                          │
│                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌────────────────┐  │
│  │ Context     │  │ Tool        │  │ Memory         │  │
│  │ Manager     │  │ Executor    │  │ Manager        │  │
│  └──────┬──────┘  └──────┬──────┘  └───────┬────────┘  │
│         │                │                 │           │
│  ┌──────┴────────────────┴─────────────────┴────────┐  │
│  │              Orchestration Layer                  │  │
│  │  - Prompt Engineering                            │  │
│  │  - Response Validation                           │  │
│  │  - Error Handling                                │  │
│  └──────────────────────────────────────────────────┘  │
│                          │                              │
│  ┌───────────────────────┴──────────────────────────┐  │
│  │              HITL Security Layer                   │  │
│  │  - Action Classification                          │  │
│  │  - Approval Queue                                 │  │
│  │  - Audit Trail                                    │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Agent Types

| Type | Use Case | HITL Level | Tools Available |
|------|----------|------------|-----------------|
| **General Assistant** | Customer support, Q&A | Low | Conversation, knowledge base |
| **Research Agent** | Data gathering, analysis | Medium | Web search, summarization |
| **Code Agent** | Development assistance | High | Code gen, debugging, execution |
| **Data Analyst** | Reports, visualization | Medium | SQL, charts, statistics |
| **Admin Agent** | System operations | Critical | User mgmt, monitoring |

### Tool System

Agents can be equipped with various tools:

| Tool | Description | HITL Required | Timeout |
|------|-------------|---------------|---------|
| `web_search` | Search the web for information | No | 10s |
| `calculator` | Perform mathematical calculations | No | 5s |
| `code_interpreter` | Execute Python code safely | Yes | 30s |
| `file_manager` | Read/write files | Yes | 15s |
| `sql_query` | Execute read-only queries | Yes | 20s |
| `api_client` | Call external APIs | Yes | 30s |

### Memory Architecture

**Three-Tier Memory System:**

1. **Working Memory (Short-term)**
   - Current conversation context
   - Active goals and intermediate results
   - Auto-cleared when session ends
   - Configurable token limit (default: 8K)

2. **Episodic Memory (Long-term)**
   - Significant interactions stored permanently
   - Vector embeddings for semantic search
   - Includes timestamps, importance scores
   - Enables cross-session recall

3. **Procedural Memory**
   - Predefined skills and SOPs
   - Response templates
   - Domain-specific knowledge bases
   - Configured by developers

### Anti-Pattern Prevention

SupremeAI addresses these common AI Agent anti-patterns:

| Anti-Pattern | Mitigation | Status |
|--------------|------------|--------|
| Prompt-and-Pray | Structured prompts with validation | ✅ PASS |
| Memory Amnesia | Three-tier memory architecture | ✅ PASS |
| Silent Failure | Comprehensive error handling + logging | ✅ PASS |
| Loop Trap | Max iteration limits + timeout guards | ✅ PASS |
| Context Overflow | Automatic summarization + pruning | ✅ PASS |
| Tool Hallucination | Schema validation + result checking | ✅ PASS |
| Permission Creep | RBAC + HITL for sensitive ops | ✅ PASS |
| Cascade Failure | Circuit breakers + graceful degradation | ✅ PASS |
| Observability Gap | OpenTelemetry full-stack tracing | ✅ PASS |
| Cost Runaway | Token budgets + spend alerts | ✅ PASS |

---

## Database Schema

### Entity Relationship Diagram

```
users ──< agents ──< conversations ──< messages
   │         │                    │
   │         │                    ├── hitl_actions > users (reviewer)
   │         │
   │         └──> agent_memories (pgvector)
   │
   └──> hitl_actions (as reviewer)
```

### Key Tables

#### users
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'user',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);
```

#### agents
```sql
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    owner_id UUID REFERENCES users(id),
    system_prompt TEXT NOT NULL,
    model VARCHAR(100) DEFAULT 'gpt-4-turbo',
    configuration JSONB DEFAULT '{}',
    hitl_config JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'active'
);
```

#### agent_memories (Vector Store)
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE agent_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id),
    content TEXT NOT NULL,
    embedding vector(1536),  -- For OpenAI ada-002
    memory_type VARCHAR(50) DEFAULT 'fact',
    metadata JSONB DEFAULT '{}',
    importance FLOAT DEFAULT 0.5,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for similarity search
CREATE INDEX idx_memories_embedding 
ON agent_memories 
USING ivfflat (embedding vector_cosine_ops);
```

#### hitl_actions
```sql
CREATE TABLE hitl_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID REFERENCES agents(id),
    action_type VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    payload JSONB NOT NULL,
    priority VARCHAR(20) DEFAULT 'medium',
    status VARCHAR(30) DEFAULT 'pending',  // pending, approved, rejected, expired
    decision_reason TEXT,
    requested_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);
```

For complete schema with all tables, indexes, and migrations, see the documentation.

---

## Configuration

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` |
| `SECRET_KEY` | JWT signing secret (min 32 chars) | `your-random-secret-key...` |
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` |
| `ALLOWED_ORIGINS` | CORS allowed origins | `http://localhost:5173` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | `SupremeAI` | Application name |
| `DEBUG` | `false` | Debug mode (dev only!) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `JWT_EXPIRE_MINUTES` | `60` | Token expiration time |
| `RATE_LIMIT_REQUESTS` | `100` | Requests/min/user |
| `VECTOR_DIMENSIONS` | `1536` | Embedding dimensions |

### Agent Configuration Example

```json
{
  "name": "Custom Agent",
  "model": "gpt-4-turbo-preview",
  "behavioral_settings": {
    "temperature": 0.3,
    "max_tokens": 3000
  },
  "tool_config": {
    "enabled_tools": ["web_search", "calculator"],
    "max_tool_calls_per_message": 5
  },
  "hitl_config": {
    "enabled": true,
    "require_approval_for": ["file_write", "external_api"],
    "auto_approve": ["web_search", "calculator"]
  }
}
```

See full `.env.example` in the repository for all options.

---

## Security

### Authentication & Authorization

- **JWT-based authentication** with configurable expiration
- **Role-Based Access Control (RBAC)** with three roles:
  - `user`: Basic access, manage own agents
  - `agent_operator`: Extended limits, team features
  - `admin`: Full system access, user management

### Human-in-the-Loop (HITL)

Critical security feature requiring human approval for sensitive actions:

**Actions Requiring Approval:**
- File write/delete operations
- External API calls
- Database modifications (INSERT/UPDATE/DELETE)
- Code execution
- Data export
- User management
- Configuration changes

**Approval Workflow:**
1. Agent requests action → System validates
2. Action queued with priority & expiry
3. Notification sent to reviewers
4. Reviewer examines payload
5. Decision recorded (approve/reject/expired)
6. Result logged for audit

### Security Best Practices

- [x] Input sanitization against injection attacks
- [x] PII detection and redaction
- [x] Rate limiting on all endpoints
- [x] Audit logging for all actions
- [x] TLS encryption required in production
- [x] Regular security dependency updates

### Recommended Security Checklist

- [ ] Rotate `SECRET_KEY` every 90 days
- [ ] Use strong passwords (12+ characters)
- [ ] Enable 2FA for admin accounts
- [ ] Review HITL pending queue daily
- [ ] Monitor anomaly detection alerts
- [ ] Keep dependencies updated weekly
- [ ] Enable rate limiting in production
- [ ] Use separate API keys per environment
- [ ] Implement IP allowlisting for admin endpoints
- [ ] Regular penetration testing

---

## Deployment

### Zero-Cost Deployment Stack

Deploy for FREE using these services:

| Component | Service | Free Tier Limits |
|-----------|---------|------------------|
| Database | Supabase | 500MB, 2GB bandwidth/mo |
| Backend | Render | 750 hours/mo, 512MB RAM |
| Frontend | Vercel | 100GB bandwidth/mo |
| Storage | Cloudflare R2 | 10GB storage |
| CDN | Cloudflare | Unlimited basic CDN |
| Monitoring | Grafana Cloud | 10k metrics, 14d retention |

### Render Deployment (Backend)

```yaml
# render.yaml
services:
  - type: web
    name: supremeai-backend
    runtime: python
    buildCommand: pip install poetry && poetry install --only main
    startCommand: python main.py
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: SECRET_KEY
        generateValue: true
    healthCheckPath: /health
```

### Vercel Deployment (Frontend)

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "vite",
  "rewrites": [
    {
      "source": "/api/(.*)",
      "destination": "https://your-backend.render.dev/api/$1"
    }
  ]
}
```

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# Or build manually
docker build -t supremeai-backend .
docker run -p 8000:8000 supremeai-backend
```

### Production Checklist

Before going to production:

- [ ] Database migrated (`alembic upgrade head`)
- [ ] `SECRET_KEY` set to cryptographically secure value
- [ ] `OPENAI_API_KEY` with production quota
- [ ] `ALLOWED_ORIGINS` set to production domain(s)
- [ ] `DEBUG=false`
- [ ] `LOG_LEVEL=WARNING` or `ERROR`
- [ ] HTTPS/TLS certificates active
- [ ] Health check endpoint accessible
- [ ] Monitoring connected
- [ ] Backup schedule configured
- [ ] Error tracking integrated

---

## Contributing

We welcome contributions! Please follow these guidelines:

### Development Workflow

1. **Fork** the repository
2. **Clone** your fork: `git clone https://github.com/YOUR_USERNAME/supremeai.git`
3. **Create** a branch: `git checkout -b feature/your-feature-name`
4. **Make** your changes with clean, documented code
5. **Test** thoroughly (unit + integration tests)
6. **Commit** with conventional commits: `git commit -m "feat: add new feature"`
7. **Push** to your fork: `git push origin feature/your-feature-name`
8. **Open** a Pull Request on GitHub

### Code Standards

- **Python**: PEP 8, Black formatter, flake8 linting
- **TypeScript**: ESLint + Prettier
- **Commits**: Conventional Commits specification
- **Tests**: pytest (backend), vitest (frontend), min 80% coverage
- **Docs**: Docstrings required for all functions/classes

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

### Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No new warnings
```

---

## Troubleshooting

### Common Issues

#### Database Connection Failed
```bash
# Check if PostgreSQL is running
pg_isready

# Verify connection string format
# Ensure database exists
createdb supremeai

# Check network connectivity
ping db-host
```

#### JWT Token Not Working
1. Verify `SECRET_KEY` matches between instances
2. Check token hasn't expired (default: 1 hour)
3. Ensure `Bearer` prefix in Authorization header
4. Verify token format at jwt.io

#### pgvector Extension Not Found
```sql
-- Enable extension
CREATE EXTENSION vector;

-- Or use pgvector-enabled database service
-- (Supabase, Neon, or pgvector Docker image)
```

#### High Latency on API Calls
1. Check AI provider status page
2. Enable response streaming
3. Review token count in requests
4. Check database query performance
5. Consider caching frequent queries

### Getting Help

- 📖 **Documentation**: This README and inline code comments
- 🐛 **Issues**: [GitHub Issues](https://github.com/SaifulHaqueNiloy/supremeai/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/SaifulHaqueNiloy/supremeai/discussions)
- 🔒 **Security**: Email security@supremeai.app (for vulnerabilities only)

---

## Project Structure

```
supremeai/
├── backend/
│   ├── app/
│   │   ├── api/              # API route handlers
│   │   │   ├── v1/           # Versioned API endpoints
│   │   │   ├── deps.py       # Dependencies
│   │   │   └── auth.py       # Auth routes
│   │   ├── core/             # Core configuration
│   │   │   ├── config.py     # Settings
│   │   │   ├── security.py   # Auth utilities
│   │   │   └── logging.py    # Logging setup
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic
│   │   │   ├── agent.py      # Agent orchestration
│   │   │   ├── memory.py     # Memory/vector service
│   │   │   └── hitl.py       # HITL engine
│   │   └── agents/           # AI Agent system
│   │       ├── base.py       # Base agent class
│   │       ├── tools.py      # Tool definitions
│   │       └── memory.py     # Memory management
│   ├── tests/                # Test suites
│   ├── alembic/              # DB migrations
│   ├── requirements.txt      # Python dependencies
│   └── pyproject.toml        # Project config
├── frontend/
│   ├── src/
│   │   ├── components/       # Reusable components
│   │   ├── pages/            # Page views
│   │   ├── hooks/            # Custom React hooks
│   │   ├── stores/           # Zustand state stores
│   │   ├── lib/              # Utilities, API client
│   │   └── types/            # TypeScript types
│   ├── public/               # Static assets
│   ├── package.json
│   └── vite.config.ts
├── docs/                     # Additional documentation
├── AGENTS.md                 # Agent configuration
├── cine_rules.json           # Agent rules engine
├── docker-compose.yml        # Docker setup
├── .env.example              # Env template
└── README.md                 # This file
```

---

## Roadmap

### v1.1.0 (Planned)
- Multi-agent collaboration protocols
- Enhanced analytics dashboard
- Plugin marketplace foundation

### v1.2.0 (Planned)
- Voice interaction support
- Advanced workflow automation
- Mobile-responsive admin panel

### v2.0.0 (Vision)
- Full plugin system
- Agent marketplace
- Enterprise SSO integration
- Multi-model support (Claude, Gemini, Llama)

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

```
MIT License

Copyright (c) 2025 Saiful Haque Niloy

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

---

## Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [React](https://react.dev/) - UI library
- [pgvector](https://github.com/pgvector/pgvector) - Vector similarity search
- [OpenTelemetry](https://opentelemetry.io/) - Observability framework
- [shadcn/ui](https://ui.shadcn.com/) - Beautiful components

---

<p align="center">
  <strong>SupremeAI</strong> - Building the future of AI agents, together 🚀
</p>

<p align="center">
  <a href="#top">Back to top ↑</a>
</p>
