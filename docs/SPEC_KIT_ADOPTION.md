# Spec Kit Adoption — SupremeAI Engineering Governance

**Status:** Phase 1 (Bootstrap) complete · **Adopted:** 2026-08-29

This document records how [GitHub Spec Kit](https://github.com/github/spec-kit)
is adopted as a lightweight, reviewable, agent-facing software-development
governance layer for SupremeAI. It defines artifact ownership, feature
classification, quality gates, CI policy, and the pilot plan.

**Core decision:** *Adopt the process, not the runtime.* Spec Kit is a
development/process layer for Spec-Driven Development (SDD). It MUST NOT add a
backend service, database, queue, API endpoint, or Render service, and has zero
production runtime dependency impact.

---

## 1. Tooling & Version Pin

| Item | Value |
|---|---|
| Spec Kit CLI | `specify-cli==1.0.0` (git tag `v1.0.0`, commit `bca6790`) |
| Installed via | `uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@v1.0.0` |
| Agent integration | `cline` (IDE-based) |
| Script type | `ps` (PowerShell — this project's primary dev environment is Windows) |
| Upgrade policy | Review releases before adopting; update the pin above and re-run `specify init` refresh deliberately |

The CLI belongs to development/agent tooling only. It MUST NOT be added to
`backend/requirements.txt`, `frontend/package.json`, production Docker runtime
images, or Render runtime services.

## 2. Baseline Record

| Item | Value |
|---|---|
| Baseline commit | `b092e664ba` on `main` |
| Working tree at adoption | Clean (0 modified files) |
| Files added by init | `.specify/` and `.clinerules/` only — no tracked file was modified |
| Preserved untouched | `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, existing `docs/`, CI/security policy |

## 3. Directory Structure

```
.specify/                     # Spec Kit tooling (templates, scripts, memory)
│   ├── memory/constitution.md   # SDD engineering constitution
│   ├── templates/               # spec/plan/tasks/checklist/constitution templates
│   ├── scripts/powershell/      # PS workflow scripts (ps profile)
│   └── integrations/, workflows/
.clinerules/workflows/        # /speckit.* slash-command workflows (Cline)
specs/                        # Feature artifacts (created per feature, flow-forward)
docs/SPEC_KIT_ADOPTION.md     # This file
```

Note: `.specify/feature.json` (active-feature pointer) is machine-local and
excluded via `.specify/.gitignore`; the workflow state resolves from it rather
than from the Git branch.

`.clinerules/` is committed: it contains only the shared `/speckit.*` workflow
definitions (no credentials — Cline does not store auth tokens in
`.clinerules/`). Re-evaluate if that ever changes.

## 4. Artifact Ownership

Avoid duplicate sources of truth. Each artifact has exactly one authority:

| Artifact | Primary purpose | Authority |
|---|---|---|
| `AGENTS.md` | AI-agent operating behavior | Agent behavior |
| `.specify/memory/constitution.md` | SDD engineering principles | Feature planning constraints |
| `specs/NNN-name/spec.md` | Feature WHAT/WHY | Feature requirements |
| `specs/NNN-name/plan.md` | Feature HOW | Technical design |
| `specs/NNN-name/tasks.md` | Work breakdown | Implementation sequence |
| `specs/NNN-name/checklist.md` | Requirement-quality review | Reviewer |
| `docs/architecture/*` | Persistent architecture | Architecture record |
| `docs/operations/*` | Runbooks | Operations |
| `README.md` | Public/project overview | Project documentation |
| `CONTRIBUTING.md` | Contribution process | Contributor governance |

## 5. Feature Classification Policy

| Class | Examples | Required process |
|---|---|---|
| **A — Tiny** | copy change, small CSS fix, simple typo | Normal PR process |
| **B — Bounded Feature** | new UI module, new API endpoint, provider adapter, storage feature | `specify → plan → tasks → implement → converge` |
| **C — Production/Architecture** | multi-tenancy, billing, auth/RBAC changes, new third-party platform, database/deployment architecture, major memory/reliability work | Full SDD: `constitution → specify → clarify → checklist → plan → tasks → analyze → implement → converge` |

Do not force full SDD for a typo or trivial dependency change.

## 6. Quality Gate Chain (Class C)

```
[1] Constitution check → [2] Specification → [3] Clarification →
[4] Requirement checklist → [5] Architecture plan → [6] Tasks →
[7] Analyze → [8] Implementation → [9] Tests/security/CI →
[10] Converge → [11] Human review → [12] Merge/deploy
```

`/speckit.analyze` is read-only and MUST run before implementation of major work.
`/speckit.converge` MUST run after implementation and before a Class C feature is
declared complete; if it appends remediation tasks, implement them and converge
again.

## 7. Required Spec Content

Every Class B/C `spec.md` MUST include: user stories; functional requirements with
stable IDs; acceptance scenarios; security constraints; tenant/isolation
requirements (where relevant); performance/resource constraints; error/failure
behavior; configuration behavior; backward-compatibility constraints; success
criteria; edge cases. Concrete library choices belong in `plan.md`, not `spec.md`.

## 8. Naming & Traceability

Feature IDs: `001-dynamic-production-configuration`, `002-memory-crisis-remediation`,
… Use the ID in the feature directory, PR title/description, and task references
where useful. The active feature is tracked via `.specify/feature.json`
(machine-local), not merely by Git branch. Branches keep the existing
`feature/…` convention from `CONTRIBUTING.md`; Spec Kit's optional git extension
is not required.

## 9. Security Rules for Spec Artifacts

Specs are repository artifacts. NEVER store API keys, secrets, passwords, private
credentials, production tokens, or Infisical secret values in them. Reference
configuration by name (`Use N8N_BASE_URL from deployment configuration`) — never
by value.

## 10. Brownfield Compatibility Commitments

- **Dynamic configuration:** plans MUST classify new config as
  `required | optional | conditional | secret | public | runtime | build-time`.
- **Multi-tenancy:** specs touching customer data MUST answer tenant/user scope,
  resource owner, shared resources, cross-tenant policy, cache/storage key scope,
  audit and telemetry scope.
- **AI/LLM features:** missing optional provider key → `NOT_CONFIGURED`, never a
  system failure.
- **Ollama:** always optional, user-controlled, backend MUST NOT depend on it.
- **Free tier:** no unnecessary process, cache, or service multiplication.

## 11. CI Policy

Phase 1 (now): CI runs the existing standard checks only. No Spec Kit validation.

Phase 2 (later, only if valuable): verify feature metadata validity, required
artifacts exist for Class B/C PRs, no secrets in spec artifacts, markdown
structure valid. Phase 3: traceability/analyze/converge evidence. Do not require
AI-generated semantic interpretation inside CI until the process has stabilized.

## 12. Rollout Status

### Phase 1 — Bootstrap ✅ (2026-08-29)

- [x] Clean reviewable baseline (`main` @ `b092e664ba`)
- [x] Pinned Spec Kit CLI v1.0.0 installed
- [x] `specify init --here --force --integration cline --script ps --non-interactive`
- [x] All generated files reviewed; no destructive changes; `AGENTS.md` preserved (additive cross-link only)
- [x] Constitution created from actual project rules (`.specify/memory/constitution.md` v1.0.0)
- [x] `AGENTS.md` cross-linked (SDD section, operating rule, obligations)
- [x] Artifact ownership documented (this file)

### Phase 2 — Pilot ⏳

Run the full flow once for `001-dynamic-production-configuration`
(Production Configuration & Dynamic Endpoint Hardening — frontend/backend endpoint
configuration, Firebase generated config, CORS source of truth, production host
configuration, Infisical/environment mapping, optional provider configuration
semantics, artifact validation, service replacement verification):

```
/speckit.specify → /speckit.clarify → /speckit.checklist → /speckit.plan →
/speckit.tasks → /speckit.analyze → /speckit.implement → /speckit.converge
```

Alternative pilot if prioritized: `002-memory-crisis-remediation`.

### Phase 3 — Operationalize ⏳

- [ ] Class A/B/C policy adopted in day-to-day review
- [ ] Contribution guidance updated if needed
- [ ] Optional CI validation (see §11)
- [ ] Future agents onboarded via `AGENTS.md` → constitution chain

### Phase 4 — Scale ⏳

Apply to architecture/security changes, major integrations, billing/multi-tenancy
work; add more CI enforcement only after measuring value.

## 13. Definition of Done (Adoption)

- [x] `.specify/` initialized and reviewed
- [x] Constitution reflects actual SupremeAI principles
- [x] `AGENTS.md` and constitution do not conflict
- [x] Existing docs intact with clear ownership
- [ ] First bounded feature implemented through the SDD flow (Phase 2)
- [x] Policy: analyze before major work; converge after
- [x] Feature artifacts location defined (`specs/`, flow-forward)
- [x] No production runtime dependency on Spec Kit
- [x] No secrets in spec artifacts (rule in force)
- [x] SDD policy documented; future AI agents know when to use Spec Kit
