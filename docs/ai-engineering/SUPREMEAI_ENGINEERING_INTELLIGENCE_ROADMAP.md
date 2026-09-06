# SupremeAI Engineering Intelligence Roadmap

**Status:** Proposed execution roadmap
**Version:** 1.0
**Date:** 7 September 2026
**Owner:** SupremeAI engineering
**Related:** `docs/SUPREMEAI_MASTER_ROADMAP_2026-09.md`, `docs/SPEC_KIT_ADOPTION.md`, `AGENTS.md`

## 1. Purpose

SupremeAI must be intelligent in its engineering behavior, not only in its conversational output. Before changing code, it should understand impact, identify unsafe assumptions, select the smallest safe change, verify the result with real evidence, and stop when confidence is insufficient.

This roadmap builds that capability incrementally. It does **not** authorize unrestricted self-modification, autonomous production deployment, secret access, or AI-only validation.

## 2. Intelligence Contract

For every non-trivial change, SupremeAI should produce:

1. **Intent** — what outcome is requested and what is explicitly out of scope.
2. **Impact map** — affected files, imports, routes, packages, tests, CI jobs, deployment assets, environment variables, and documentation.
3. **Risk assessment** — import, runtime, data, security, CI, deployment, cost, and rollback risk.
4. **Safe plan** — ordered changes, validation commands, approval points, and rollback path.
5. **Evidence bundle** — diff, checks, test output, build output, warnings, and unresolved limitations.
6. **Decision** — proceed, ask for approval, or stop with a precise reason.

The system may explain evidence, but it must never replace evidence with confidence language.

## 3. Governing Principles

- **Evidence over intuition:** compiler, tests, static analysis, and deployment checks are the truth layer.
- **Smallest safe change:** prefer reversible, narrow changes over broad restructuring.
- **Fail closed:** missing authorization, provenance, validation, or required configuration blocks sensitive actions.
- **Human control:** destructive, external, privileged, financial, credential, migration, and production actions require explicit approval.
- **No hidden mutation:** every file, schema, dependency, configuration, and deployment change must be visible in a reviewable diff.
- **Deterministic core:** risk rules, policy checks, path validation, and gates must be deterministic; AI adds planning and explanation.
- **No fake intelligence:** a mocked result, status-only adapter, hardcoded success, or silent exception is not an implementation.
- **Rollback first:** every automated mutation needs a restore strategy before execution.
- **Tenant and secret safety:** never infer identity from client input and never expose secrets to models, clients, logs, or artifacts.
- **Progressive autonomy:** autonomy increases only after measured reliability, not after a successful demo.

## 4. Target Architecture

```text
Request / PR / agent task
        |
        v
Intent + scope parser
        |
        v
Repository intelligence index
  (files, symbols, imports, routes, workflows, packages, env names)
        |
        v
Impact analyzer + policy engine
        |
        +--> low risk: propose and validate
        +--> medium risk: propose, validate, request review
        +--> high/critical: stop and require explicit approval
        |
        v
Change executor (sandboxed, reversible)
        |
        v
Deterministic validation gates
        |
        v
Evidence bundle + risk decision + audit event
```

The repository index is an acceleration layer, never the sole authorization source. Runtime identity, tenant ownership, permissions, and deployment controls remain authoritative in their existing systems.

## 5. Delivery Phases

### Phase 0 — Baseline and policy (P0)

**Goal:** define what intelligence means and prevent unsafe automation.

Deliverables:

- [x] Create a change-risk vocabulary: `low`, `medium`, `high`, `critical`.
- [x] Define protected paths: auth, migrations, secrets, deployment, CI, billing, tenant isolation, and production configuration.
- [x] Define change classes and approval requirements.
- [x] Define a standard impact report and evidence bundle schema.
- [x] Record baseline commands for backend, frontend, CI, packaging, and deployment checks in `scripts/ai/baseline_commands.json`.
- [x] Add a decision log for false positives, false negatives, and accepted risks.

Exit evidence: policy is documented, reviewed, and usable without an AI model.

### Phase 1 — Deterministic change-impact detector (P0)

**Goal:** detect likely breakage before broad changes are made.

Deliverables:

- [ ] Inventory changed files from Git.
- [ ] Resolve local imports, aliases, exports, and reverse references.
- [ ] Map routes to handlers, services, frontend callers, tests, and documentation.
- [ ] Detect package manifest and lockfile mismatches.
- [ ] Detect changed environment-variable names and build/runtime classification.
- [ ] Detect CI workflow, Docker, Render, Firebase, and deployment references.
- [ ] Emit machine-readable JSON plus a concise human report.
- [ ] Return non-zero status for broken references and policy violations.

