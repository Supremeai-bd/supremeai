# 📐 SupremeAI 2.0 System Diagrams & Visual Architecture

> **নথি সংক্ষেপ (Summary):** এই নথিতে SupremeAI 2.0-এর হাই-লেভেল সিস্টেম আর্কিটেকচার, ডেটাবেস স্কিমা (ERD), এজেন্ট অর্কেস্ট্রেশন, সিকিউরিটি সিকোয়েন্স, সেলফ-হিলিং স্টেট এবং সিআই/সিডি ডিপ্লয়মেন্ট ফ্লো-এর ভিজ্যুয়াল Mermaid ডায়াগ্রামগুলো সংরক্ষিত হয়েছে।

---

## 🏗️ 1. High-Level Architecture (উচ্চ-স্তরের সিস্টেম আর্কিটেকচার)

```mermaid
graph TB
    subgraph "Frontend Layer"
        A[React/Vite Web App] 
        B[Electron Desktop App]
        C[Flutter Mobile App]
    end

    subgraph "API Gateway & Load Balancing"
        D[FastAPI Backend<br>(User/Admin Mode)]
        E[Render Primary Service]
        F[Render Secondary Service<br>(Auto-failover)]
    end

    subgraph "Core Services"
        G[Authentication & RBAC]
        H[JIT OTP Service]
        I[AI Agent Orchestrator]
        J[Self-Healing Engine]
        K[Central Error Bus]
    end

    subgraph "Data Layer (Polyglot Persistence)"
        L[(PostgreSQL<br>Relational DB)]
        M[(Redis<br>Cache & Queue)]
        N[(Neo4j<br>Graph DB)]
        O[(Qdrant<br>Vector DB)]
        P[(MongoDB<br>Document DB)]
    end

    subgraph "External Integrations"
        Q[OpenAI / Anthropic APIs]
        R[LangChain / MLflow]
        S[Firebase / Supabase]
    end

    subgraph "Monitoring & Observability"
        T[Autonomous Agents]
        U[Prometheus / Grafana]
        V[Alert Service<br>(Email/Slack)]
    end

    A --> D
    B --> D
    C --> D
    D --> E & F
    E & F --> G & H & I & J & K
    G & H & I --> L & M & N & O & P
    I --> Q & R & S
    J --> T
    K --> U & V
    T --> M & N

    style D fill:#f9f,stroke:#333,stroke-width:4px
    style I fill:#bbf,stroke:#333,stroke-width:4px
    style J fill:#bfb,stroke:#333,stroke-width:4px
```

---

## 🗄️ 2. Database Schema & ERD (ডেটাবেস সত্তা-সম্পর্ক চিত্র)

```mermaid
erDiagram
    USERS ||--o{ PROJECTS : creates
    USERS ||--o{ AGENTS : owns
    USERS ||--|| PROFILES : has
    USERS ||--o{ AUDIT_LOGS : generates
    
    PROJECTS ||--o{ AGENTS : contains
    PROJECTS ||--o{ DATASOURCES : uses
    PROJECTS ||--o{ DEPLOYMENTS : deploys
    
    AGENTS ||--o{ AGENT_RUNS : executes
    AGENTS ||--o{ AGENT_METRICS : produces
    AGENTS }o--|| AGENT_TEMPLATES : based_on
    
    AGENT_RUNS ||--o{ LOGS : generates
    AGENT_RUNS ||--o{ ARTIFACTS : creates
    
    DATASOURCES }o--|| CONNECTORS : uses
    
    DEPLOYMENTS ||--o| DEPLOYMENT_LOGS : logs

    USERS {
        uuid id PK
        string email UK
        string password_hash
        string role "USER|ADMIN"
        timestamp created_at
    }
    
    PROJECTS {
        uuid id PK
        string name
        text description
        uuid owner_id FK
        string status "ACTIVE|ARCHIVED"
    }
    
    AGENTS {
        uuid id PK
        string name
        string type "CODE|DATA|HEALER"
        json config
        uuid project_id FK
        uuid template_id FK
    }
    
    AGENT_RUNS {
        uuid id PK
        uuid agent_id FK
        string status "RUNNING|COMPLETED|FAILED"
        timestamp start_time
        timestamp end_time
        float cost
    }
```

---

## 🤖 3. Agent Orchestration & Execution Flow (এজেন্ট সঞ্চালনা সিকোয়েন্স)

