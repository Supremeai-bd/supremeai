# SupremeAI Core Constitution

> **Status: Foundational / Mandatory**
>
> This document defines the cross-cutting philosophy and architectural rules that every SupremeAI agent, developer, module, Circle, feature, integration and execution path must follow.
>
> **Read this before planning or implementing any major change.** If a proposed implementation conflicts with this constitution, stop and resolve the conflict before proceeding.

## 1. The North Star

SupremeAI is being built as a **centralized intelligent powerhouse**.

It should become a system that can:

- discover what it can already do;
- compose capabilities across domains;
- use external capabilities when they are better than building them internally;
- allow every tenant/user to control the SupremeAI they own;
- think about consequences before execution;
- learn from validated experience and useful ideas;
- improve over time under governed human oversight.

### The shortest expression

> **One Central System. Complete Circles. Composable Capabilities. Universal Connectivity. User-Owned Control. Intelligent Execution. Human-Governed Evolution.**

---

## 2. Rule #1 — Everything Important Is Centralized

**Centralization is the foundational architectural principle.**

Planning, execution, permissions, policy, configuration, capability discovery, integrations, memory, learning, governance, observability, evolution and recovery must not become isolated systems with independent authority.

Centralized does **not** mean one file, one process or one monolith.

It means:

> **Distributed implementation is allowed; fragmented ownership and control are not.**

A component may execute somewhere else, store data in an appropriate scope, or use an external provider. The SupremeAI control plane must still be able to understand, govern, connect and observe it.

**Nothing important should become an architectural island.**

---

## 3. The Circle Model

Related capabilities should be organized into **Complete Circles** rather than a collection of isolated features.

A Circle is a coherent domain of capability with its own lifecycle, internal components and responsibilities, while remaining connected to the central SupremeAI system.

```text
                    SUPREMEAI CENTRAL CORE
                  Intelligence / Control / Policy
                             │
        ┌────────────────────┼────────────────────┐
        ↓                    ↓                    ↓
     CIRCLE A             CIRCLE B             CIRCLE C
   complete domain      complete domain      complete domain
        ↕                    ↕                    ↕
        └────────────── Universal Connection ─────┘
```

A module is therefore not judged only on its own quality.

It must be evaluated as:

> **Module → Circle → SupremeAI → Whole System**

If a rule, safeguard, intelligence pattern or capability is useful in one Circle, agents must ask whether it should apply across other Circles as a universal rule.

### Universal Rule Principle

> **A solution discovered in one part of SupremeAI must be evaluated for applicability across the whole system. Do not assume a rule is module-specific merely because the problem was discovered inside one module.**

This prevents module-centric thinking from creating inconsistent architecture.

---

## 4. Every Circle Must Increase the Powerhouse

A Circle is not complete merely because it has many features.

It should increase SupremeAI's total ability to solve real problems.

### Powerhouse means

**Own Core Capability + External Capability + Intelligent Orchestration**

SupremeAI must not try to rebuild every third-party platform.

If GitHub is best at Git hosting, use GitHub.
If a specialist provider is best at a task, use that provider.
If SupremeAI's own core is strategically important, keep that capability under its own control.

The goal is not to eliminate third-party dependencies. The goal is to avoid **uncontrolled dependency**.

> **Use the best available power; keep SupremeAI's intelligence, policy, permissions and orchestration in control.**

---

## 5. External Capabilities Are Fuel, Not Islands

Third-party capability should enter SupremeAI through governed integration surfaces such as APIs, adapters, MCP or authorized browser execution.

Conceptually:

```text
Circle / Agent
      ↓
Central Capability Discovery
      ↓
Policy + Permission + Risk
      ↓
Integration / Adapter / MCP / Browser
      ↓
External Capability
      ↓
Verify + Record + Return
```

A Circle should not create its own uncontrolled connection to every external service.

The central system should know:

- what the external capability can do;
- which tenant/user authorized it;
- which permissions are granted;
- which Circle requested it;
- what risk is involved;
- what was executed;
- whether the result was verified;
- what happens if the provider fails.

### Capability dependency vs control dependency

External dependency may be acceptable.

External **control dependency** should be minimized.

> **Capability can be external. Control must remain governed by SupremeAI.**

---

## 6. User-Owned SupremeAI

The platform administrator governs the SupremeAI platform, but every customer/tenant should be able to govern the SupremeAI environment they own within platform boundaries.

Users should be able to discover and activate the capabilities they need rather than receiving one rigid feature set.

Examples:

- Marketing-focused user → marketing capabilities
- Chat-focused user → chat/research capabilities
- Developer → GitHub/coding capabilities
- Automation user → workflow/MCP capabilities
- Advanced user → create and manage their own MCP-backed capabilities

User control should include, where permitted:

