# SUPREMEAI 2.0 — ULTIMATE GOD CONTROL CENTER
# Master Plan & Gap Analysis

> **Version:** 2.0.0  
> **Date:** 2026-06-21  
> **Status:** Master Plan — Awaiting Implementation  
> **Vision:** A single, omnipotent dashboard to control a limitless, multi-functional AI entity

---

## TABLE OF CONTENTS

1. [Vision Statement](#1-vision-statement)
2. [Architecture Philosophy](#2-architecture-philosophy)
3. [Full Dashboard Module Plan](#3-full-dashboard-module-plan)
4. [Current Dashboard Analysis](#4-current-dashboard-analysis)
5. [Gap Analysis: What We're Missing](#5-gap-analysis-what-were-missing)
6. [Implementation Roadmap](#6-implementation-roadmap)
7. [UI/UX Design Principles](#7-uiux-design-principles)
8. [Security & Access Control](#8-security--access-control)

---

## 1. VISION STATEMENT

> "One dashboard to rule them all. One interface to bind every AI capability, every cloud resource, every data stream, every model, every tool — into a single coherent consciousness that the operator can shape, direct, and evolve in real-time."

The SupremeAI God Control Center is not just an admin panel. It is the **neural cortex** of a living AI organism. From this single interface, an operator can:

- **Birth new AI capabilities** (skills, agents, workflows)
- **Shape the AI's personality** (rules, ethics, behavior patterns)
- **Monitor its health** across all cloud providers and services
- **Control its resources** (scale up/down, route traffic, balance load)
- **Audit its memory** (view, edit, purge conversation history)
- **Deploy its evolution** (push updates, A/B test, rollback)
- **Command its tools** (browsers, code execution, media generation)
- **Govern its access** (users, permissions, API keys, rate limits)

---

## 2. ARCHITECTURE PHILOSOPHY

### The "Neural Cortex" Metaphor

| Dashboard Section | Biological Analog | Purpose |
|------------------|-------------------|---------|
| **System Overview** | Brainstem / Vital Signs | Is the AI alive? |
| **Model Router** | Prefrontal Cortex | Decision-making, routing logic |
| **Skill Marketplace** | Motor Cortex | What actions can the AI perform? |
| **Memory Manager** | Hippocampus | Long-term memory, recall, forgetting |
| **Rules Engine** | Amygdala / Ethics Center | Emotional/ethical boundaries |
| **Cloud Orchestrator** | Autonomic Nervous System | Automatic resource scaling |
| **User Governance** | Social Cortex | Who can interact with the AI? |
| **Deployment Control** | DNA/RNA Replication | Evolution, mutation, adaptation |
| **Observability** | Sensory Cortex | What does the AI perceive? |
| **Security Center** | Immune System | Threat detection, defense |

### Design Principles

1. **Omniscience** — Every metric, every log, every state visible at a glance
2. **Omnipotence** — Every parameter, every rule, every resource controllable
3. **Real-time** — No refresh needed; WebSocket/SSE for live data
4. **Contextual** — AI-assisted dashboard that suggests actions based on patterns
5. **Auditable** — Every change logged, every action traceable
6. **Resilient** — Dashboard works even if parts of the backend fail

---

## 3. FULL DASHBOARD MODULE PLAN

### MODULE 0: COMMAND CENTER (Home / Landing)

**Purpose:** The "at-a-glance" view. Like a spaceship cockpit.

**Widgets:**
- **System Heartbeat** — Real-time pulse of all services (green/yellow/red)
- **Active Requests** — Live request counter with sparkline graph
- **Cost Burn Rate** — $/hour current spend + projected monthly
- **Model Load Distribution** — Pie chart of which AI providers are active
- **Recent Alerts** — Top 5 anomalies requiring attention
- **Quick Actions** — One-click buttons: "Emergency Stop", "Scale to Max", "Purge Cache", "Deploy Hotfix"
- **AI Assistant** — Built-in chat to ask "Why is latency high?" and get AI-generated diagnostics

**Layout:** Grid of cards, 3-column on desktop, collapsible on mobile

---

### MODULE 1: AI MODEL CONTROL CENTER

**Purpose:** Direct control over every AI model and provider.

**Sub-modules:**

#### 1.1 Model Router Panel
- Visual flow diagram: Request → Intent Classifier → Provider Selector → Model
- Real-time routing decisions with explanations ("Why did this go to GPT-4?")
- Override switches: Force specific model for next N requests
- A/B testing setup: Route 50% to Model A, 50% to Model B
- Cost vs Quality slider: "Prefer cheaper" ↔ "Prefer best quality"

#### 1.2 Provider Management
- Status of all providers: OpenRouter, Gemini, Groq, DeepSeek, NVIDIA, Ollama (local)
- API key health: Valid / Invalid / Rate-limited / Expired
- Latency heatmap per provider (last 1h, 24h, 7d)
- Failover configuration: "If Provider A fails, try B, then C"
- Custom provider addition: Add new OpenAI-compatible endpoints

#### 1.3 Model Tuning
- Temperature, top_p, max_tokens sliders per model
- System prompt editor with version history
- Fine-tuning job management (upload data, start job, monitor progress)
- Model comparison tool: Same prompt, different models, side-by-side results

#### 1.4 Prompt Engineering Lab
- Prompt template library (save, categorize, search)
- Prompt testing ground: Test against multiple models simultaneously
- Prompt optimization: AI-suggested improvements to your prompts
- Prompt version control: Git-like history for every prompt

---

### MODULE 2: SKILL & AGENT ORCHESTRATION

**Purpose:** Manage what the AI can DO — skills, tools, agents, workflows.

**Sub-modules:**

#### 2.1 Skill Marketplace (Enhanced)
- **Current:** Basic list with install button
- **Enhanced:** 
  - Visual skill cards with icons, ratings, usage stats
  - Skill dependency graph (Skill A requires Skills B, C)
  - Skill performance metrics: Success rate, avg execution time, error rate
  - Skill sandbox: Test a skill without installing
  - Custom skill builder: Visual no-code builder + code editor
  - Skill versioning: Install v1.2, rollback to v1.1
  - Community skills: Browse, rate, submit skills

#### 2.2 Agent Builder
- **NEW MODULE**
- Visual workflow designer (drag-and-drop nodes)
- Agent types: ReAct, Plan-and-Execute, Multi-Agent Swarm
- Tool assignment: Which skills can this agent use?
- Memory configuration: Short-term, long-term, vector DB
- Human-in-the-loop: Pause for approval at critical steps
- Agent testing: Simulate conversations, debug step-by-step

#### 2.3 Tool Configuration
- Browser automation: Configure headless Chrome, proxy settings, user agents
- Code execution: Docker sandbox settings, language runtimes, timeout limits
- Media generation: Image/Video/Voice model selection, style presets
- Data connectors: Supabase, Firestore, Redis, Pinecone connection managers
- API integrations: Add custom REST/GraphQL endpoints as tools

#### 2.4 Workflow Automation
- **NEW MODULE**
- Trigger-based workflows: "When X happens, do Y"
- Scheduled tasks: Cron-like scheduler for recurring AI tasks
- Pipeline builder: Chain multiple skills into a workflow
- Workflow execution logs: Step-by-step trace with timings
- Workflow templates: Pre-built workflows for common use cases

---

### MODULE 3: MEMORY & KNOWLEDGE MANAGEMENT

**Purpose:** Control what the AI REMEMBERS and KNOWS.

**Sub-modules:**

#### 3.1 Conversation Memory
- **Current:** Basic checkpoint list
- **Enhanced:**
  - Full conversation history with search, filter, export
  - Conversation analytics: Topics discussed, sentiment over time
  - Memory editing: Edit, delete, or summarize past conversations
  - Memory importance scoring: Auto-flag important conversations
  - Cross-session memory: "The user mentioned their dog 'Buddy' 3 sessions ago"

#### 3.2 Knowledge Base (RAG)
- **NEW MODULE**
- Document upload: PDF, DOCX, TXT, Markdown, URLs
- Chunking strategy configuration: Size, overlap, semantic vs fixed
- Embedding model selection: OpenAI, HuggingFace, local
- Vector DB management: Pinecone, Supabase pgvector, Chroma
- Retrieval testing: "Given this query, what documents would be retrieved?"
- Knowledge graph visualization: Connected concepts and entities

#### 3.3 Memory Checkpoints (Enhanced)
- **Current:** Simple list with delete
- **Enhanced:**
  - Checkpoint timeline visualization
  - Compare two checkpoints side-by-side
  - Restore from checkpoint with merge options
  - Auto-checkpoint rules: "Checkpoint every 10 messages" or "Before dangerous operations"
  - Checkpoint tagging: "Stable", "Experimental", "Rollback Point"

#### 3.4 Entity & Preference Store
- **NEW MODULE**
- User profile builder: Names, preferences, facts learned about users
- Entity extraction: People, places, organizations mentioned
- Preference learning: "User prefers concise answers", "User likes code examples"
- Privacy controls: "Forget everything about user X", "Anonymize all data"

---

### MODULE 4: CONSTITUTIONAL RULES & ETHICS ENGINE

**Purpose:** Define the AI's MORAL COMPASS and BOUNDARIES.

**Sub-modules:**

#### 4.1 Rules Editor (Enhanced)
- **Current:** JSON text area
- **Enhanced:**
  - Visual rule builder: If-Then-Else with dropdowns
  - Rule categories: Safety, Privacy, Quality, Brand Voice, Compliance
  - Rule severity: Block / Warn / Log / Allow
  - Rule testing: "If I say X, what rules trigger?"
  - Rule conflict detection: "Rule A contradicts Rule B"
  - Rule effectiveness: How often did this rule trigger? Was it correct?

#### 4.2 Content Filtering
- **NEW MODULE**
- Toxicity detection thresholds: Hate, harassment, self-harm, sexual, violent
- PII detection: Auto-redact emails, phone numbers, SSNs
- Topic blocking: "Never discuss politics, religion, or medical advice"
- Custom filter builder: Regex patterns, keyword lists, semantic filters
- Filter testing: Test messages against filters before deployment

#### 4.3 Bias & Fairness Monitor
- **NEW MODULE**
- Demographic parity analysis across user groups
- Response sentiment analysis by topic
- Bias alert: "Responses to Group A are 30% more negative"
- Fairness metrics dashboard
- Mitigation suggestions: "Adjust prompt to be more neutral"

#### 4.4 Audit Trail
- **NEW MODULE**
- Every rule change logged with who, when, why
- Before/after diff view
- Rollback capability: "Revert to rules from 3 days ago"
- Compliance reporting: Export for regulatory audits

---

### MODULE 5: CLOUD & INFRASTRUCTURE ORCHESTRATION

**Purpose:** Control the PHYSICAL and VIRTUAL infrastructure.

**Sub-modules:**

#### 5.1 Multi-Cloud Control Panel
- **Current:** Basic GCP health stats
- **Enhanced:**
  - Visual topology map: GCP, AWS, Azure, Cloudflare, Supabase
  - Service status per region: Green/Yellow/Red
  - Cost breakdown by provider, service, region
  - Resource utilization: CPU, Memory, Disk, Network
  - Auto-scaling rules: "Scale up if CPU > 70% for 5 min"
  - Disaster recovery: Failover to secondary region with one click

#### 5.2 Kubernetes / Container Management
- **NEW MODULE**
- Pod status visualization
- Deployment rollout control: Rolling update, canary, blue-green
- Resource limits: Set CPU/memory per service
- Log streaming: Real-time logs from any container
- Shell access: Exec into running containers for debugging

#### 5.3 Database Management
- **NEW MODULE**
- Supabase: Table browser, query runner, row editor
- Redis: Key browser, TTL viewer, flush options
- Pinecone: Index management, vector search testing
- Firestore: Collection browser, document editor
- Query performance: Slow query log, index suggestions

#### 5.4 CDN & Edge Configuration
- **NEW MODULE**
- Cloudflare: Cache rules, WAF settings, rate limits
- Firebase Hosting: Deployment history, rollback, preview channels
- Image optimization: Automatic WebP/AVIF conversion settings
- Geographic routing: Route users to nearest datacenter

---

### MODULE 6: USER & ACCESS GOVERNANCE

**Purpose:** Control WHO can use the AI and WHAT they can do.

**Sub-modules:**

#### 6.1 User Management (Enhanced)
- **Current:** Basic username/role/permissions list
- **Enhanced:**
  - User directory with search, filter, bulk actions
  - User activity timeline: Last login, requests made, skills used
  - User segments: Power users, new users, churned users
  - Impersonation: "Login as user X" for support debugging
  - User onboarding flow builder

#### 6.2 Role-Based Access Control (RBAC)
- **NEW MODULE**
- Role builder: Create custom roles with granular permissions
  - Permission examples: `skill:install`, `memory:read:all`, `model:override`, `deploy:production`
  - Resource-level permissions: "Can only access memory for Project X"
- Permission matrix: Visual grid of who can do what
- API key management: Generate, revoke, scope-limited keys
- OAuth/SAML integration: SSO for enterprise users

#### 6.3 Rate Limiting & Quotas
- **NEW MODULE**
- Per-user rate limits: Requests/min, tokens/day, cost/month
- Per-API-key quotas
- Burst allowance configuration
- Quota usage visualization: Progress bars, alerts at 80%
- Automatic throttling: Gradual slowdown before hard limit

#### 6.4 Audit & Compliance
- **NEW MODULE**
- Complete audit log: Every API call, every data access
- Log search: Full-text search across all logs
- Anomaly detection: "User X made 10x more requests than usual"
- Compliance reports: GDPR data export, CCPA deletion requests
- Data retention policies: Auto-purge old data

---

### MODULE 7: OBSERVABILITY & INTELLIGENCE

**Purpose:** Understand what the AI is DOING and WHY.

**Sub-modules:**

#### 7.1 Real-Time Metrics Dashboard
- **NEW MODULE**
- Request volume: QPS, latency percentiles (p50, p95, p99)
- Error rate: 4xx, 5xx breakdown by endpoint
- Model performance: Accuracy, hallucination rate, user satisfaction
- Cost tracking: $/request, $/user, $/day, projected monthly bill
- Custom dashboards: Build your own with drag-and-drop widgets

#### 7.2 Distributed Tracing
- **NEW MODULE**
- Jaeger/Zipkin-style trace visualization
- Request journey: Frontend → API → Model → Tool → Response
- Bottleneck identification: "This request spent 80% time in ChromaDB"
- Error trace: Full stack trace across services

#### 7.3 Alerting & Incidents
- **NEW MODULE**
- Alert rules: "If error rate > 5% for 5 min, alert"
- Notification channels: Email, Slack, Discord, PagerDuty, SMS
- Incident management: Create incident, assign, track resolution
- Runbook integration: "Alert triggered → show relevant runbook"
- Post-mortem builder: Timeline, root cause, action items

#### 7.4 AI-Powered Insights
- **NEW MODULE**
- "Why did latency spike at 3 PM?" → AI analyzes logs and suggests cause
- "What are users asking about most?" → Topic clustering
- "Which skills fail most often?" → Failure pattern detection
- "Predict next week's cost" → Time-series forecasting
- "Suggest optimization" → AI-recommended infrastructure changes

---

### MODULE 8: DEPLOYMENT & EVOLUTION CONTROL

**Purpose:** Manage the AI's EVOLUTION — updates, experiments, rollbacks.

**Sub-modules:**

#### 8.1 CI/CD Pipeline Visualizer
- **NEW MODULE**
- GitHub Actions pipeline visualization
- Real-time build status per commit
- Deployment history: What was deployed when, by whom
- One-click rollback: "Revert to commit abc123"
- Deployment approvals: Require approval before production deploy

#### 8.2 Feature Flags & Experiments
- **NEW MODULE**
- Feature flag dashboard: Toggle features on/off
- A/B test setup: "Show new UI to 10% of users"
- Experiment results: Statistical significance, conversion rates
- Gradual rollout: 1% → 5% → 25% → 100%
- Kill switch: "Disable feature immediately if issues detected"

#### 8.3 Model Versioning & Canary
- **NEW MODULE**
- Model version registry: v1.0, v1.1, v2.0-beta
- Canary deployment: Route 5% traffic to new model version
- Shadow mode: Run new model in parallel, compare outputs, don't serve
- Model performance comparison: A/B test results for model versions
- Automatic rollback: "If error rate > threshold, auto-revert"

#### 8.4 Release Notes & Changelog
- **NEW MODULE**
- Auto-generated changelog from commits
- Release note editor with markdown
- User-facing vs internal changes separation
- Scheduled releases: "Deploy this change next Tuesday at 2 AM"

---

### MODULE 9: SECURITY & THREAT CENTER

**Purpose:** Protect the AI from ATTACKS and MISUSE.

**Sub-modules:**

#### 9.1 Threat Detection
- **NEW MODULE**
- Prompt injection detection: "Ignore previous instructions" alerts
- Jailbreak attempts: Log and block adversarial prompts
- Data exfiltration monitoring: "Is the AI leaking training data?"
- Anomalous usage patterns: "User X is scraping the API"
- Threat intelligence feed: Known attack patterns, auto-block

#### 9.2 Vulnerability Management
- **NEW MODULE**
- Dependency vulnerability scanner: Snyk-like integration
- Secret detection: "API key committed to repo"
- Penetration test results: Track findings, remediation status
- Security scorecard: Overall security grade (A-F)

#### 9.3 Incident Response
- **NEW MODULE**
- Incident playbooks: "If prompt injection detected, do X, Y, Z"
- Automated response: Auto-block IP, revoke key, alert team
- Forensics: Preserve evidence, reconstruct attack timeline
- Post-incident review: Root cause, lessons learned

#### 9.4 Compliance & Privacy
- **NEW MODULE**
- GDPR: Data subject access requests, right to be forgotten
- CCPA: Consumer privacy requests
- HIPAA: Healthcare data handling (if applicable)
- SOC 2: Security controls evidence collection
- Custom compliance frameworks

---

### MODULE 10: SETTINGS & SYSTEM CONFIGURATION

**Purpose:** Global system settings and maintenance.

**Sub-modules:**

#### 10.1 Environment Configuration
- **Current:** Basic env var editor
- **Enhanced:**
  - Environment variable manager: Add, edit, delete, validate
  - Secret management: Integration with GCP Secret Manager, AWS Secrets Manager
  - Config versioning: "This was the config on June 1st"
  - Config diff: Compare staging vs production config
  - Config validation: "This config is missing required variable X"

#### 10.2 Backup & Restore
- **NEW MODULE**
- Automated backups: Database, memory, knowledge base, rules
- Backup scheduling: Daily, weekly, custom cron
- Point-in-time recovery: "Restore to exactly 3:42 PM yesterday"
- Cross-region backup replication
- Backup integrity testing: "Verify backup is restorable"

#### 10.3 System Maintenance
- **NEW MODULE**
- Cache management: Flush Redis, CDN, browser cache
- Log rotation: Configure retention, archive old logs
- Database maintenance: Vacuum, reindex, optimize
- Health check customization: Add custom health checks
- Maintenance mode: "Site under maintenance" page with countdown

#### 10.4 Integrations Hub
- **NEW MODULE**
- Third-party integrations: Slack, Discord, Telegram, email
- Webhook management: Incoming/outgoing webhooks
- API key management for external services
- Custom integration builder: No-code connector builder

---

## 4. CURRENT DASHBOARD ANALYSIS

### What We Currently Have (from `AdminConsole.tsx`):

| Feature | Status | Quality |
|---------|--------|---------|
| **Project Status Overview** | ✅ Basic | 6 static cards with hardcoded data |
| **Sandbox Terminal** | ✅ Basic | Simple chat interface for admin |
| **Constitutional Rules Editor** | ✅ Basic | JSON text area only |
| **GCP Health Stats** | ✅ Basic | 3 status fields |
| **Cloud Distribution Stats** | ✅ Basic | Request count, provider count |
| **Skill Marketplace** | ✅ Basic | List with install button |
| **Memory Checkpoints** | ✅ Basic | List with delete button |
| **Admin Login with TOTP** | ✅ Working | Password + Google Authenticator |
| **Sub-tabs** | ✅ Present | sandbox, logs, costs, health, users, config, project_status |
| **Live Logs (SSE)** | ✅ Present | EventSource for real-time logs |
| **Cost Report** | ✅ Present | Fetches from `/admin-api/costs` |
| **Health Map** | ✅ Present | Fetches from `/admin-api/health-map` |
| **User Management** | ✅ Basic | Add/delete users |
| **Environment Config** | ✅ Basic | Key-value editor |
| **Deploy Trigger** | ✅ Present | POST to `/admin-api/deploy` |

### Current Architecture:
- **Single file:** `AdminConsole.tsx` (39KB — already very large)
- **No component splitting:** Everything in one file
- **No state management:** Local useState only
- **No data caching:** Refetches on every tab switch
- **Limited real-time:** Only logs use SSE
- **No visualization:** No charts, graphs, or diagrams
- **Mobile-unfriendly:** Desktop-only layout

---

## 5. GAP ANALYSIS: WHAT WE'RE MISSING

### Critical Gaps (Must-Have for "God Control Center")

| # | Missing Feature | Impact | Priority |
|---|----------------|--------|----------|
| 1 | **Real-time metrics & charts** | Can't see system health visually | 🔴 P0 |
| 2 | **Model router visualization** | Can't understand or control routing | 🔴 P0 |
| 3 | **Agent/workflow builder** | Can't create complex AI behaviors | 🔴 P0 |
| 4 | **Knowledge base (RAG) management** | Can't control what AI knows | 🔴 P0 |
| 5 | **Visual rule builder** | JSON editing is error-prone | 🔴 P0 |
| 6 | **Distributed tracing** | Can't debug failures across services | 🟡 P1 |
| 7 | **Alerting & incidents** | Find out about problems too late | 🟡 P1 |
| 8 | **Feature flags & A/B testing** | Can't safely roll out changes | 🟡 P1 |
| 9 | **RBAC with granular permissions** | All admins have same power = risky | 🟡 P1 |
| 10 | **Threat detection** | AI vulnerable to attacks | 🟡 P1 |
| 11 | **AI-powered insights** | Dashboard doesn't help diagnose | 🟢 P2 |
| 12 | **Multi-cloud topology map** | Can't see full infrastructure | 🟢 P2 |
| 13 | **Database management UI** | Need CLI for DB operations | 🟢 P2 |
| 14 | **Backup & restore UI** | No self-service recovery | 🟢 P2 |
| 15 | **Integration hub** | Every integration requires code | 🟢 P2 |

### Technical Debt Gaps

| # | Issue | Current State | Target |
|---|-------|--------------|--------|
| 1 | **File size** | `AdminConsole.tsx` = 39KB | Split into ~20 components |
| 2 | **State management** | useState only | Redux Toolkit or Zustand |
| 3 | **Data fetching** | Inline fetch everywhere | React Query (TanStack Query) |
| 4 | **Charts/visualization** | None | Recharts + D3 for custom |
| 5 | **Real-time updates** | Only logs use SSE | WebSocket for all modules |
| 6 | **Mobile responsive** | Desktop only | Fully responsive |
| 7 | **Dark/light mode** | Dark only | Toggle + system preference |
| 8 | **Accessibility** | Not accessible | WCAG 2.1 AA compliant |

---

## 6. IMPLEMENTATION ROADMAP

### Phase 1: Foundation (Week 1-2)
- [ ] Refactor `AdminConsole.tsx` into component modules
- [ ] Set up state management (Zustand or Redux Toolkit)
- [ ] Set up React Query for data fetching
- [ ] Add Recharts for basic charts
- [ ] Create shared component library (cards, tables, forms, modals)

### Phase 2: Core Modules (Week 3-4)
- [ ] **Module 0:** Command Center with real-time widgets
- [ ] **Module 1:** Model Router visualization
- [ ] **Module 2:** Enhanced Skill Marketplace
- [ ] **Module 3:** Conversation Memory browser

### Phase 3: Power Modules (Week 5-6)
- [ ] **Module 4:** Visual Rules Builder
- [ ] **Module 5:** Cloud Orchestrator (enhanced GCP + add others)
- [ ] **Module 6:** Enhanced User Management + RBAC
- [ ] **Module 7:** Basic Observability (metrics, logs)

### Phase 4: Intelligence (Week 7-8)
- [ ] **Module 7:** AI-powered insights
- [ ] **Module 8:** CI/CD Pipeline visualizer
- [ ] **Module 9:** Basic Threat Detection
- [ ] **Module 2:** Agent Builder (visual workflow)

### Phase 5: Polish (Week 9-10)
- [ ] Mobile responsiveness
- [ ] Dark/light mode
- [ ] Accessibility audit
- [ ] Performance optimization
- [ ] Documentation

---

## 7. UI/UX DESIGN PRINCIPLES

### Visual Language
- **Theme:** "Cyberpunk meets Enterprise" — Dark mode primary, neon accents
- **Color palette:**
  - Background: `#0a0e1a` (deep space)
  - Surface: `#111827` (panel)
  - Primary accent: `#00f3ff` (cyan — information)
  - Success: `#10b981` (emerald)
  - Warning: `#f59e0b` (amber)
  - Danger: `#ef4444` (red)
  - God mode: `#bc13fe` (purple — admin-only actions)
- **Typography:** JetBrains Mono for data, Inter for UI text
- **Icons:** Lucide React (consistent, lightweight)

### Layout Patterns
- **Sidebar navigation:** Collapsible, icon + label, grouped by module
- **Breadcrumb:** Always show current location
- **Command palette:** Cmd+K to search anything (inspired by VS Code)
- **Contextual help:** `?` icon on every panel explaining what it does
- **Keyboard shortcuts:** Full shortcut map accessible via `?`

### Interaction Patterns
- **Confirm destructive actions:** "Are you sure?" with type-to-confirm for dangerous ops
- **Progressive disclosure:** Advanced options hidden behind "Advanced" toggle
- **Real-time feedback:** Toast notifications for all actions
- **Skeleton loading:** Never show blank screens
- **Error boundaries:** Graceful degradation if a module crashes

---

## 8. SECURITY & ACCESS CONTROL

### Authentication
- **Primary:** Password + TOTP (already implemented ✅)
- **Enhanced:** Hardware key (WebAuthn/FIDO2) support
- **SSO:** OAuth2/SAML for enterprise
- **Session:** Short-lived JWT with refresh token rotation

### Authorization Matrix

| Role | System View | Model Control | Skill Install | Rules Edit | Deploy Prod | User Admin | Cost View |
|------|------------|---------------|---------------|------------|-------------|------------|-----------|
| **Viewer** | ✅ Read | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Operator** | ✅ Read | ✅ Override | ✅ | ❌ | ❌ | ❌ | ✅ Own |
| **Developer** | ✅ Read/Write | ✅ Full | ✅ Full | ✅ Test | ✅ Staging | ❌ | ✅ Team |
| **Admin** | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| **God** | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Full + Audit |

### Audit Requirements
- Every login/logout logged
- Every config change logged with before/after
- Every deployment logged with approver
- Every rule change logged with justification
- All logs immutable (write-once, append-only)
- Logs retained for 1 year minimum

---

## APPENDIX: RECOMMENDED TECH STACK

| Layer | Current | Recommended |
|-------|---------|-------------|
| **Framework** | React 19 | React 19 + Next.js 14 (App Router) |
| **State** | useState | Zustand + React Query |
| **Styling** | Tailwind | Tailwind + shadcn/ui components |
| **Charts** | None | Recharts + Tremor |
| **Tables** | None | TanStack Table |
| **Forms** | Manual | React Hook Form + Zod |
| **Real-time** | EventSource | Socket.io or native WebSocket |
| **Maps/Diagrams** | None | React Flow (for workflows) |
| **Icons** | Unknown | Lucide React |
| **Testing** | Vitest | Vitest + Playwright (E2E) |

---

*End of Master Plan*