```mermaid
sequenceDiagram
    participant U as User/Admin
    participant F as Frontend (Studio Client)
    participant B as Backend API
    participant O as Orchestrator
    participant A1 as Agent: Code Generator
    participant A2 as Agent: Data Analyzer
    participant A3 as Agent: Self-Healer
    participant DB as Databases
    
    U->>F: Create AI Task
    F->>B: POST /api/v1/agents/execute
    B->>O: Route Task
    O->>A1: Generate Code
    O->>A2: Analyze Data Requirements
    A1->>DB: Read Schema
    A2->>DB: Query Historical Data
    A1-->>O: Code Output
    A2-->>O: Data Insights
    O->>A3: Validate & Optimize
    A3-->>O: Optimized Result
    O-->>B: Final Response
    B-->>F: Display Result
    F-->>U: Show Output

    Note over O,A3: Self-Healing: If A1 fails,<br>A3 attempts recovery
    Note over O,DB: Vector DB (Qdrant) for<br>similar error lookup
```

---

## 🩺 4. Self-Healing Engine State Machine (সেলফ-হিলিং ইঞ্জিন স্টেট ডায়াগ্রাম)

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Error_Detected: Agent/System Failure
    Error_Detected --> Error_Analysis: Error Bus Event
    Error_Analysis --> Strategy_Lookup: Query Vector DB
    Strategy_Lookup --> Recovery_Attempt: Found Strategy
    Strategy_Lookup --> Alert_Admin: No Strategy
    
    Recovery_Attempt --> Recovery_Success: Healing Successful
    Recovery_Attempt --> Recovery_Failed: Healing Failed
    
    Recovery_Success --> Idle: Resume Normal Ops
    Recovery_Failed --> Escalation: Critical State
    Escalation --> Admin_Intervention: Notify via JIT OTP
    Admin_Intervention --> Idle: Manual Fix
    
    Alert_Admin --> Admin_Intervention: Human-in-Loop
    Recovery_Success --> Idle: Resume Monitoring
    
    note right of Error_Analysis
        Uses Central Error Bus
        & Autonomous Agents
    end note
    
    note right of Recovery_Attempt
        Circuit Breaker Pattern
        Exponential Backoff
    end note
```

---

## 🔐 5. Request Security & Threat Response (সিকিউরিটি ও অন-স্পট ট্র্যাকিং)

```mermaid
graph TD
    subgraph "Request Flow"
        R[Incoming Request]
        RL[Rate Limiter<br>Fail-Closed]
        Auth[Authentication<br>JWT + RBAC]
        JIT[JIT OTP Check<br>Sensitive Actions]
    end

    subgraph "Security Services"
        IP[IP Churn Detection<br>Redis-backed]
        EK[Encryption Service<br>AES-256-GCM]
        Audit[Audit Logger<br>Blockchain-verifiable]
    end

    subgraph "Threat Response"
        TD[Threat Detection<br>ML-based Anomaly]
        AL[Auto-Block IP]
        NT[Notify Admin<br>Email/Slack]
    end

    R --> RL
    RL -->|Pass| Auth
    Auth -->|Authorized| JIT
    JIT -->|Verified| IP
    IP --> EK
    EK --> Audit
    Audit --> TD
    TD -->|Suspicious| AL & NT
    AL -->|Blacklist| RL

    style JIT fill:#fbb,stroke:#f66,stroke-width:3px
    style TD fill:#fbb,stroke:#f66,stroke-width:3px
```

---

## 🚀 6. CI/CD Multi-Cloud Deployment Pipeline (ডিপ্লয়মেন্ট পাইপলাইন)

```mermaid
graph LR
    subgraph "Development"
        A[Local Dev<br>pnpm dev]
        B[Git Push<br>main/develop]
    end

    subgraph "CI/CD (GitHub Actions)"
        C[Run Tests<br>Backend/Frontend/Mobile]
        D[Build Docker Images<br>backend/Dockerfile.ci]
        E[Build Static Assets<br>apps/studio-client]
    end

    subgraph "Deployment Targets"
        F[GCP Cloud Run<br>Backend Service]
        G[Render Web Service<br>Backend Primary]
        H[Render Web Service<br>Backend Secondary]
        I[Vercel / Netlify<br>Frontend Hosting]
        J[Firebase Hosting<br>Admin Dashboard]
        K[Flutter Build<br>Mobile APK/IPA]
    end

    subgraph "Post-Deployment"
        L[Health Checks<br>/health]
        M[Autonomous Rollback<br>on Failure]
        N[Slack/Email Notification]
    end

    A --> B
    B --> C
    C --> D & E
    D --> F & G & H
    E --> I & J
    C --> K
    F & G & H --> L
    L -->|Failure| M
    M --> N

    style C fill:#f96,stroke:#333,stroke-width:2px
    style L fill:#6f9,stroke:#333,stroke-width:2px
    style M fill:#f66,stroke:#333,stroke-width:2px
```
