# SECURITY_GUARDIAN.md — Security Guardian Constitution

> **প্রকৃতি:** চিরন্তন (Timeless) সিকিউরিটি কনস্টিটিউশন — টেকনোলজি-মুক্ত ইনভেরিয়েন্টসমূহ।  
> **মালিক:** Security Guardian Engine (`.github/workflows/pr-pipeline.yml` → `guardian-lite` / `guardian-deep`)  
> **সম্পর্কিত ডকুমেন্টস:** [ARCH-GAP-01-DECISION-GAP-ANALYSIS](../master_docs/ARCH-GAP-01-DECISION-GAP-ANALYSIS.md), [HITL_APPROVAL_CONTRACT](./HITL_APPROVAL_CONTRACT.md), [SECURITY_CONTROLS_BASELINE](./SECURITY_CONTROLS_BASELINE.md), [implementation_plan.md](../../implementation_plan.md)  
> **Phase:** 1 (Security Constitution & Policies)  
> **তৈরির তারিখ:** সেপ্টেম্বর ২০২৬

---

## 🎯 Executive Summary / সারসংক্ষেপ

SupremeAI-এর সিকিউরিটি সিদ্ধান্ত আর কোনো "lint-এর পরের ধাপ" নয়। এটি একটি **ইন্টেলিজেন্ট গার্ডিয়ান ডিসিশন ইঞ্জিন** যা ১৫টি চিরন্তন ইনভেরিয়েন্ট দ্বারা পরিচালিত হয়।

এই কনস্টিটিউশন (constitution) ঘোষণা করে যে — টেকনোলজি পরিবর্তিত হতে পারে (JWT → Paseto, Redis → Valkey, SQLAlchemy → SQLModel), কিন্তু **নিচের ১৫টি মূলনীতি আগামী ১০০০ দিন অপরিবর্তিত থাকবে**। গার্ডিয়ান এই ইনভেরিয়েন্টগুলিকে "অনুমান" হিসেবে নয়, বরং **প্রয়োগযোগ্য চুক্তি (enforceable contracts)** হিসেবে ব্যবহার করে।

This file is the **single source of truth** for the Guardian's behavior. Modifying it counts as a self-modification under SG-11 (Bootstrap Trust) — see the [Bootstrap Trust](#-bootstrap-trust-sg-11) section.

The 15 invariants are bound to:
- A **two-tier engine** (Lite + Deep) that runs based on `risk_class`.
- A **protected-scopes** policy (`security/policies/protected-scopes.yml`) that escalates to CRITICAL.
- A **security decision contract** (YAML) emitted by `pr-gate` for every PR.
- A **time-bound exceptions** policy (`security/policies/exceptions.yml`) so bypasses never become permanent.

---

## 🛡️ The 15 Timeless Invariants

```text
SG-01: Never expose secrets or sensitive credentials.
SG-02: Never trust unvalidated or unauthenticated input.
SG-03: Authentication and authorization must be explicit and enforceable.
SG-04: Every privileged action must operate under least privilege.
SG-05: User, tenant, agent, and system boundaries must remain isolated.
SG-06: Security-sensitive operations must be auditable.
SG-07: Security controls must not be silently weakened or bypassed.
SG-08: Unknown security state must never be treated as confirmed-safe.
SG-09: Destructive or privileged automation requires explicit authorization.
SG-10: Security findings require evidence before they become blocking decisions (No Evidence → No Verdict).
SG-11: Guardian must never approve or validate its own security-critical modification (Bootstrap Trust).
SG-12: Critical paths (Auth, HITL, Secrets) require stronger validation than ordinary code.
SG-13: External systems, dependencies, APIs, and tools are untrusted boundaries.
SG-14: Security exceptions must be explicit, scoped, owned, and time-bounded (No Permanent Bypass).
SG-15: Every security control must have an enforceable verification path.
```

### Invariant Explanations (with practical examples)

**SG-01 — Never expose secrets or sensitive credentials.**  
কোনো API key, JWT signing key, DB password, Infisical token, বা PII কখনোই log, commit message, error response, বা `print()` output-এ যাবে না। *Example:* `graph_service.py`-তে `print(f"NEO4J_URI={uri}")` লেখা হলে Guardian-Lite সেটাকে `BLOCK` করবে কারণ `NEO4J_URI`-তে password embedded থাকতে পারে।

