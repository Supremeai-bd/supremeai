# 🏷️ SupremeAI — Master Federation Group Taxonomy Specification

> **Canonical SSOT for Issue & PR Group Naming, Repository Routing, and Semantic Classification**  
> **Status:** Canonical Standard (Issue #180, Roadmap Phase 2)  
> **Enforcement Entrypoint:** `scripts/agents/group_taxonomy.py`

---

## 1. The Standard Title Contract

Every issue, branch, and pull request created across the SupremeAI Federation must use the standardized format:

```text
<type>(<group>): <short-description>
```

### Examples:
- `feat(browser): add anti-detect stealth mode to playwright engine`
- `feat(command): telegram webhook handler for remote superadmin approvals`
- `feat(skills): add duckduckgo deep-research search adapter`
- `fix(infra): consolidate actions to eliminate runner queue deadlock`
- `sec(security): enforce zero-leak master vault token discipline`
- `feat(agents): [Step-1] Instruction Builder contract validation`

---

## 2. Master Taxonomy: 27 Canonical Groups in 4 Categories

### Category 1: Repository-Direct Domain Groups (12 Repositories)
These groups map directly 1:1 to an independent specialized satellite repository in the `Supremeai-bd` organization:

| Group Name | Target Repository | Scope & Domain Responsibility |
|---|---|---|
| **`agents`** | `Supremeai-bd/supremeai-agents` | Continuous execution loop, role contracts, prompt templates, agent lifecycle |
| **`browser`** | `Supremeai-bd/supremeai-browser` | Headless Chromium, stealth automation, DOM navigation, web scrapers |
| **`command`** | `Supremeai-bd/supremeai-command` | Omnichannel remote control (Telegram, Webhooks, Mobile), human-in-the-loop triggers |
| **`skills`** | `Supremeai-bd/supremeai-skills` | Modular agent skills, MCP tool adapters, reusable action plugins |
| **`vscode`** | `Supremeai-bd/supremeai-vscode` | VS Code extension, IDE sidecars, editor widget integrations |
| **`api`** | `Supremeai-bd/supremeai-api` | Stable API gateway, OpenAPI contracts, public client SDKs, consumer docs |
| **`studio`** | `Supremeai-bd/supremeai-studio` | Frontend web UI, design system, interactive dashboards, control planes |
| **`core`** | `Supremeai-bd/supremeai-core` | Proprietary intelligence engine, multi-agent debate consensus, decision state machines |
| **`security`** | `Supremeai-bd/supremeai-security` | Vault (Infisical), RBAC policies, secret rotation, boundary security guards |
| **`infra`** | `Supremeai-bd/supremeai-infra` | Cloud deployment (Render, Cloudflare), Docker setups, CI/CD Actions infrastructure |
| **`memory`** | `Supremeai-bd/supremeai-memory` | Vector DB, AI semantic memory, long-term retention policies, Supabase sync |
| **`gateway`** | `Supremeai-bd/supremeai-open` | Public gateway ("Elephant's Teeth"), external contributor PRs, public issue triage |

---

### Category 2: AI Engine, Prompts & Intelligence Groups
Cross-cutting intelligence tasks governing models, prompts, evaluation, and datasets:

| Group Name | Scope & Domain Responsibility |
|---|---|
| **`prompts`** | System prompts, meta-prompting architectures, prompt versioning and tuning |
| **`evals`** | Ground-truth AI evaluations, SWE-bench benchmarks, automated response scoring |
| **`llm-routing`** | Multi-model load balancing, fallback chains (OpenAI, Claude, Gemini, Local models) |
| **`datasets`** | Synthetic data generation, RLHF feedback datasets, training pipelines |

---

### Category 3: System Quality, Resilience & Performance Groups
Operational performance, cost controls, and self-healing:

| Group Name | Scope & Domain Responsibility |
|---|---|
| **`reliability`** | Watchdogs, heartbeat monitoring, self-healing circuits, crash recovery |
| **`perf`** | Token consumption optimization, latency reduction, throughput enhancement |
| **`cost`** | LLM cost control, semantic caching policies, budget guards |
| **`telemetry`** | Live execution logging, distributed tracing, metrics dashboards |
| **`quality`** | General QA, static analysis, code coverage, test integrity |

---

### Category 4: Operations, Governance & Business Groups
Policies, releases, documentation, and customer management:

| Group Name | Scope & Domain Responsibility |
|---|---|
| **`governance`** | Superadmin decisions, constitutional rules, authority boundaries, policies |
| **`bridge`** | Public-to-private bridge intake, air-gap work order processing, patch delivery |
| **`release`** | Versioning, staging closeouts, Capability Harvest, release trains |
| **`docs`** | Documentation, guides, architecture diagrams, API references, changelogs |
| **`billing`** | Customer subscription tiers, quota enforcement, tenant isolation |
| **`triage`** | Incoming raw ideas, backlog organization, bug triage |

---

## 3. Automated Bridge Routing Contract

When an external contributor or autonomous agent submits a task or patch to `Supremeai-bd/supremeai-open`:
1. The Bridge Router extracts the group from the title regex `r'^[a-z]+\(([^)]+)\):'`.
2. If the group belongs to **Category 1 (Repository-Direct)**, the Bridge Router automatically resolves `resolve_group_repository(group)` and forwards the patch directly to that satellite repository.
3. If the group belongs to Categories 2–4, the task is routed according to the declared `Touching files` in the task envelope.

---

## 4. CLI Usage

The group taxonomy can be inspected and validated via CLI:

```bash
# List all canonical groups and target repositories
python scripts/agents/group_taxonomy.py list

# Validate a specific group name
python scripts/agents/group_taxonomy.py validate browser
# Output: [OK] canonical primary group: browser [repository-direct] -> target repo: Supremeai-bd/supremeai-browser

# Look up active issues in a specific group before creating a new issue
python scripts/agents/group_taxonomy.py lookup browser
```