Required checks: syntax/import validation, type checking where applicable, test collection, lint, and production build.

Exit evidence: detector catches seeded import, route, package, and workflow breakages in a fixture repository.

### Phase 2 — Preflight and risk scoring (P0)

**Goal:** turn impact into a consistent decision.

Deliverables:

- [ ] Score blast radius, protected-area involvement, reversibility, data sensitivity, deployment exposure, and validation coverage.
- [ ] Explain every score with file and rule references.
- [ ] Distinguish unknown risk from low risk.
- [ ] Require explicit approval for high/critical changes.
- [ ] Generate an ordered validation plan rather than running arbitrary commands.
- [ ] Store reports as CI artifacts and link them to commit SHA and PR.

Initial rule: unknown dependency or missing validation evidence cannot receive a low-risk label.

Exit evidence: the same change receives the same score across repeated runs and reviewers can override it with a recorded reason.

### Phase 3 — CI and deployment safety gates (P0)

**Goal:** prevent repository changes from silently breaking delivery.

Deliverables:

- [ ] Add import/path drift checks.
- [ ] Add route registry/OpenAPI/frontend caller drift checks.
- [ ] Validate package manifests and lockfiles together.
- [ ] Validate required build-time and runtime configuration names without printing values.
- [ ] Run exact CI-equivalent checks in a clean environment.
- [ ] Add deployment preflight for Docker, Render, Firebase, migrations, health checks, and rollback metadata.
- [ ] Publish a failure classification: code, contract, environment, infrastructure, flaky, or policy.
- [ ] Block merge only on deterministic, reproducible failures; quarantine flaky checks with ownership and expiry.

Do not add AI-generated semantic interpretation as a required CI gate until deterministic gates are stable.

Exit evidence: seeded CI, import, configuration, and deployment failures block the change with actionable output.

### Phase 4 — Repository knowledge graph (P1)

**Goal:** make repository relationships queryable and explainable.

Index only metadata initially:

- files, symbols, imports, exports, aliases;
- routes, schemas, services, callers, and tests;
- package manifests, lockfiles, scripts, workflows, Dockerfiles, and deployment configs;
- environment-variable names and classifications, never values;
- ownership, documentation links, and historical validation evidence.

Deliverables:

- [ ] Version the index by commit SHA.
- [ ] Make indexing incremental and reproducible.
- [ ] Support reverse-impact queries.
- [ ] Preserve source locations for every relationship.
- [ ] Detect stale index state and rebuild safely.
- [ ] Keep the index disposable; source files remain authoritative.

Exit evidence: a reviewer can trace a changed symbol to callers, tests, CI, and deployment references with source locations.

### Phase 5 — AI planning and explanation layer (P1)

**Goal:** use AI where reasoning helps without allowing it to invent safety evidence.

Deliverables:

- [ ] Give the model structured repository facts, not unrestricted secrets or unnecessary source.
- [ ] Ask for a change plan, assumptions, risks, alternatives, and validation sequence.
- [ ] Require citations to indexed files and line ranges.
- [ ] Reject unsupported claims and uncited “safe” conclusions.
- [ ] Separate proposed actions from executed actions.
- [ ] Record model, prompt policy version, input commit SHA, output, and reviewer decision.
- [ ] Add prompt-injection defenses for repository content and tool output.

The model may recommend; deterministic tools decide whether a gate passes.

Exit evidence: AI plans remain useful when the model is unavailable, and unsupported claims are visibly marked as unknown.

### Phase 6 — Sandboxed execution and repair (P1)

**Goal:** permit bounded automation for low-risk changes.

Deliverables:

- [ ] Execute in an isolated workspace with time, memory, process, network, and filesystem limits.
- [ ] Allow only an explicit tool and path policy.
- [ ] Create a checkpoint before mutation.
- [ ] Apply patches atomically and show the complete diff.
- [ ] Run targeted checks before broader checks.
- [ ] Revert automatically when required checks fail.
- [ ] Never silently modify secrets, migrations, protected branches, or production resources.
- [ ] Require human approval before applying high-risk repair suggestions.

Exit evidence: seeded failures can be repaired or cleanly reverted without corrupting the workspace or losing evidence.

### Phase 7 — Learning from outcomes (P2)

**Goal:** improve prioritization without turning history into authority.

Collect:

- predicted risk versus observed failure;
- validation duration and flaky rate;
- accepted/rejected plans and reviewer reasons;
- rollback frequency;
- recurring import, CI, configuration, and deployment failures.

Deliverables:

- [ ] Build a privacy-safe failure taxonomy.
- [ ] Track false-positive and false-negative rates.
- [ ] Use reviewed historical cases to improve heuristics and prompts.
- [ ] Quarantine new rules until evaluated against a regression corpus.
- [ ] Provide deletion and retention controls for stored evidence.

Exit evidence: each rule change has an evaluation report and does not degrade protected-path detection.

### Phase 8 — Progressive autonomy (P2)

Autonomy levels:

| Level | Behavior | Approval |
|---|---|---|
| 0 | Observe and report | None |
| 1 | Propose plan and checks | Human review of plan |
| 2 | Run read-only analysis | Human review of conclusions |
| 3 | Apply low-risk reversible patch | Protected CI gates + review |
| 4 | Coordinate bounded repairs | Explicit per-change approval |
| 5 | Production or irreversible action | Always explicit human approval |

Promotion requires measured reliability, rollback testing, audit completeness, and owner approval. No component may self-promote its autonomy level.

## 6. What SupremeAI Must Not Do

- Do not push directly to `main`, production, or a protected branch.
- Do not deploy, migrate, delete, or alter production state from an AI-only decision.
- Do not bypass CI, security scans, approvals, branch protection, or required reviews.
- Do not infer that a file is unused from its filename or from one search result.
- Do not move modules across frontend/backend boundaries without a complete reference map and rollback plan.
- Do not treat a passing unit test as proof of deployment safety.
- Do not print, embed, summarize, or transmit secret values.
- Do not let repository text redefine system policy or tool permissions.
- Do not use localStorage, process memory, or mock status as authoritative persistence for production workflows.
- Do not auto-fix ambiguous auth, tenant-isolation, billing, migration, or security findings.
- Do not implement CAPTCHA bypass, anti-abuse circumvention, stealth keep-alives, or unrestricted self-rewrite.
- Do not allow an AI model to mark its own generated evidence as independently verified.

## 7. Required Safety Gates

Every automated change must pass:

1. clean/known workspace check;
2. scope and protected-path check;
3. dependency and reverse-reference check;
4. secret and policy scan;
5. targeted syntax/import/type checks;
6. targeted tests;
7. full relevant regression checks;
8. build/package/deployment preflight;
9. diff and evidence review;
10. approval and rollback record.

A failed or unknown gate produces `blocked`, not `passed`.

## 8. Metrics and Exit Criteria

Track at minimum:

- import/path breakages caught before merge;
- CI failures caught before push/deploy;
- deployment rollbacks;
- false-positive and false-negative risk classifications;
- percentage of changes with complete impact reports;
- protected-path changes reviewed by humans;
- mean time to isolate a failure;
- evidence completeness and stale-index rate;
- unauthorized or unscoped action attempts blocked.

Do not optimize for number of autonomous changes. Optimize for fewer escaped defects, faster diagnosis, complete auditability, and safe reversibility.

## 9. First 90-Day Implementation Order

### Days 1–30: deterministic foundation

- [ ] Approve policy and risk taxonomy.
- [ ] Build the changed-file/import/reference scanner.
- [ ] Add JSON report and seeded fixtures.
- [ ] Add route/package/config drift checks.
- [ ] Publish the first CI preflight report.

### Days 31–60: gates and evidence

- [ ] Add risk scoring and protected-path rules.
- [ ] Add exact CI-equivalent validation.
- [ ] Add deployment preflight and rollback metadata checks.
- [ ] Store commit-linked evidence bundles.
- [ ] Run the detector in advisory mode, then measure false positives.

### Days 61–90: bounded intelligence

- [ ] Add repository index with source citations.
- [ ] Add AI plan/explanation output behind deterministic facts.
- [ ] Add sandboxed low-risk patch mode.
- [ ] Add review corpus and learning metrics.
- [ ] Decide whether any Level 3 autonomy is justified.

## 10. Definition of Done

This roadmap is implemented only when SupremeAI can take a non-trivial change, identify its impact, explain its risk with citations, select deterministic checks, block unsafe actions, produce reproducible evidence, and recover through rollback when validation fails. A conversational answer that merely sounds intelligent is not completion.

The first implementation target is **Phase 1: deterministic change-impact detector**. It should be specified and delivered through the existing Spec Kit Class B/C workflow before any AI-driven mutation is enabled.