**SG-02 — Never trust unvalidated or unauthenticated input.**  
External input (HTTP body, query string, WebSocket message, MCP tool arg, webhook payload) সবসময় schema-validate করতে হবে এবং যেখানে প্রযোজ্য সেখানে auth-context সহ যাচাই করতে হবে। *Example:* `/api/tasks/run` endpoint-এ যদি `agent_id` query param ব্যবহারকারীর tenant-এর অধীনে না থাকে, তাহলে `403 Forbidden` — কখনো "silent fall-through" নয়।

**SG-03 — Authentication and authorization must be explicit and enforceable.**  
"Implicit trust" (যেমন "এই endpoint শুধু internal তাই auth লাগবে না") নিষিদ্ধ। প্রতিটি privileged action-এ স্পষ্ট `@require_auth(scope="...")` decorator বা policy gate থাকতে হবে। *Example:* HITL approval revoke endpoint-টি শুধু `is_authenticated` নয়, `has_scope("hitl:revoke")` চেক করবে।

**SG-04 — Every privileged action must operate under least privilege.**  
GitHub PAT যা শুধু issue label করে, তার দিয়ে `git push` হবে না। Render API key যা শুধু deploy trigger করে, তার দিয়ে service delete হবে না। *Example:* `Deploy Doctor`-এর ব্যবহৃত `RENDER_API_KEY_1`-এর শুধু "read deploys + read logs" scope থাকতে হবে, full admin নয়।

**SG-05 — User, tenant, agent, and system boundaries must remain isolated.**  
Tenant-A-এর task list Tenant-B দেখতে পারবে না। Agent-X-এর session token Agent-Y-এর request-এ পুনরায় ব্যবহার করা যাবে না। *Example:* `database/migrations/`-এ যদি `tenant_id` column সরানো হয় RLS (Row-Level Security) ছাড়া, তাহলে Guardian-Deep এটাকে CRITICAL BLOCK হিসেবে চিহ্নিত করবে।

**SG-06 — Security-sensitive operations must be auditable.**  
HITL approve/reject, secret rotation, auto-merge enable/disable, deploy trigger — প্রতিটির একটি অপরিবর্তনযোগ্য audit trail থাকতে হবে (issue comment, log line, বা DB row)। *Example:* PR Helper Step 5 যখন auto-merge enable করে, তখন সেটা একটি comment হিসেবে PR-এ লেখা থাকবে — পরে কে কখন কী করেছিল দেখা যাবে।

**SG-07 — Security controls must not be silently weakened or bypassed.**  
`# noqa`, `@pytest.mark.skip`, `if DEBUG: bypass = True`, `try: validate(); except: pass` — সব নীরব bypass নিষিদ্ধ। বাইপাস করতে হলে স্পষ্ট `EXC-xxx` ID সহ exception (`security/policies/exceptions.yml`-এ) লাগবে। *Example:* কোনো test-এ `pytest.skip("auth flaky")` লেখা থাকলে Guardian-Lite সেটাকে `WARN` করবে এবং owner-কে জিজ্ঞেস করবে যে exception filed হয়েছে কিনা।

**SG-08 — Unknown security state must never be treated as confirmed-safe.**  
যদি Guardian কোনো path analyze করতে না পারে (binary file, অপরিচিত extension, encoding error), তাহলে সেটাকে "safe" ধরা যাবে না — এটি `REVIEW` হবে, `PASS` নয়। *Example:* কোনো PR-এ `.so` ফাইল যোগ করা হলে Guardian-Lite সেটাকে "untrusted binary" হিসেবে চিহ্নিত করে human review-তে পাঠাবে।

**SG-09 — Destructive or privileged automation requires explicit authorization.**  
Auto-merge, force-push, branch delete, issue close, deploy trigger — প্রতিটির আলাদা explicit authorization gate থাকতে হবে। *Example:* PR Helper Step 5 যখন `gh pr merge --auto --squash` চালায়, তখন সেটির জন্য আলাদা `PURE_IMPROVEMENT_VERIFIED` flag লাগে; "general CI green" যথেষ্ট নয়।

