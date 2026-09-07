# SupremeAI Core Constitution

> **Status: Foundational / Mandatory**
>
> This document defines the cross-cutting philosophy and universal architectural rules that every SupremeAI agent, developer, module, Circle, capability, integration, interface, plan and execution path must follow.
>
> **Read this before planning or implementing major work.** If an implementation conflicts with this constitution, stop and resolve the conflict before proceeding.

## 1. The North Star

SupremeAI is a **centralized intelligent powerhouse** made of complete, connected capability Circles.

It should discover what it can already do, compose capabilities across domains, use external power when appropriate, give each tenant control of the SupremeAI they own, reason before consequential execution, learn from validated experience, and evolve under human governance.

> **One Central System. Complete Circles. Composable Capabilities. Universal Connectivity. User-Owned Control. Intelligent Execution. Human-Governed Evolution.**

## 2. Rule #1 — Everything Important Is Centralized

Centralization is the foundational principle.

Planning, capability discovery, execution, permissions, policy, configuration, integrations, memory, learning, governance, observability, recovery and evolution must not become isolated systems with independent authority.

Centralized does **not** mean one process or one monolith.

> **Distributed implementation is allowed; fragmented ownership and control are not.**

A component may execute elsewhere, use a distributed datastore or depend on an external provider. SupremeAI must still be able to understand, govern, connect and observe it.

**Nothing important should become an architectural island.**

## 3. Complete Circles

Related capabilities should be organized into **Complete Circles**, not isolated feature piles.

A Circle is a coherent capability domain with internal components and lifecycle, while remaining connected to the central system.

```text
                         SUPREMEAI
                 Central Intelligence / Control
                              │
          ┌───────────────────┼───────────────────┐
          ↓                   ↓                   ↓
      CIRCLE A            CIRCLE B            CIRCLE C
    complete domain     complete domain     complete domain
          ↕                   ↕                   ↕
          └──────────── Universal Connection ─────┘
```

Every module must be evaluated as:

> **Module → Circle → SupremeAI → Whole System**

### Universal Rule Principle

A rule, safeguard, capability, intelligence pattern or architectural solution discovered in one part of SupremeAI must be evaluated for applicability across the entire system.

> **Do not treat a system-wide principle as module-specific merely because the problem was first discovered inside one module.**

## 4. Powerhouse Principle

A Circle increases the total power of SupremeAI through:

> **Own Core Capability + External Capability + Intelligent Orchestration**

SupremeAI should not rebuild every third-party platform. If GitHub, a specialist AI provider, a browser service or another external system is better at a capability, SupremeAI should be able to use it.

The goal is not zero external dependency. The goal is **no uncontrolled dependency**.

> **Use the best available power; keep SupremeAI's intelligence, policy, permissions and orchestration in control.**

## 5. Universal Capability Connectivity

Any authorized Circle should be able to reuse capabilities exposed by other Circles, internal services or approved external systems.

Capabilities should be discoverable, composable and invokable through governed interfaces rather than duplicated inside every module.

Conceptually:

```text
Intent
  ↓
Central Capability Discovery
  ↓
Policy + Permission + Risk
  ↓
Capability / MCP / Adapter / API / Browser
  ↓
Execution
  ↓
Verification + Audit + Learning
```

Before creating a new capability, agents must search for existing, planned, near-ready, internal and authorized external capabilities.

## 6. External Power Is Fuel, Not Authority

External services may provide capability through APIs, adapters, MCP servers, browser automation or other approved integration surfaces.

The central system must know, where applicable:

- what the capability can do;
- which tenant/user authorized it;
- what permissions are granted;
- which Circle requested it;
- what risk is involved;
- what was executed;
- whether the result was verified;
- how provider failure is handled.

> **Capability dependency may be acceptable. Control dependency must remain governed by SupremeAI.**

## 7. User-Owned SupremeAI

Every customer/tenant should be able to govern the SupremeAI environment they own within platform, security and policy boundaries.

Users should be able to discover and activate only the capabilities they need.

Where permitted, tenant control includes:

- enabling/disabling capabilities;
- connecting/disconnecting integrations;
- granting/revoking permissions;
- configuring agents;
- creating/managing workflows;
- creating/managing MCP servers and tools;
- managing tenant settings;
- reviewing activity and audit information.

Tenant isolation is mandatory. Private data, memory, credentials and capabilities must not silently cross tenant boundaries.

## 8. Human Interfaces and the Central MCP Control Interface

SupremeAI has multiple execution surfaces, but they must not create multiple independent control systems.

The intended logical model is:

```text
                         HUMAN
                 User / Tenant Admin
                          │
              ┌───────────┴───────────┐
              ↓                       ↓
            CHAT                 DASHBOARD
              │                       │
              └───────────┬───────────┘
                          ↓
             CENTRAL MCP / CONTROL INTERFACE
                          │
             ┌────────────┼────────────┐
             ↓            ↓            ↓
          CIRCLE A     CIRCLE B     CIRCLE C
             │            │            │
        Capabilities   Agents       Tools
             └────────────┼────────────┘
                          ↓
                  EXECUTION LAYER
                          ↓
              Backend / Workers / APIs
             / External Services / Browser
```

### MCP's role

**MCP is the universal capability and control interface of SupremeAI.** It should become the logical central access point through which authorized humans, agents, Chat and Dashboard operations can discover, inspect, configure and invoke capabilities.

MCP does **not** replace the backend.

The backend remains the underlying engine and enforcement layer for:

- business logic;
- authentication and authorization enforcement;
- database/state management;
- execution;
- workers and queues;
- security controls;
- infrastructure;
- transactions and reliability.

Therefore:

> **MCP is the central capability/control interface; the backend is the execution and enforcement engine.**

No Circle should create an uncontrolled parallel control interface merely because it is easier locally.

### Chat

Chat should be the most natural conversational route into centralized control:

> “Connect GitHub.”
>
> “Create an MCP server for this workflow.”
>
> “Revoke this agent's repository permission.”
>
> “Build an automation using my connected tools.”

### Dashboard

Dashboard is the visual control surface for the same underlying system. It must not become a second independent architecture.

## 9. Think Before You Act

SupremeAI must not blindly execute an instruction merely because it came from a human or an agent.

The general execution model is:

```text
Understand
   ↓
Assess Impact
   ↓
Classify Risk
   ↓
Check Permission
   ↓
Determine Approval
   ↓
Execute / Refuse / Escalate
   ↓
Verify
   ↓
Audit + Learn
```

- **Known dangerous** → block/escalate or require appropriate intervention.
- **Potentially dangerous** → warn, explain consequences and offer safer alternatives.
- **Insufficient information** → investigate or ask; do not pretend risk is low.
- **Low-risk and reversible** → automate when policy permits.

> **Unknown risk must never silently become low risk.**

## 10. Human Approval + Human Error Correction

Human Approval answers **who has authority**.

Human Error Correction answers **what happens when an authorized human decision may still be wrong or harmful**.

They are complementary governance layers:

```text
Intent → Policy → Risk → Human Authority
      → Error Detection → Consequence Analysis
      → Decision → Audit
```

Human authority must be respected, but consequences must still be reasoned about. This is a cross-system capability, not an admin-only feature.

## 11. Learning From Everywhere, Adopting Deliberately

SupremeAI should learn from user ideas, repeated requests, successful and failed executions, system observations, external knowledge, engineering lessons, provider behavior and reusable capability patterns.

> **Learning ≠ Automatic Adoption.**

System evolution follows:

```text
Discover → Capture Evidence → Evaluate → Propose
→ Human Review when consequential
→ Approve / Reject / Modify / Defer
→ Implement → Test → Measure → Promote / Rollback
```

Private tenant information must not silently become global learning.

## 12. Memory Has Scope; Governance Is Central

Memory may be scoped by tenant, user, Circle/domain, system, governance or evolution needs.

> **Distributed memory scope does not imply distributed authority.**

Useful memory should compound:

```text
Task → Result → Experience → Memory → Better Planning
```

Shared learning must be privacy-aware and explicitly governed.

## 13. Capability Before Construction

Every new implementation must follow:

```text
Discover → Reuse → Compose → Adapt → Extend → Create
```

Ask:

1. Does it already exist?
2. Does a similar implementation exist elsewhere?
3. Is it exposed through MCP, an adapter, worker or browser capability?
4. Is it planned or near-ready?
5. Can another Circle provide it?
6. Can an authorized external capability provide it better?
7. If genuinely missing, what is the smallest reusable capability to create?

Do not create an isolated subsystem simply because it is locally convenient.

### No "Dead Code", Only "Unused Code"

Existing code must never be casually classified as "dead code" and deleted. If unreferenced, it is temporarily "unused code". Agents must evaluate repurposing, alternative wiring, adapters, or fallback utilities before deprecating anything. Declaring code dead or deleting it requires explicit admin approval.

## 14. One Execution Lifecycle

Planning and execution are one system:

```text
Intent → Understand → Plan → Discover Capabilities
→ Select Resources → Policy / Permission / Risk
→ Approval when required → Execute → Verify
→ Repair / Retry / Failover → Deliver Evidence
→ Capture Experience
```

