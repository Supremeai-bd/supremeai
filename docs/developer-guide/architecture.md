# Architecture Overview

## Overview

SupremeAI 2.0 is a multi-cloud AI orchestration platform built on FastAPI with a React/Vite frontend. It targets zero-cost operation through aggressive free-tier utilization across multiple AI providers, while maintaining enterprise-grade security through the AutonoGuard Engine.

## Core Philosophy

1. **Zero Cost**: Utilize free-tier services and open-source libraries (DeepSeek-V3, Kimi K2.5, Together AI fallback, Supabase, Render, Vercel, Firebase).
2. **High Scalability & Performance**: Asynchronous non-blocking architecture designed to handle sudden user traffic spikes cleanly.
3. **Zero Breakage & Targeted Delta Patching**: Running production logic, database schemas, and configuration state are preserved flawlessly.
4. **Human-in-the-Loop with Minimal Effort**: High-privilege destructive actions require JIT OTP verification.
5. **Malware Immunity via JIT Defense**: Assume the local client session might be compromised.
6. **Self-Healing Engine**: Autonomous central error bus automatically attempts error remediation.
7. **Failure-Aware Context**: System retains past failure history and routes dynamically to prevent repeating failed attempts.

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    CLIENT LAYER                          │
│  Web (React/Vite) | Mobile (Flutter) | Desktop (Electron)│
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   API GATEWAY                            │
│  Rate Limiter → IP Churn Check → JIT OTP Verify          │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   AUTONOGUARD ENGINE                     │
│  JIT OTP | IP Churn | AST Scan | Circuit Breaker | Heal   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   AGENT SWARM                            │
│  Browser | Coding | Research | Email | GitHub | Custom    │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   LLM GATEWAY                            │
│  DeepSeek | Groq | OpenAI | Gemini | Client-side Ollama  │
└─────────────────────────────────────────────────────────┘

```

## Monorepo Structure

```
supremeai/
├── admin/                    # Admin god mode portal
├── apps/
│   ├── mobile/              # Flutter mobile app
│   ├── studio-client/        # React/Vite web & desktop client
│   └── web-chat/            # Lightweight web chat
├── backend/
│   ├── api/                 # 74+ API router modules
│   ├── brain/               # LLM model router, agent departments
│   ├── core/                # 30+ core resilience modules
│   ├── memory/              # ChromaDB, SQLite, Supabase stores
│   └── tools/               # AI agents (Browser, Vision, Email, etc.)
├── docs/                    # Documentation
├── infrastructure/          # Cloudflare CDN, Terraform, Firebase
└── scripts/                 # Bootstrap, deploy, secret sync tools
```

## Data Architecture

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Cache | Redis (Upstash) | Session state, rate limiting, semantic cache |
| Vector DB | ChromaDB | Embeddings, similarity search |
| Relational | PostgreSQL | Structured data, user data |
| Document | Supabase/Firestore | Dynamic config, tenant settings |
| Object | Firebase Storage | File uploads, media |

## Deployment Topology

| Service | Provider | Cost | Purpose |
|---------|----------|------|---------|
| Cloud Run | GCP Always Free | $0 | Primary backend compute |
| Firebase | Google Free Tier | $0 | Authentication + Hosting |
| Render | Free 750h/month | $0 | Backup backend |
| Upstash Redis | Free Tier | $0 | Session state + rate limiting |
| Cloudflare Workers | Free Tier | $0 | Load balancing |