**SG-10 — Security findings require evidence before they become blocking decisions (No Evidence → No Verdict).**  
কোনো finding যদি "heuristic match" হয় কিন্তু প্রমাণ না থাকে, তাহলে সেটি `WARN` হবে, `BLOCK` নয়। এটি false-positive storm প্রতিরোধ করে। *Example:* কোনো PR-এ `password = "..."` pattern match হলে, কিন্তু string-টি আসলে একটি test fixture-এর placeholder, তাহলে Guardian সেটাকে `WARN` করবে এবং evidence pack চাইবে — সরাসরি `BLOCK` নয়।

**SG-11 — Guardian must never approve or validate its own security-critical modification (Bootstrap Trust).**  
যদি কোনো PR `pr-helper.yml`, `delta_analysis.py`, `hunk_isolation.py`, এই `SECURITY_GUARDIAN.md` ফাইল, বা `security/policies/**` পরিবর্তন করে, তাহলে Guardian auto-merge নিষ্ক্রিয় করবে এবং বাধ্যতামূলক human review দাবি করবে। *বিস্তারিত নিচের [Bootstrap Trust](#-bootstrap-trust-sg-11) section-এ।*

**SG-12 — Critical paths (Auth, HITL, Secrets) require stronger validation than ordinary code.**  
সাধারণ backend code-এর জন্য যা যথেষ্ট (unit test), সেটা auth/HITL/secrets code-এর জন্য যথেষ্ট নয় (দরকার integration + boundary test)। *Example:* `services/hitl/**` বা `backend/core/auth/**` পরিবর্তন করলে Guardian-Deep mandatory হবে — এটি Guardian-Lite দিয়ে pass হলেও।

**SG-13 — External systems, dependencies, APIs, and tools are untrusted boundaries.**  
কোনো external service (Render, Supabase, GitHub API, npm registry, MCP server) থেকে আসা প্রতিটি response-কে untrusted হিসেবে validate করতে হবে। *Example:* MCP server থেকে আসা tool result-কে schema-validate করতে হবে — সরাসরি `eval()` বা `exec()` করা যাবে না।

**SG-14 — Security exceptions must be explicit, scoped, owned, and time-bounded (No Permanent Bypass).**  
প্রতিটি exception-এর একটি `owner`, একটি নির্দিষ্ট `scope.path`, একটি `expires_on` (max 30 দিন), এবং একটি justification থাকতে হবে। *Example:* দেখুন `security/policies/exceptions.yml`-এর schema — কোনো `expires_on` না থাকলে সেটা গার্ডিয়ান দ্বারা reject করা হবে।

**SG-15 — Every security control must have an enforceable verification path.**  
কোনো rule যদি "enforce" করা যায় না (যেমন শুধু doc-এ লেখা থাকে কিন্তু CI-তে চেক নেই), তাহলে সেটি "control" নয়, "wish"। প্রতিটি ইনভেরিয়েন্টের একটি concrete enforcement mechanism থাকতে হবে। *Example:* SG-01-এর জন্য `trufflehog` বা `gitleaks` scan; SG-04-এর জন্য `permissions:` block audit; SG-11-এর জন্য protected-scopes path check।

---

## 🏛️ Two-Tier Guardian Engine

### Guardian-Lite (every PR — fast)

| Aspect | Value |
|---|---|
| **When** | প্রতিটি PR-এ বাধ্যতামূলক (opened / synchronize / ready_for_review) |
| **Runtime** | ~১৫–৩০ সেকেন্ড |
| **Checks** | Hardcoded secret/token leak (gitleaks-style), dangerous shell commands, workflow `permissions:` block audit, no-bypass control rules, SG-01/SG-04/SG-07 surface checks |
| **Output** | Single YAML decision row feeding `pr-gate` |
| **Failure behavior** | Any confirmed violation → `status: BLOCK` (no auto-merge) |

### Guardian-Deep (high-risk only — slower)

| Aspect | Value |
|---|---|
| **When** | শুধুমাত্র যখন `risk_class >= HIGH` অথবা `protected_scope_touched == true` |
| **Runtime** | ~১–২ মিনিট |
| **Checks** | Auth middleware + tenant isolation regression, HITL bypass detection, dependency + config delta analysis, security control weakening patterns (SG-07), bootstrap-trust detection (SG-11), baseline-vs-delta evidence (SG-10) |
| **Output** | Full Security Decision Contract (see below) |
| **Failure behavior** | `new_findings_introduced > 0` (with evidence) → `status: BLOCK`; self-modification → `status: REVIEW` + auto-merge disabled |

### Workflow composition (Phase 2 preview)

```
PR opened/updated
   │
   ├─► detect-scope  ──► (computes risk_class + protected_scope flags)
   │
   ├─► guardian-lite (every PR, ~20s)
   │
   ├─► guardian-deep (only if risk_class ≥ HIGH or protected_scope)
   │
   ├─► pr-agent-helper + pr-lifecycle (delta analysis)
   │
   ├─► ci.yml (workflow_call — only if code_changed)
   │
   └─► pr-gate (synthesizes Security Decision Contract → required status check)
```

---

## 🔐 Protected Scopes

নিচের যেকোনো পাথে পরিবর্তন এলে স্বয়ংক্রিয়ভাবে `risk_class: CRITICAL` নির্ধারিত হবে এবং **Guardian-Deep + Mandatory Human Review** সক্রিয় হবে। Source of truth: [`security/policies/protected-scopes.yml`](../../security/policies/protected-scopes.yml).

| Path | Description | Risk Class | Invariants Enforced |
|---|---|---|---|
| `services/hitl/**` | Human-in-the-Loop control logic | CRITICAL | SG-09, SG-12 |
| `backend/core/auth/**` | Authentication & session management | CRITICAL | SG-03, SG-04, SG-12 |
| `backend/core/security/**` | Security primitives (crypto, validation, sanitization) | CRITICAL | SG-01, SG-02, SG-07 |
| `.github/workflows/**` | CI/CD pipeline definitions | CRITICAL | SG-04, SG-09, SG-11 |
| `.github/scripts/pr_helper/**` | PR Helper delta/hunk scripts (bootstrap-trust critical) | CRITICAL | SG-11 |
| `docs/security/SECURITY_GUARDIAN.md` | This constitution itself | CRITICAL | SG-11 |
| `security/policies/**` | Security policy definitions | CRITICAL | SG-11, SG-14 |
| `database/migrations/**` | Tenant isolation & data schema | CRITICAL | SG-05, SG-12 |

**Consequence of `risk_class: CRITICAL`:**
1. Guardian-Deep is mandatory (Lite passing alone is insufficient).
2. Auto-merge is disabled (PR Helper Step 5 short-circuits).
3. At least one human approval is required (branch-protection rule).
4. The PR is labeled `needs-security-review` for triage visibility.

**Risk classification rules** (full table in `protected-scopes.yml`):

| Condition | Risk Class |
|---|---|
| any protected_scope touched | CRITICAL |
| auth_changed OR hitl_changed OR workflows_changed | HIGH |
| security_changed | HIGH |
| backend code_changed (non-protected) | MEDIUM |
| frontend_changed OR docs_only | LOW |

---

## 📊 Security Decision Contract

`pr-gate` কোনো অন্ধ status check হবে না। এটি নিচের standardized YAML কন্ট্রাক্ট মূল্যায়ন করে সিদ্ধান্ত নেবে। এই কনট্রাক্টটি Guardian-Deep (বা Guardian-Lite + Deep skip) দ্বারা emitted হয়ে `pr-gate`-এ artifact হিসেবে আপলোড হবে।

```yaml
guardian_decision:
  status: "PASS" | "WARN" | "REVIEW" | "BLOCK"
  risk_class: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
  protected_scope_touched: false
  baseline_existing_debt: 12
  new_findings_introduced: 0
  evidence_summary:
    confirmed_violations: []
    unverified_claims_dropped: 2
  self_modification_detected: false
```

### Decision matrix

| Condition | `status` | Auto-merge |
|---|---|---|
| `new_findings_introduced == 0` (no evidence-backed new violation) | `PASS` | ✅ Allowed (with debt report) |
| `new_findings_introduced == 0` but `unverified_claims_dropped > 0` | `WARN` | ✅ Allowed (note on PR) |
| `self_modification_detected == true` (SG-11) | `REVIEW` | ❌ Disabled — mandatory human review |
| `new_findings_introduced > 0` (with evidence) | `BLOCK` | ❌ Disabled |
| `protected_scope_touched == true` AND no human approval | `REVIEW` | ❌ Disabled |

> **Key insight (SG-10):** Pre-existing security debt (counted in `baseline_existing_debt`) does **NOT** block a PR — only **new, evidence-backed findings** introduced by the PR itself trigger `BLOCK`. This prevents the Guardian from becoming a hostage to historical debt.

---

## 🧷 Bootstrap Trust (SG-11)

### The problem

Guardian যদি নিজের কোড (e.g., `delta_analysis.py`, `pr-helper.yml`, `SECURITY_GUARDIAN.md`) পরিবর্তন করার সিদ্ধান্ত নিজে approve করে, তাহলে সেটি একটি **circular trust loop** তৈরি করে। একজন attacker (বা compromised agent) গার্ডিয়ান নিজেকে disable করে একটি malicious PR auto-merge করতে পারে।

### The rule

যদি কোনো PR নিচের যেকোনো পাথ পরিবর্তন করে:
- `.github/workflows/pr-helper.yml`
- `.github/workflows/pr-pipeline.yml`
- `.github/scripts/pr_helper/delta_analysis.py`
- `.github/scripts/pr_helper/hunk_isolation.py`
- `docs/security/SECURITY_GUARDIAN.md`
- `security/policies/protected-scopes.yml`
- `security/policies/exceptions.yml`

তাহলে:
1. **Auto-merge স্বয়ংক্রিয়ভাবে disabled** হবে (PR Helper Step 5 `if:` condition দ্বারা)।
2. `self_modification_detected: true` হবে Security Decision Contract-এ।
3. `status: REVIEW` set হবে (BLOCK নয় — কারণ পরিবর্তনটি legitimate-ও হতে পারে)।
4. **Mandatory human approval** দরকার (branch protection rule দ্বারা enforce করা)।
5. PR-এ `bootstrap-trust-review` label যুক্ত হবে।

### Why "REVIEW" and not "BLOCK"?

কিছু legitimate self-modification আছে — যেমন গার্ডিয়ানের নিজের bug fix, নতুন invariant যোগ, বা policy আপডেট। সেগুলোকে `BLOCK` করলে development আটকে যাবে। কিন্তু সেগুলো কখনো "auto-approve" হবে না — প্রতিটির জন্য একজন human maintainer-এর স্পষ্ট approval লাগবে।

### Coverage of ARCH-GAP-01

This section directly resolves:
- **GAP-06 (Bootstrap Trust)** — `protected-scopes.yml` includes `.github/scripts/pr_helper/**` as CRITICAL.
- **GAP-10 (HITL Self-Modify)** — `services/hitl/**` + `backend/core/auth/**` are CRITICAL.
- **GAP-07 (Mode Switch Auth)** — framework for explicit authorization now lives here as SG-03 + SG-09.

---

## 🔗 Related Files

| File | Purpose |
|---|---|
| [`security/policies/protected-scopes.yml`](../../security/policies/protected-scopes.yml) | Machine-readable protected path registry + risk classification rules |
| [`security/policies/exceptions.yml`](../../security/policies/exceptions.yml) | Time-bound, owner-based exception schema (SG-14) |
| [`docs/master_docs/ARCH-GAP-01-DECISION-GAP-ANALYSIS.md`](../master_docs/ARCH-GAP-01-DECISION-GAP-ANALYSIS.md) | Source GAP analysis (GAP-01 to GAP-12) |
| [`docs/security/HITL_APPROVAL_CONTRACT.md`](./HITL_APPROVAL_CONTRACT.md) | HITL approval flow contract (SG-09 enforcement) |
| [`docs/security/SECURITY_CONTROLS_BASELINE.md`](./SECURITY_CONTROLS_BASELINE.md) | Baseline controls inventory (SG-15 enforcement) |

---

## 📜 Amendment Policy

This constitution (SECURITY_GUARDIAN.md) is itself a **protected scope** under SG-11. Any amendment:
1. MUST be opened as a PR (no direct push to main, even though main has no branch protection today).
2. Triggers `risk_class: CRITICAL` → Guardian-Deep + mandatory human review.
3. MUST be accompanied by a PR body explaining which invariant is being added/clarified and why.
4. Once merged, the new SHA becomes the canonical reference for all Guardian decisions going forward.

The 15 invariants themselves are **immutable in spirit** — they may be reworded for clarity, but their enforcement semantics cannot be weakened without a successor constitution document.
