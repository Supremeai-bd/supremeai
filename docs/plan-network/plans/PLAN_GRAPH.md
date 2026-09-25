---
id: plan-graph
subject: "SupremeAI Plan Graph"
document_role: graph
planning_authority: Architecture Governance / Planning Circle
canonical: true
status: active
evidence_state: verified
disposition: retain
last_verified: 2026-09-24
supersedes: []
superseded_by: []
target_scope: combined_ecosystem
---

# SupremeAI Plan Graph

> The visual relationship map of the Plan Network. Every arrow is a real
> dependency that already exists in [PLAN_REGISTRY.md](./PLAN_REGISTRY.md).
> This is a **living graph**, not a static diagram — when the registry changes,
> this graph changes.

**Legend:**

- `A --> B` means **A depends on B** (B must be Stable before A can ship).
- Node color = domain (see [domains](../architecture/domains.md)).
- Node border = status (Stable = green, Active = blue, Implementing = purple, Verifying = amber, Proposed = gray).

---

## Full dependency graph

```mermaid
flowchart TD
    %% ---- Foundation ----
    P01["🛡️ P01 Security Guardian<br/><i>Security · Active</i>"]

    %% ---- Intelligence core ----
    P02["🧠 P02 Provider Abstraction<br/><i>Intelligence · Active</i>"]
    P03["🔌 P03 MCP Architecture<br/><i>MCP · Stable</i>"]
    P04["🤖 P04 Agent Orchestration<br/><i>Agents · Active</i>"]
    P05["🧬 P05 Memory & Knowledge<br/><i>Intelligence · Active</i>"]

    %% ---- Automation / Experience ----
    P06["🌐 P06 Browser Automation<br/><i>Automation · Implementing</i>"]
    P07["🖥️ P07 Frontend Evolution<br/><i>Experience · Active</i>"]

    %% ---- Infra / Observability ----
    P08["⚙️ P08 Infrastructure Optimization<br/><i>Infrastructure · Active</i>"]
    P09["📈 P09 Observability<br/><i>Observability · Implementing</i>"]

    %% ---- Governance ----
    P10["🚦 P10 Deployment Safety<br/><i>Governance · Active</i>"]
    P11["✅ P11 Testing & Quality<br/><i>Governance · Verifying</i>"]
    P12["🧹 P12 Codebase Cleanup<br/><i>Governance · Proposed</i>"]

    %% ---- Depends-on edges (A --> B : A depends on B) ----
    P01 --> P02
    P01 --> P03
    P01 --> P08

    P02 --> P04
    P03 --> P04
    P03 --> P05
    P03 --> P06
    P03 --> P07
    P04 --> P05
    P04 --> P07

    P08 --> P09
    P08 --> P10
    P08 --> P11
    P09 --> P10

    %% ---- Related (dashed) ----
    P01 -.related.-> P10
    P01 -.related.-> P11
    P04 -.related.-> P06
    P04 -.related.-> P10
    P10 -.related.-> P11
    P11 -.related.-> P12

    %% ---- Status styling ----
    classDef stable stroke:#059669,stroke-width:3px,color:#059669;
    classDef active stroke:#1d4ed8,stroke-width:2px,color:#1d4ed8;
    classDef implementing stroke:#7c3aed,stroke-width:2px,color:#7c3aed;
    classDef verifying stroke:#ca8a04,stroke-width:2px,color:#ca8a04;
    classDef proposed stroke:#64748b,stroke-width:2px,color:#64748b;

    class P03 stable;
    class P01,P02,P04,P05,P07,P08,P10 active;
    class P06,P09 implementing;
    class P11 verifying;
    class P12 proposed;
```

---

## Foundation → Execution flow

The same network read top-to-bottom as the user's intended execution model:

```mermaid
flowchart TD
    V["🎨 Vision & Principles"]
    V --> D["🏛️ 9 Domains"]
    D --> P["📋 12 Strategic Plans<br/>(this registry)"]
    P --> DEP["🔗 Dependencies<br/>(this graph)"]
    DEP --> M["🎯 Milestones"]
    M --> GH["🐛 GitHub Issues / PRs"]
    GH --> IMPL["💻 Implementation"]
    IMPL --> VRF["🔍 Verification"]
    VRF -.feedback.-> P
```

---

## Domain cluster view

Plans grouped by their owning domain. This is the view to use when scoping a
single team's work.

```mermaid
flowchart LR
    subgraph Security["🛡️ Security"]
        P01["P01 Security Guardian"]
    end
    subgraph Intelligence["🧠 Intelligence"]
        P02["P02 Provider Abstraction"]
        P04["P04 Agent Orchestration"]
        P05["P05 Memory & Knowledge"]
    end
    subgraph MCP["🔌 MCP"]
        P03["P03 MCP Architecture"]
    end
    subgraph Agents["🤖 Agents"]
        P04b["P04 (shared)"]
    end
    subgraph Automation["🌐 Automation"]
        P06["P06 Browser Automation"]
    end
    subgraph Experience["🖥️ Experience"]
        P07["P07 Frontend Evolution"]
    end
    subgraph Infra["⚙️ Infrastructure"]
        P08["P08 Infra Optimization"]
    end
    subgraph Observability["📈 Observability"]
        P09["P09 Observability"]
    end
    subgraph Governance["🚦 Governance"]
        P10["P10 Deployment Safety"]
        P11["P11 Testing & Quality"]
        P12["P12 Codebase Cleanup"]
    end

    P01 --> P02
    P01 --> P03
    P01 --> P08
    P02 --> P04
    P03 --> P04
    P03 --> P05
    P03 --> P06
    P03 --> P07
    P04 --> P05
    P04 --> P07
    P08 --> P09
    P08 --> P10
    P08 --> P11
    P09 --> P10
```

---

## Reading the graph

1. **Start at P01.** Everything depends on Security Guardian. If P01 is not
   Stable, no other plan can claim Stable either.
2. **Follow the arrows down.** P03 (MCP) is the most-connected enabler — four
   plans depend on it. That makes P03 the highest-leverage plan to keep healthy.
3. **Watch the dashed lines.** `related` edges are not blocking dependencies,
   but they signal "touching one likely affects the other."
4. **P11 (Testing & Quality) is the verification sink.** It depends on infra
   but every plan eventually flows evidence through it.

---

## Updating this graph

This graph is generated from [PLAN_REGISTRY.md](./PLAN_REGISTRY.md). When you
change a plan's `dependsOn` or `enables`, update both files in the same PR.
The `scripts/governance/lint_plans.py` check (extended by this patch) verifies
graph ↔ registry parity.
