---
id: architecture-domains
subject: "SupremeAI Domains"
document_role: architecture
planning_authority: "Architecture Governance / Planning Circle"
canonical: true
status: active
evidence_state: verified
disposition: retain
last_verified: 2026-09-24
supersedes: []
superseded_by: []
target_scope: combined_ecosystem
---

# SupremeAI Domains

> **Layer 2 — the 9 system domains.** Domains are not plans — they are the
> stable buckets plans live inside. A plan belongs to exactly one domain;
> cross-cutting concerns live in Governance.

---

## The 9 domains

| # | Domain | Icon | Accent | Owns | # Plans |
|---|--------|------|--------|------|---------|
| 1 | [Security](../plans/security/security-guardian.md) | 🛡️ | `#dc2626` | trust boundary, secrets, audit | 1 |
| 2 | [Intelligence](../plans/intelligence/) | 🧠 | `#7c3aed` | provider abstraction, memory, knowledge | 3 |
| 3 | [Agents](../plans/agents/agent-orchestration.md) | 🤖 | `#0891b2` | agent roles, mesh, coding workflow | 1 |
| 4 | [MCP](../plans/mcp/mcp-architecture.md) | 🔌 | `#059669` | tool registry, federation, control tower | 1 |
| 5 | [Automation](../plans/automation/browser-automation.md) | 🌐 | `#ca8a04` | browser pools, remote control, RE | 1 |
| 6 | [Experience](../plans/experience/frontend-evolution.md) | 🖥️ | `#db2777` | frontend, dashboard, chat UX, auth | 1 |
| 7 | [Infrastructure](../plans/infrastructure/infrastructure-optimization.md) | ⚙️ | `#2563eb` | free-tier federation, config, CI/CD | 1 |
| 8 | [Observability](../plans/observability/observability.md) | 📈 | `#0d9488` | metrics, logs, traces, runtime verification | 1 |
| 9 | [Governance](../plans/governance/) | 🚦 | `#475569` | lifecycle, deployment safety, cleanup, quality | 3 |

---

## Why domains (not "families")

The legacy repo classified plans into 13 *content-derived families*
(`control-tower-mcp`, `free-tier-federation`, etc.) — useful for inventory, but
families overlap and a single plan can belong to several.

**Domains are disjoint.** A plan belongs to exactly one domain. This is what
makes the registry a clean table instead of a tag cloud. The mapping from the
13 legacy families to these 9 domains is in
[MIGRATION_MAP.md](../plans/MIGRATION_MAP.md).

---

## Domain responsibilities

### 🛡️ Security
The trust boundary. Secrets, auth, audit, threat model. Every other domain
depends on this being trustworthy. **Highest blast radius.**

### 🧠 Intelligence
The reasoning core: provider abstraction (P02), agent orchestration lives in
the Agents domain but agents are "intelligent", and the memory & knowledge
engine (P05). Three plans, one brain.

### 🤖 Agents
Agent roles (planner / executor / reviewer), the multi-agent mesh, the coding
workflow. Kept separate from Intelligence because the *role model* is a
distinct concern from *which LLM* or *how memory works*.

### 🔌 MCP
The Model Context Protocol control tower — the most mature domain (41 legacy
docs consolidated). Tool registry, federation, multi-tenant routing.

### 🌐 Automation
Browser pools, Supreme Teleport multi-device control, reverse-engineering.
Provider-neutral, free-tier aware, admin-gated.

### 🖥️ Experience
The user-facing surface: frontend, dashboard, chat, admin console, onboarding,
role-based auth. The only domain with `target_scope: user_project`.

### ⚙️ Infrastructure
Free-tier federation, 512 MB survival, zero-hardcode config, CI/CD pipeline.
What makes SupremeAI economically possible.

### 📈 Observability
Metrics, logs, traces, runtime verification. Turns claims into evidence — the
thing that lets plans reach Stable.

### 🚦 Governance
Plan lifecycle, deployment safety, testing & quality, codebase cleanup.
Cross-cutting concerns that don't belong to a single technical domain.

---

## Adding a new domain

Domains are **very** stable — adding one is a founder-level decision. Before
proposing a new domain, answer:

1. Does it have ≥2 plans that don't fit any existing domain?
2. Does it have a distinct owner circle?
3. Does it have its own verification surface?

If yes to all three, propose it via [IMPACT_MAP.md](../plans/IMPACT_MAP.md).
The bar is intentionally high — domain churn would re-introduce the jungle.
