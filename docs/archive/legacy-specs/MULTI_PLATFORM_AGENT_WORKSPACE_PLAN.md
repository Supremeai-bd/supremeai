# SupremeAI — Multi-Platform & Multi-Account Agent Workspace Architecture Plan

> **Purpose:** SupremeAI-এর AI agents যেন local PC-এর compute-এর ওপর নির্ভর না করে, একাধিক legitimate account এবং একাধিক cloud platform-এর available capacity ব্যবহার করে isolated, reproducible এবং governed development work করতে পারে।
>
> **Core principle:**  
> **Account ≠ Agent ≠ Workspace ≠ Branch ≠ Platform**

---

## 1. মূল লক্ষ্য

SupremeAI-এর development system এমন হবে যেখানে একটি task এলে system নিজে সিদ্ধান্ত নিতে পারবে:

1. কোন agent দরকার
2. কোন ধরনের workspace দরকার
3. কোন platform ব্যবহার করা উপযুক্ত
4. কোন legitimate account/seat-এ capacity আছে
5. কোন branch-এ কাজ হবে
6. কতক্ষণ workspace রাখা হবে
7. failure হলে কোথায় retry হবে
8. merge-এর আগে কোন validation দরকার
9. কখন human approval বাধ্যতামূলক

অর্থাৎ system-এর লক্ষ্য হবে:

```text
Task
 ↓
Risk / Capability Analysis
 ↓
Agent Selection
 ↓
Workspace Selection
 ↓
Account Selection
 ↓
Platform Selection
 ↓
Isolated Workspace
 ↓
Agent Work
 ↓
Tests / Audit / CI
 ↓
PR
 ↓
Checker / Governance
 ↓
Human Approval when required
 ↓
Merge
 ↓
Workspace Recycle / Destroy
 ↓
Memory + Audit
```

---

## 2. সবচেয়ে গুরুত্বপূর্ণ architecture rule

### 2.1 19 accounts মানে 19 permanent workspace নয়

বর্তমান ধারণাটি:

```text
19 Contributors
      ↓
19 Accounts / Possible Capacity
      ↓
Dynamic Resource Pool
```

এটা কখনো এমন হবে না:

```text
19 Accounts
 ↓
19 Always-Running Workspaces
```

বরং:

```text
Available Capacity
      ↓
Scheduler
      ↓
3–5 Active Workspaces
      ↓
Task অনুযায়ী dynamically allocate
```

প্রয়োজনে পরে:

```text
3 → 5 → 8 → 12 → 19+
```

হতে পারবে। Architecture-এ কোনো সংখ্যা hardcode করা হবে না।

---

## 3. Account, Agent, Workspace এবং Branch আলাদা

### Account
Cloud platform-এর legitimate user/seat/account। এর মধ্যে থাকতে পারে:
- `account_id`
- `provider`
- `authorization_state`
- `quota`
- `current_usage`
- `eligible_workspace_types`
- `health`
- `availability`

Agent কখনো account-এর raw password/token জানবে না।

---

### Agent
যে AI worker task সম্পন্ন করছে। উদাহরণ:
- Planner Agent
- Coder Agent
- Test Agent
- Security Agent
- Review Agent
- CI-Fixer Agent
- Merge/Governance Agent

একই agent এক task শেষে অন্য workspace-এ আবার কাজ করতে পারবে।

---

### Workspace
Agent-এর জন্য temporary development environment। যেমন:
- Codespaces
- Gitpod workspace
- future cloud IDE
- Local development workspace

Workspace disposable হবে।

---

### Branch
Code isolation। Rule:
```text
1 Task → 1 Branch → 1 Focused PR
```
একাধিক agent একই branch-এ parallel write করবে না, unless explicit coordination policy অনুমতি দেয়।

---

## 4. Multi-Platform Architecture

SupremeAI platform-specific logic সরাসরি agent-এর মধ্যে রাখবে না। বরং:

```text
                Workspace Scheduler
                        |
        +---------------+---------------+
        |               |               |
   Codespaces        Gitpod           Local
        |               |               |
   Provider A       Provider B      Provider C
```

পরবর্তীতে: Azure Dev Box, Cloud IDE X, Self-hosted Runner সহজে যোগ করা যাবে।

---

## 5. Platform-এর role

### Tier A — Cloud Development Workspace
- **উদ্দেশ্য**: Heavy coding, Dependency installation, Build, Backend/Frontend work, Long-running development, Repo-level analysis.
- **Candidate**: GitHub Codespaces, Gitpod.

### Tier B — Lightweight Web IDE
- **উদ্দেশ্য**: Quick edit, Documentation, Review, Config change, Simple source inspection, Manual human work.
- **Candidate**: `github.dev` (Compute pool-এর অংশ নয়, browser-only).

### Tier C — CI / Validation
- **উদ্দেশ্য**: Tests, Lint, Type-check, Build, Security scan, PR validation, Regression detection.
- **Candidate**: GitHub Actions. Temporary workspace used on failure for CI-Fixer agent.

### Tier D — Untrusted / Arbitrary Code Execution
- **উদ্দেশ্য**: Agent-generated বা untrusted code isolated sandbox-এ রান করা (No host secrets, restricted network, ephemeral).
- **Candidate**: `SandboxProvider` (CodeSandbox, E2B, Firecracker).

---

## 6. Workspace এবং Sandbox আলাদা abstraction

```text
WorkspaceProvider ≠ SandboxProvider
```

- **Workspace**: Trusted-ish development environment (Repository, Git, Dependencies, Build tools).
- **Sandbox**: Untrusted execution environment (No host secrets, restricted filesystem/network, strict timeout/output caps).

---

## 7. Core Control Plane

SupremeAI-এর central controller:
```text
SupremeAI Control Plane
│
├── Task Orchestrator
├── Agent Registry
├── Workspace Scheduler
├── Account Registry
├── Provider Registry
├── Quota Manager
├── Branch Lock Manager
├── Security Guardian
├── Governance / Approval
├── CI Integration
├── Memory
└── Audit
```

---

## 8. Credential Broker & Zero-Leakage Architecture

```text
Agent → NEVER → Raw Account Credential
```

বরং:
```text
Agent
 ↓
Workspace Scheduler
 ↓
Credential Broker
 ↓
Vault / Secret Store (Infisical)
 ↓
Scoped Provider Authentication
```

Agent শুধু প্রয়োজনীয় scoped capability পাবে, কোনো raw token নয়।

---

## 9. Dynamic Workspace Pool & Scheduling

Recommended pool configuration:
```yaml
workspace_pool:
  min: 0
  target: 3
  max: 5
```

- **No work**: 0 running workspace.
- **Moderate work**: 2–3 active.
- **Heavy work**: 4–5 active.

---

## 10. Failure Recovery & Checkpointing

Cloud workspace failure মানেই task failure নয়:
```text
Agent A in Workspace A (Codespaces)
       ↓ Workspace crash
Latest git checkpoint/commit
       ↓ Scheduler failover
Workspace B in Account B (Gitpod)
       ↓
Agent resumes seamlessly
```
Task state central system-এ সংরক্ষিত থাকবে, কোনো একক workspace-এর ভেতর আটকা পড়বে না।
