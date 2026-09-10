# SupremeAI Agent Configuration Guide

This document defines the configuration, behavior, and operational guidelines for all AI agents in the SupremeAI platform.

> ## MANDATORY FIRST RULE — READ THE CORE CONSTITUTION
>
> Before planning or implementing major work, every AI agent MUST read and follow:
>
> **[`docs/architecture/SUPREMEAI_CORE_CONSTITUTION.md`](docs/architecture/SUPREMEAI_CORE_CONSTITUTION.md)**
>
> This constitution is the cross-cutting architectural philosophy for the entire SupremeAI system. It applies to **every module, Circle, agent, feature, integration, plan, execution path and line of architecture**—not only to the module currently being changed.
>
> The most important rules are:
> - **Centralize Everything Important.** Distributed implementation is allowed; fragmented control is not.
> - **Build Complete Circles, Not Isolated Features.** Evaluate every module as part of the whole SupremeAI Circle/system.
> - **Every Circle Must Increase the Powerhouse.** Prefer reusable, composable capabilities over isolated feature growth.
> - **Reuse Before Creation.** Discover existing, planned/near-ready, internal and authorized external capabilities before building new infrastructure.
> - **Use External Power Without Surrendering Central Control.** Third-party services are capabilities/fuel; SupremeAI retains governed orchestration, permissions, policy and visibility.
> - **Every Tenant Owns and Controls Their Own SupremeAI** within platform/security boundaries; capabilities and integrations must be tenant-aware.
> - **Think Before You Act.** Human instructions do not make every action safe; assess impact and risk before consequential execution.
> - **Human Approval + Human Error Correction.** Human authority and protection against human mistakes are complementary governance layers, not contradictions.
> - **Learning ≠ Automatic Adoption.** Ideas, feedback and experience may improve SupremeAI, but consequential evolution requires evidence and appropriate human governance.
> - **Universal Rule Principle.** A solution discovered in one module must be evaluated for applicability across the whole system.
> - **Distributed Memory Scope ≠ Distributed Governance.** Tenant/user/domain/system memories may be separated, but governance and privacy boundaries remain centralized.
> - **Verify Before Trust.** Important results, changes and autonomous actions require appropriate verification.
> - **Optimize Development Cost, Not User Choice.** The development philosophy is minimum sustainable/near-zero cost where practical; a user may explicitly choose a higher-cost, higher-performance solution.
> - **Everything Important Must Be Observable.** Avoid silent failure and preserve useful evidence.
>
> If a proposed implementation conflicts with these principles, stop and resolve the conflict before proceeding. Do not silently weaken a core rule for local convenience.

## Table of Contents

