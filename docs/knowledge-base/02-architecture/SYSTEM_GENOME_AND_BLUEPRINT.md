# 🧬 SupremeAI 2.0 — System Genome & Complete Architecture Blueprint

> **Knowledge Card:** `SYSTEM_GENOME`  
> **Responsibility:** Defines the holistic system architecture, module topology, data flow mesh, and inter-service dependencies.

---

## 🏛️ High-Level Enterprise Topology

```mermaid
graph TB
    subgraph Clients["📱 Client Layer"]
        ReactWeb["React/Vite Web App (apps/studio-client)"]
        FlutterMobile["Flutter Mobile App (apps/mobile)"]
        VSCodeExt["VS Code Extension (tools/vscode-extension)"]
    end

    subgraph Edge["☁️ Edge Gateway Layer"]
        CFWorker["Cloudflare Worker / Reverse Proxy"]
        CostGuard["CostGuard & Rate Limiter"]
    end

    subgraph Backend["⚙️ Backend Core (FastAPI)"]
        FastAPI["FastAPI Orchestrator Engine"]
        LLMRouter["LLM Intelligence Router"]
        SelfHealer["SelfHealer Engine"]
        AutonoGuard["AutonoGuard JIT Security Mesh"]
        ConfigProxy["DynamicConfigProxy (Firestore)"]
    end

    subgraph Providers["🧠 Multi-Cloud AI Providers"]
        Moonshot["Moonshot Kimi K2.5 (Reasoning / Bengali)"]
        DeepSeek["DeepSeek V3 (Coding & Math)"]
        TogetherAI["Together AI (Auto-Fallback)"]
        GCP["Google Cloud Platform / Cloud Run"]
    end

    subgraph Storage["💾 Persistence & Cache Layer"]
        Firestore["Google Firestore (Tenant DB & Configs)"]
        Redis["Redis (Cache & Context Store)"]
    end

    Clients --> Edge
    Edge --> Backend
    Backend --> Providers
    Backend --> Storage
```

---

## 🔬 Component Breakdown & Responsibility Matrix

| Component | Path | Primary Purpose | Key Dependencies | Used By | Failure Mode & Recovery |
|---|---|---|---|---|---|
| **FastAPI Core** | `backend/` | Central REST, SSE, & WS orchestrator | `poetry`, `pydantic`, `uvicorn` | All Clients | Auto-restarted by Cloud Run / Render |
| **LLM Router** | `backend/core/llm_router/` | Provider Selection Intelligence (PSI-001 ~ PSI-005) | Provider API Keys | FastAPI Core | Falls back to Together AI on rate limits |
| **AutonoGuard Mesh** | `backend/core/security/` | On-spot JIT OTP & AST auditing | Redis, Firestore | Sensitive Admin APIs | Rejects request; triggers OTP alert |
| **DynamicConfigProxy** | `backend/core/config/` | Database-driven runtime settings | Firestore NoSQL | Entire Backend | Falls back to local default settings |
| **Studio Client** | `apps/studio-client/` | React/Vite web application & God Mode | Vite, React, React Query | End Users / Admins | Served statically via Vercel |

---

## 📊 End-to-End Request Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Admin
    participant Client as Studio Client (React)
    participant Gateway as Cloudflare Worker / Gateway
    participant FastAPI as Backend Orchestrator
    participant Guard as AutonoGuard (JIT OTP)
    participant Router as LLM Intelligence Router
    participant Provider as AI Provider (Kimi / DeepSeek)
    participant DB as Firestore & Redis

    User->>Client: Send Code / Prompt Request
    Client->>Gateway: HTTP POST /api/v1/chat/completions
    Gateway->>FastAPI: Forward Request with Auth Headers
    FastAPI->>Guard: Verify JWT & JIT OTP (if sensitive)
    Guard-->>FastAPI: Verification Passed (OK)
    FastAPI->>Router: Route Prompt (Evaluate PSI-001/002)
    Router->>DB: Check Redis Cache for identical prompt
    alt Cache Hit
        DB-->>Router: Return Cached Response
        Router-->>FastAPI: Return Cached Result
    else Cache Miss
        Router->>Provider: Invoke Primary Provider (e.g. DeepSeek)
        alt Provider Rate Limit (429)
            Provider-->>Router: 429 Too Many Requests
            Router->>Provider: Fallback to Together AI
        end
        Provider-->>Router: Stream Response Tokens
        Router->>DB: Store in Redis Cache
    end
    FastAPI-->>Client: Stream Response via SSE / JSON
    Client-->>User: Render Interactive Result
```