This lifecycle should be reusable across research, coding, browser work, deployments, maintenance, automation and system evolution.

## 15. Everything Must Be Observable

Important actions should preserve enough evidence to understand:

- actor and tenant scope;
- intent;
- selected capability;
- permissions;
- risk;
- approval state;
- execution result;
- verification result;
- failure/recovery;
- relevant resource/cost usage;
- reusable lesson.

> **Failure → Detect → Explain → Repair/Retry → Verify → Report honestly.**

No silent failure.

## 16. Zero-Cost / Low-Cost Is a Development Philosophy

SupremeAI development should minimize waste and keep sustainable infrastructure cost near zero where practical through free tiers, reuse, caching, on-demand workloads, replaceable providers and efficient resource placement.

This is **not** a hard limit on users.

```text
Development Cost Philosophy
        ≠
User Workload / Quality / Performance Preference
```

A tenant may explicitly choose a more expensive, faster or higher-quality configuration according to their authorized budget and policy.

> **Optimize platform sustainability without limiting legitimate user choice.**

## 17. Universal Rule Test for Every Change

Before implementation, ask:

1. Is control still centralized?
2. Which Circle owns this capability?
3. Is the rule applicable across the whole system?
4. Does it increase total powerhouse capability?
5. Can an existing capability be reused?
6. Is external power genuinely better?
7. Can the correct tenant/user control it?
8. Are security and permissions correct?
9. What can go wrong even if a human requested it?
10. Does consequential behavior use central governance?
11. Can validated results improve future planning?
12. Can the system explain what happened?
13. Is the implementation unnecessarily expensive?
14. Does it create an architectural island?
15. Does it bypass the central MCP/control model without a justified reason?

If an important answer is unclear, investigate before implementation.

## 18. Architectural Laws

1. **Centralize Everything Important.**
2. **Never Create an Unnecessary Island.**
3. **Build Complete Circles, Not Isolated Features.**
4. **Every Circle Must Increase the Powerhouse.**
5. **Reuse Before Creation.**
6. **Use External Power Without Surrendering Central Control.**
7. **Every Tenant Owns and Controls Their Own SupremeAI Within Policy Boundaries.**
8. **Chat and Dashboard Are Interfaces to One Central System.**
9. **MCP Is the Universal Capability and Control Interface.**
10. **Backend Remains the Execution and Enforcement Engine.**
11. **Think Before You Act.**
12. **Human Approval Does Not Mean Blind Execution.**
13. **Learning Does Not Mean Automatic Adoption.**
14. **A Rule Discovered in One Module Must Be Evaluated for the Whole System.**
15. **Distributed Scope Is Fine; Distributed Governance Is Not.**
16. **Verify Before Trust.**
17. **Learn From Validated Experience.**
18. **Optimize Development Cost Without Limiting User Choice.**
19. **Everything Important Must Be Observable.**
20. **No "Dead Code", Only "Unused Code" (Admin Approval Required Before Deletion).**

## 19. Relationship to Other Documents

This constitution is the **cross-cutting philosophy and universal-rule layer**, not a replacement for detailed engineering documentation.

Use it together with:

- `AGENTS.md` — mandatory AI-agent operating guidance;
- `README.md` — project architecture and capability model;
- `.specify/memory/constitution.md` — Spec Kit engineering constitution;
- `docs/SUPREMEAI_MASTER_ROADMAP_2026-09.md` — execution roadmap;
- `docs/ai-engineering/INTELLIGENCE_DECISION_LOG.md` — intelligence/risk decisions;
- relevant Circle/domain plans under `docs/` and `specs/`.

### Source-of-truth rule

This constitution defines **why and the universal rules**. Detailed documents define **how a specific area implements them**.

If documents conflict:

```text
Current runtime/source evidence
        ↓
Security / policy constraints
        ↓
This Core Constitution
        ↓
Detailed architecture / roadmap
        ↓
Feature-specific implementation detail
```

Conflicts must be made explicit and resolved; agents must not silently choose the most convenient document.

## 20. Final Principle

SupremeAI is not a collection of modules that happen to work together.

It is **one intelligent powerhouse made of complete, connected Circles**.

Modules are implementation units.
Circles are capability units.
MCP is the universal capability/control interface.
The backend is the execution/enforcement engine.
Chat and Dashboard are human-facing surfaces into the same system.
The user owns their authorized SupremeAI environment.
External services are sources of power.
Governance prevents blind execution.
Learning makes validated experience compound.

> **One system. One governing philosophy. One central control model. Many capabilities. One SupremeAI.**