- enable/disable capabilities;
- connect/disconnect integrations;
- grant/revoke permissions;
- configure agents;
- create/manage workflows;
- create/manage MCP servers or tools;
- control tenant-level settings;
- review activity and audit information.

**Tenant isolation remains mandatory.** One user's private capabilities, memory or data must not silently become another user's resources.

---

## 7. Chat Is the Center of the Center

The dashboard is the central control surface.

The user-facing **Chat is the center of that center**: a natural interface for asking SupremeAI to discover, configure, plan and execute capabilities.

For example:

> “Connect GitHub.”
>
> “Create an MCP server for this workflow.”
>
> “Disable this integration.”
>
> “Give this agent read-only repository access.”
>
> “Build a marketing automation using my connected tools.”

The UI should expose control explicitly, while Chat should increasingly provide the simplest route to that same centralized control.

---

## 8. Think Before You Act

SupremeAI must not blindly execute an instruction merely because it came from a human.

Human authorization is important, but human decisions can also contain mistakes, misunderstandings or dangerous consequences.

The general execution pattern is:

```text
Understand
   ↓
Assess impact
   ↓
Classify risk
   ↓
Check permission
   ↓
Determine approval requirement
   ↓
Execute / Refuse / Escalate
   ↓
Verify
   ↓
Audit
```

The system must distinguish uncertainty from certainty:

- **Known dangerous** → block/escalate or require the appropriate intervention.
- **Potentially dangerous** → warn, explain consequences and propose safer alternatives.
- **Insufficient information** → ask or investigate rather than pretending risk is low.
- **Low-risk and reversible** → allow efficient automation when policy permits.

Unknown risk must never be silently treated as low risk.

---

## 9. Human Approval + Human Error Correction Are Complementary

These are not competing philosophies.

### Human Approval answers:

> **Who has authority to approve a consequential action?**

### Human Error Correction answers:

> **What should happen when an authorized human decision may still be harmful or mistaken?**

Therefore governance should combine:

```text
AI reasoning
    +
Human authority
    +
Impact analysis
    +
Error detection
    +
Safer alternatives
    +
Auditability
```

The goal is not to place AI above humans.

The goal is to prevent **blind execution by either side**.

This governance model is a cross-system capability, not an admin-only feature. Governance logic should be centralized and reusable by every Circle that performs consequential work.

---

## 10. Learning From Everywhere, Adopting Deliberately

SupremeAI should learn from:

- user ideas and feedback;
- repeated requests;
- successful and failed executions;
- validated system observations;
- research and external knowledge;
- engineering lessons;
- provider reliability;
- reusable capability patterns.

But:

> **Learning ≠ automatic adoption.**

A useful idea should move through a governed evolution pipeline when it can affect the product or system:

```text
Discover
  ↓
Capture evidence
  ↓
Evaluate
  ↓
Compare alternatives
  ↓
Propose
  ↓
Human review when consequential
  ↓
Approve / Reject / Modify / Defer
  ↓
Implement safely
  ↓
Test + measure
  ↓
Promote or rollback
```

Users are not merely feature consumers. Their ideas may become inputs to SupremeAI's future—subject to privacy, evidence and governance.

---

## 11. Memory Has Scope, Governance Is Central

Memory may be separated by scope for privacy and correctness:

- tenant memory;
- user memory;
- Circle/domain memory;
- system memory;
- governance memory;
- evolution memory.

This separation does not mean independent governance.

> **Distributed memory scope does not imply distributed authority.**

Private tenant data must not silently become global learning material. Shared learning should be explicitly governed, appropriately sanitized and privacy-aware.

Useful memory should compound:

```text
Task → Result → Experience → Memory → Better Planning
```

---

## 12. Capability Before Construction

Before building anything new, every agent must ask:

```text
Discover → Reuse → Compose → Adapt → Extend → Create
```

Specifically:

1. Does the capability already exist?
2. Does a similar implementation exist elsewhere in the repository?
3. Is it already exposed through MCP, an adapter, a worker or browser capability?
4. Is it documented as near-ready in the planning corpus?
5. Can another Circle provide the capability?
6. Can an authorized external capability provide it better?
7. If it is genuinely missing, what is the smallest reusable capability to create?

Do not create an isolated subsystem simply because the current task is easier to implement that way.

---

## 13. One Execution Lifecycle

Planning and execution are not separate philosophies.

All consequential work should fit a common lifecycle:

```text
Intent
  ↓
Understand
  ↓
Plan
  ↓
Discover capabilities
  ↓
Select resources
  ↓
Policy / Permission / Risk
  ↓
Approval when required
  ↓
Execute
  ↓
Verify
  ↓
Repair / Retry / Failover
  ↓
Deliver with evidence
  ↓
Capture useful experience
```

The same lifecycle should be reusable across user tasks, research, coding, browser work, deployments, maintenance and system evolution, with different scopes and permissions.

---

## 14. Everything Must Be Observable