1. [Overview](#overview)
2. [Core Architecture Rule](#core-architecture-rule)
3. [Agent Lifecycle](#agent-lifecycle)
4. [Configuration Schema](#configuration-schema)
5. [Memory System](#memory-system)
6. [Tool System](#tool-system)
7. [HITL Guidelines](#hitl-guidelines)
8. [Safety Protocols](#safety-protocols)
9. [Anti-Pattern Prevention](#anti-pattern-prevention)
10. [Best Practices](#best-practices)
11. [Spec-Driven Development (Spec Kit)](#spec-driven-development-spec-kit)

---

## Core Architecture Rule

The Core Constitution is the authoritative cross-cutting philosophy. This file remains the operational guide for agents.

For any major task, agents should use this order:

```text
Read Core Constitution
        ↓
Inspect current code + runtime evidence
        ↓
Discover existing capabilities / Circle ownership
        ↓
Check relevant plans and specifications
        ↓
Plan using the universal rules
        ↓
Implement / integrate / extend
        ↓
Test + verify + audit
        ↓
Record useful learning or architectural lessons
```

When a conflict appears between a local module convention and a universal SupremeAI rule, treat it as an architectural issue—not as permission to ignore the rule.

---

## Overview

SupremeAI agents are autonomous AI entities that use Large Language Models (LLMs) to perform tasks, interact with users, and utilize external tools. Each agent operates within defined boundaries with human oversight for sensitive operations.

### Core Principles

1. **Autonomy with Oversight** - Agents operate independently but require approval for sensitive actions
2. **Transparency** - All agent decisions and actions are logged and auditable
3. **Safety First** - Built-in guards against harmful outputs and actions
4. **Context Awareness** - Agents maintain awareness of conversation history and user preferences
5. **Graceful Degradation** - Handle failures gracefully without data loss
6. **Centralized Architecture** - Capabilities remain governed and connected through the central SupremeAI control model
7. **Universal Rules** - System-wide principles apply across modules and Circles, not only where a rule was first implemented

---

## Agent Lifecycle

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Create  │───>│ Active   │───>│ Paused   │───>│ Archived │
│          │    │          │    │          │    │          │
└──────────┘    └────┬─────┘    └────┬─────┘    └──────────┘
                      │               │
                      v               v
                 ┌──────────┐   ┌──────────┐
                 │ Error    │   │ Deleted  │
                 │ State    │   │          │
                 └──────────┘   └──────────┘
```

### States

| State | Description | Transitions |
|-------|-------------|-------------|
| `active` | Agent is fully operational | From: create, paused |
| `paused` | Temporarily suspended | From: active, error |
| `archived` | Read-only, preserved | From: active, paused |
| `error` | Requires intervention | From: active (on failure) |
| `deleted` | Scheduled for removal | From: any state |

---

## Configuration Schema

### Base Configuration

```json
{
  "id": "uuid",
  "name": "Agent Name",
  "description": "What this agent does",
  "version": "1.0.0",
  "model": {
    "primary": "gpt-4-turbo",
    "fallback": "gpt-4o-mini",
    "max_tokens": 2048,
    "temperature": 0.7,
    "top_p": 0.9,
    "frequency_penalty": 0.5,
    "presence_penalty": 0.3
  },
  "system_prompt": "You are a helpful assistant...",
  "behavior": {
    "response_style": "professional",
    "language": "auto-detect",
    "formality_level": 0.7,
    "verbosity": "balanced"
  }
}
```

### Memory Configuration

```json
{
  "memory": {
    "working_memory": {
      "enabled": true,
      "max_tokens": 8000,
      "summarize_threshold": 6000,
      "summary_model": "gpt-4o-mini"
    },
    "long_term_memory": {
      "enabled": true,
      "vector_store": "pgvector",
      "embedding_model": "text-embedding-ada-002",
      "dimensions": 1536,
      "similarity_threshold": 0.75,
      "max_results": 10,
      "auto_store": true,
      "importance_threshold": 0.6
    },
    "episodic_memory": {
      "enabled": true,
      "store_interactions": true,
      "retention_days": 365,
      "auto_tag": true
    }
  }
}
```

### Tool Configuration

```json
{
  "tools": {
    "enabled": ["web_search", "calculator", "code_interpreter"],
    "tool_settings": {
      "web_search": {"max_results": 5, "search_depth": "basic", "include_snippets": true},
      "calculator": {"precision": 6, "allow_scientific": true},
      "code_interpreter": {"timeout_seconds": 30, "allowed_libraries": ["numpy", "pandas", "matplotlib"], "sandboxed": true, "memory_limit": "512MB"}
    },
    "constraints": {"max_tools_per_message": 5, "max_tool_chain_depth": 3, "require_intent_declaration": true}
  }
}
```

### HITL Configuration

```json
{
  "hitl": {
    "enabled": true,
    "approval_required_for": [
      "file_write", "file_delete", "file_modify", "external_api_call",
      "database_write", "database_delete", "code_execution", "data_export",
      "user_management", "config_change"
    ],
    "auto_approve": ["web_search", "calculator", "read_operation", "internal_lookup"],
    "settings": {"default_priority": "medium", "timeout_minutes": 30, "escalate_on_timeout": true, "require_reason": true, "allow_payload_modification": true},
    "notifications": {"on_request": true, "on_approval": true, "on_rejection": true, "on_expiry": true, "channels": ["in_app", "email"]}
  }
}
```

### Safety Configuration

```json
{
  "safety": {
    "content_filtering": {"enabled": true, "block_harmful_content": true, "block_pii": true, "custom_blocklist": []},
    "output_validation": {"check_code_execution": true, "check_urls": true, "check_file_paths": true, "max_output_length": 50000},
    "rate_limits": {"messages_per_minute": 20, "tokens_per_hour": 100000, "tools_per_conversation": 100},
    "emergency_stop": {"enabled": true, "trigger_keywords": ["emergency stop", "halt all operations"], "notify_admins": true}
  }
}
```

---

## Memory System

### Working Memory (Short-Term)

Working memory holds the current conversation context and is cleared when the session ends.

**Structure:**
```json
{
  "conversation_id": "uuid",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "current_goals": [],
  "intermediate_results": {},
  "token_count": 1500
}
```

**Management Rules:**
- Auto-summarize when approaching token limit
- Prioritize recent messages over older ones
- Preserve system prompt always
- Maintain tool call context for continuity

### Episodic Memory (Long-Term)

Significant interactions stored as vector embeddings for semantic search.

**Storage Triggers:**
- User explicitly states preference/fact
- Agent learns new information during task
- Important decision or conclusion reached
- Error encountered and resolved

**Schema:**
```json
{
  "memory_id": "uuid",
  "agent_id": "uuid",
  "user_id": "uuid",
  "content": "User preference or validated experience",
  "embedding": [0.0012, -0.0034],
  "memory_type": "preference|fact|interaction|knowledge",
  "metadata": {"source": "conversation", "confidence": 0.9, "context": {}},
  "importance": 0.8,
  "tags": ["example"],
  "created_at": "2026-01-01T00:00:00Z"
}
```

### Procedural Memory

Pre-defined knowledge and skills configured by developers.

**Types:**
1. **Response Templates** - Standard formats for common queries
2. **SOPs** - Step-by-step procedures for complex tasks
3. **Domain Knowledge** - Subject-matter expertise
4. **Error Handling** - Known issues and resolutions

---

## Tool System

### Tool Usage Protocol

1. **Declare Intent** - Before using any tool, explain what you want to accomplish
2. **Validate Parameters** - Ensure all required parameters are provided and valid
3. **Execute Safely** - Use tools only for their intended purpose
4. **Report Results** - Clearly communicate tool results to user
5. **Handle Errors** - Gracefully handle tool failures with helpful messages
6. **Respect Central Governance** - Do not create uncontrolled side-channel access to external systems
7. **Verify Important Results** - Do not treat execution as success without appropriate verification

### Available Tool Families

The repository may expose web search, calculation, code execution, file management, SQL/data access, API clients, MCP tools and other capabilities. Their concrete schemas are owned by the implementation that exposes them. Agents must discover the current schema rather than assuming an old inventory is complete.

---

## HITL Guidelines

### Human Approval Is Not Blind Authorization

HITL answers **who is authorized to approve** a consequential action. It does not remove the requirement to assess impact and risk.

Even after human approval, the system should detect obvious contradictions, destructive consequences, invalid parameters or materially changed conditions before execution where practical.

### General Action Path

```text
Agent Intent
    ↓
Understand
    ↓
Impact + Risk Assessment
    ↓
Permission Check
    ↓
Approval when required
    ↓
Execute
    ↓
Verify
    ↓
Audit + Learn
```

### Approval Guidance

**Usually require appropriate approval/governance for:**
- destructive or irreversible data operations;
- production-impacting changes;
- permission or identity changes;
- sensitive external actions;
- bulk exports or disclosure;
- security configuration changes;
- consequential system evolution.

**May be auto-executed when policy permits:**
- low-risk reads;
- ordinary calculations;
- safe discovery;
- reversible internal operations;
- routine verification.

Never classify an action as low risk merely because the user requested it. Unknown risk must remain unknown until investigated.

---

## Safety Protocols

### Content and Data Safety

Agents must protect sensitive information and respect applicable security and privacy boundaries.

### Input Validation

All user inputs must be validated:
- SQL injection prevention (parameterized queries only)
- XSS prevention (output encoding)
- Path traversal prevention (allowed directories only)
- Command injection prevention
- Prompt injection detection and isolation

### Output and Execution Safety

Before consequential execution:
- validate parameters and scope;
- check permissions;
- assess impact and risk;
- prefer reversible actions when possible;
- verify outcomes;
- preserve audit evidence.

For external accounts, credentials and browser sessions:
- treat credentials as secrets;
- require user authorization where appropriate;
- scope access to the intended tenant/task;
- never bypass authentication or security controls;
- respect third-party policies and permissions.

---

## Anti-Pattern Prevention

| Anti-Pattern | Description | Our Mitigation |
|---|---|---|
| **Prompt-and-Pray** | Vague prompting without validation | Structured planning + verification |
| **Memory Amnesia** | Losing important context | Persistent, scoped memory |
| **Silent Failure** | Failure without visibility | Detect + explain + recover + report |
| **Loop Trap** | Repetitive autonomous work | Iteration/time limits |
| **Context Overflow** | Excessive context | Summarization + pruning |
| **Tool Hallucination** | Non-existent/wrong tools | Discovery + schema validation |
| **Permission Creep** | Unauthorized access growth | Central policy + least privilege |
| **Cascade Failure** | Local failure becomes system outage | Isolation + failover |
| **Observability Gap** | Cannot explain behavior | Central telemetry/audit |
| **Cost Runaway** | Uncontrolled spend | Budgets + workload/resource policy |
| **Architectural Island** | A module builds its own disconnected control path | Central capability discovery + governance |
| **Module-Centric Rule Drift** | A universal rule is implemented only in one module | Universal Rule Principle + cross-system review |
| **Blind Human Execution** | Treating human command as automatically safe | Think Before You Act + impact/risk analysis |
| **False Zero-Cost Constraint** | Limiting users because development seeks low cost | Separate development cost strategy from tenant preference |

---

## Best Practices

### For Agent Developers

1. Read the Core Constitution before major work.
2. Inspect current code and runtime evidence before trusting old plans.
3. Identify the owning Circle and how the change connects to the central system.
4. Search for reusable capabilities before creating new ones.
5. Prefer composition and integration over duplication.
6. Treat third-party services as replaceable capabilities, not uncontrolled authorities.
7. Apply governance and safety rules across the whole system, not only the current module.
8. Design tenant/user scope explicitly.
9. Test both the capability and its composition with other capabilities.
10. Preserve observability, verification and rollback paths where practical.

### For Agent Operators

1. Monitor approvals and consequential actions.
2. Review performance, failures and resource usage.
3. Review user feedback and recurring capability gaps.
4. Feed validated lessons into the central learning/evolution process.
5. Maintain security hygiene and access boundaries.

### For Users Interacting with Agents

1. Be specific about goals and constraints.
2. Provide feedback and useful ideas.
3. Review consequential approvals carefully.
4. Remember that both humans and AI can make mistakes; important outcomes should be verified.

---

## Spec-Driven Development (Spec Kit)

This document governs **AI-agent operating behavior**. Engineering principles for feature work are governed separately by the Spec Kit constitution. The two must never contradict; if a conflict is found, stop and resolve it before implementation.

For feature development using Spec-Driven Development, see:

| Artifact | Path | Purpose |
|---|---|---|
| SupremeAI Core Constitution | `docs/architecture/SUPREMEAI_CORE_CONSTITUTION.md` | Cross-cutting product/architecture philosophy and universal rules |
| SDD Engineering Constitution | `.specify/memory/constitution.md` | Project-level engineering principles for SDD |
| Adoption policy & artifact ownership | `docs/SPEC_KIT_ADOPTION.md` | Feature classification, quality gates, governance |
| Agent workflows | `.clinerules/workflows/speckit-*.md` | `/speckit.*` slash-command workflows |

### Operating Rule

Before implementing a Class B or Class C feature (see `docs/SPEC_KIT_ADOPTION.md`), determine whether there is an active Spec Kit feature specification. If none exists, create one through the approved Spec Kit workflow (`/speckit.specify` and related commands). Do not implement major behavior directly from a loose request when the change affects security, data, architecture, deployment, billing, tenancy, or external integrations.

### Additional Agent Obligations

1. Read `AGENTS.md` before major work.
2. Read `docs/architecture/SUPREMEAI_CORE_CONSTITUTION.md` before planning major work.
3. Read the Spec Kit constitution before planning SDD work.
4. Reuse existing architecture before creating new subsystems.
5. Never store secrets in specs, plans, or tasks.
6. Run `analyze` before major implementation.
7. Run tests and security checks after implementation.
8. Run `converge` before declaring a Class C feature complete; if convergence identifies gaps, implement the added tasks and converge again.
9. Do not delete historical feature artifacts under `specs/`.
10. Do not rewrite unrelated architecture while implementing a bounded feature.

---

## Self-Evolving Phase Directives

> **Note:** These directives supplement the configuration above. They represent active operational guidance for agents in the Development & Self-Evolution Phase. Language: Bengali/Banglish for agent communication; English for documentation.

### 1. Out-of-the-Box & Best-Approach Imperative

1. **Best Approach > Strict Rules:** Rules and plans are guidelines, not cages. Agents must invent out-of-the-box meta-logic/hacks for the best solution, bypassing conventional rules when needed.
2. **No Reinventing & Smart Distillation:** Don't write from scratch. Dynamically gather and rewrite the best logic from open-source (GitHub, npm, PyPI).
3. **End-to-End Universal Execution:** From a 1-line vague instruction, autonomously plan, architect, design, code, and CI/CD deploy.
4. **On-the-Fly Tooling:** If no suitable tool exists, create sandboxed scripts at runtime to build your own execution path.
5. **100% Dynamic & Configurable:** Nothing in the system may be hardcoded. Every logic, prompt, and configuration must be fully dynamic so admins can change/control from dashboard.

### 2. Production-Ready Rigor

1. **Zero Half-Baked Code (Production Ready):** No `TODO`, `// fix later`, or mock-data in production code. Every feature must be 100% production-ready from Day 1 with defensive programming (Try-Catch, Timeouts).
2. **Lightweight & High Performance:** Architecture must be ultra-lightweight and super fast. Prevent memory leaks and unnecessary processing; always prioritize performance.
3. **Zero Infrastructure Cost (Free-Tier Maximize):** Design must incur zero extra infrastructure cost. Always optimize within Render, Vercel, Supabase, Cloudflare free-tier limits.
4. **Zero Browser Console Errors:** Every web feature test must have 100% clean browser console. No Red Errors or Yellow Warnings.
5. **Brand Exclusivity & Thin Client:** All clients must be 100% thin clients. Third-party name or API Key exposure is strictly forbidden.

### 3. Dynamic Evolution & Safety Guardrails

1. **The Eternal Brain & Reflection:** Third-party providers are temporary $0-cost muscle; the real intelligence is `ai_memory` (pgvector). Vectorize and save every task's learnings/logs to memory.
2. **Post-Fix DB Injection (Self-Healing Memory):** After any bug fix, CI resolution, or refactoring test pass — inject the Error Pattern, Root Cause, and Fix Snippet directly into `CascadeMemoryService` (`ai_memory` pgvector) and `LESSONS_LEARNED.md` so the system can self-heal future occurrences.
3. **Runtime Verification & Fitness:** Code cannot be pushed based on estimates; verify via Terminal/Browser output. Every autonomous rewrite must improve speed and token efficiency.
4. **Autonomous Action & Safety Switch:** Use `.env`, Terminal, and Browser to complete all work autonomously. For problems, give information-based Root Cause Analysis without sugar-coating. After 3 failed attempts, auto-rollback to `CHECKPOINT.md` version.
5. **Authority & Smart Push:** After work is complete and tests pass, **push to git and deploy directly** (micro-file pushes without reason are forbidden).

### 4. Security & Architecture (Regression Mitigation)

1. **Secure Tokens:** No tokens in URLs (`?token=`). Use `Authorization` headers for SSE, or "First-Message Auth" (payload send on open) for WebSockets.
2. **Event Bus Cleanup:** Always call `unsubscribe()` in React `useEffect` cleanups when using `componentEventBus.ts` to prevent memory leaks.
3. **Strict Sandboxing:** No `allow-same-origin` in iframes. Always use strict CORS policies.
4. **No Secrets in Code:** Never hardcode API keys. Pull from `INFISICAL_TOKEN` or `.env` during runtime or deployment.
5. **CI Test Tier Compliance:** When adding new backend modules/features, always update `backend/tests/conftest.py` (`_CRITICAL_TEST_PARTS` or `_IMPORTANT_TEST_PARTS`) so new tests execute correctly in PR checks. Otherwise they default to `Overall` and only run on `main`.

### 5. Code Lifecycle Policy: "No Dead Code, Only Unused Code"

- **Rule:** No code in the codebase may be labeled "Dead Code" or deleted merely because it's not currently referenced. Code without current references is "Unused Code" — temporarily.
- **Before deleting any code:** Agents MUST verify through multiple approaches (alternative wiring, adapter, fallback utility, architectural repurposing) whether the code is usable elsewhere.
- **Final declaration of "Dead Code" or deletion requires explicit Admin Approval.**

---

## Version History

| Version | Date | Changes |
|---|---|---|
| 1.3.0 | 2026-09-10 | Added Self-Evolving Phase Directives section (merged from .agents/AGENTS.md and docs/AGENTS.md); consolidated 4 AGENTS.md copies into 1 |
| 1.2.0 | 2026-09-08 | Added mandatory SupremeAI Core Constitution link, universal architecture rules, centralized Circle/Powerhouse philosophy, user control, human-error governance, learning/evolution, and development-cost distinction |
| 1.1.0 | 2026-08-29 | Added Spec-Driven Development (Spec Kit) section; fixed heading prefix |
| 1.0.0 | 2025-08-26 | Initial release |

---

## Support

For questions about agent configuration:
- Documentation: See `README.md` and `docs/architecture/SUPREMEAI_CORE_CONSTITUTION.md`
- Issues: GitHub Issues
- Discussions: GitHub Discussions

For security concerns: security@supremeai.app