If the central system cannot understand what happened, it cannot safely govern or improve it.

Important actions should have sufficient visibility into:

- actor/tenant scope;
- intent;
- selected capability;
- permissions;
- risk classification;
- approval state;
- execution result;
- verification result;
- failure/recovery;
- relevant cost/resource usage;
- reusable lesson or memory.

No silent failure.

> **Failure → Detect → Explain → Repair/Retry → Verify → Report honestly.**

---

## 15. Zero-Cost / Low-Cost Is a Development Philosophy, Not a User Limitation

During SupremeAI's development, the core engineering preference is:

> **Keep the system as close to zero-cost as practically sustainable, and eliminate waste.**

This means preferring:

- free tiers where they are reliable enough;
- reuse over duplicate infrastructure;
- caching;
- on-demand heavy workloads;
- replaceable providers;
- efficient workload placement;
- minimal unnecessary services;
- dynamic resource pools.

### Critical distinction

This is **not** a permanent product rule that every user must operate SupremeAI cheaply.

A user may explicitly want the most powerful, fastest or most expensive available architecture.

Therefore:

```text
Development Cost Philosophy
        ≠
User Workload / Quality / Performance Preference
```

The platform should support different cost/performance policies per tenant where appropriate.

For example:

> Developer default: minimize sustainable infrastructure cost.
>
> User requirement: “Use the highest-quality/highest-performance option regardless of cost.”
>
> SupremeAI: plan according to that user's authorized budget, policy and objective.

**Cost optimization is a system strategy, not a hard ceiling on user capability.**

---

## 16. Universal Rule Test for Every Change

Before an agent implements a change, it should ask:

1. **Centralization:** Is control still centralized?
2. **Circle:** Which Circle owns this capability?
3. **Whole-system applicability:** Does this rule/solution apply elsewhere?
4. **Powerhouse:** Does this increase total system capability?
5. **Reuse:** Does an existing capability already solve this?
6. **External power:** Is a third-party capability genuinely better here?
7. **User control:** Can the correct tenant/user control it?
8. **Security:** Are scope and permissions correct?
9. **Risk:** What can go wrong, even if a human requested it?
10. **Governance:** Does consequential behavior use the central governance path?
11. **Learning:** Can the validated outcome improve future planning?
12. **Observability:** Can the system explain what happened?
13. **Cost:** Is the implementation unnecessarily expensive or wasteful?
14. **No isolation:** Does this create a new architectural island?

If the answer to any important question is unclear, investigate before implementation.

---

## 17. Architectural Laws

These are the shortest rules agents should remember:

1. **Centralize Everything Important.**
2. **Never Create an Unnecessary Island.**
3. **Build Complete Circles, Not Isolated Features.**
4. **Every Circle Must Increase the Powerhouse.**
5. **Reuse Before Creation.**
6. **Use the Best External Capability Without Surrendering Central Control.**
7. **Every Tenant Owns and Controls Their Own SupremeAI Within Policy Boundaries.**
8. **Chat Should Make Central Control Natural.**
9. **Think Before You Act.**
10. **Human Approval Does Not Mean Blind Execution.**
11. **Learning Does Not Mean Automatic Adoption.**
12. **A Rule Discovered in One Module Must Be Evaluated for the Whole System.**
13. **Distributed Scope Is Fine; Distributed Governance Is Not.**
14. **Verify Before Trust.**
15. **Learn From Validated Experience.**
16. **Optimize Cost Without Limiting User Choice.**
17. **Everything Important Must Be Observable.**

---

## 18. Relationship to Other Documents

This constitution is the **cross-cutting philosophy layer**, not a replacement for detailed engineering documentation.

Use it together with:

- `AGENTS.md` — mandatory AI-agent operating and engineering guidance;
- `README.md` — public project architecture and capability model;
- `.specify/memory/constitution.md` — Spec Kit engineering constitution;
- `docs/SUPREMEAI_MASTER_ROADMAP_2026-09.md` — execution roadmap;
- `docs/ai-engineering/INTELLIGENCE_DECISION_LOG.md` — intelligence/risk decisions;
- relevant domain/Circle plans under `docs/` and `specs/`.

### Source-of-truth rule

This constitution defines the **why and universal architectural rules**.

Detailed documents define **how** a particular area implements those rules.

If documents appear to conflict:

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

A conflict must be made explicit and resolved; agents must not silently choose whichever document is more convenient.

---

## 19. Final Principle

SupremeAI should not be thought of as a collection of modules that happen to work together.

It should be built as **one intelligent powerhouse made of complete, connected Circles**.

The modules are implementation units.
The Circles are capability units.
The central system is the control and intelligence layer.
The user is the owner of their experience and authorized capabilities.
External services are usable sources of power.
Governance protects the system from blind execution.
Learning makes validated experience compound.

> **One system. One governing philosophy. Many capabilities. One SupremeAI.**
