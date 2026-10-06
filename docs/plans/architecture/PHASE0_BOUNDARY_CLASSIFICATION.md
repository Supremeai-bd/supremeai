# Phase 0 — Boundary Classification Matrix

**Status:** Proposed · **Roadmap ref:** `SUPREMEAI_REPOSITORY_SEPARATION_AND_EVOLUTION_ROADMAP.md` §3, §12
**বাংলা:** এই ম্যাট্রিক্সই Phase 0 গেট — এটা ছাড়া কোনো repo-তে কোড মুভ করা যাবে না।

## 1. Verified dependency probes (evidence, not guesswork)

| Probe | Result | Consequence |
|---|---|---|
| `frontend/src` → direct backend imports | **0** | Studio extraction is LOW-RISK (Phase 2) |
| `infrastructure/mcp-control-plane` → external imports | **0** | Self-contained; natural Phase 3 extraction |
| `backend/core` → `adaptive_engine` | 8 files | Core stays in monolith (Phase 5, high-risk) |
| `backend/core` → `brain` | 14 files | Core stays in monolith (Phase 5, high-risk) |
| Contract raw material | `packages/shared-types`, `shared/protos/supreme_engine.proto` | SDK seeding material (Phase 1) |

## 2. Top-level module classification (🟢 Open / 🟡 Review / 🔴 Proprietary / ⛔ Restricted)

| Module | Class | Target repo | Phase | Notes |
|---|---|---|---|---|
| `frontend/` (571 files) | 🟢 | supremeai-studio | 2 | 0 backend imports verified |
| `packages/shared-types` | 🟢 | supremeai-sdk | 1 | pure types |
| `packages/design-tokens`, `ui-components` | 🟢 | supremeai-studio | 2 | UI-only |
| `packages/core-infrastructure`, `shared-services` | 🟡 | review → sdk or core-infra | 1 | interface split needed |
| `shared/protos/*.proto` | 🟢 | supremeai-sdk | 1 | seeded already |
| `packages/scripts` | 🟡 | review | — | mixed tooling |
| `infrastructure/mcp-control-plane` | 🔴 | supremeai-mcp-control-plane | 3 | self-contained verified |
| `apps/mission-control` | 🟡 | hybrid (shell public, tower private) | later | roadmap §9 |
| `backend/api`, `backend/database` | 🔴 | supremeai-core | 5 | after internal boundaries |
| `backend/core`, `backend/brain` | 🔴 | supremeai-core | 5 | coupled: 8+14 files |
| `backend/adaptive_engine` | 🔴 | supremeai-evolution | 6 | most sensitive after core |
| `backend/memory`, RAG internals | 🔴 | supremeai-memory | 7 | data has own tenancy rules |
| deployment/secret configs | ⛔ | supremeai-infrastructure | 4 | Infisical only |
| `docs/`, `skills/`, examples | 🟢 | supremeai-open | 8 | only what teaches |

## 3. Do-not-extract list (explicit)

1. `backend/core` + `backend/brain` + `backend/adaptive_engine` — live coupling verified; extract only after `public-contracts/ core/ orchestration/ routing/ execution/ verification/` internal split stabilizes (roadmap §17).
2. `apps/mission-control` privileged routes — admin-only commands stay with the tower (roadmap §9).
3. Anything ⛔ — never moves by repo split; moves by vault.

## 4. Ecosystem repos — live status (updated post-extraction)

| Repo | Visibility | Status |
|---|---|---|
| `paykaribazaronline/supremeai-sdk` | 🟢 public | **Phase 1 DONE**: `types/` (shared-types), `api-schemas/openapi.yaml` (11k-line real spec), `protos/`, `@supremeai/sdk` v0.1.0 |
| `paykaribazaronline/supremeai-core` | 🔴 private | Charter + BOUNDARY.md (code extraction Phase 5 — blocked per §3) |
| `paykaribazaronline/supremeai-studio` | 🟢 public | **Phase 2 DONE**: frontend at root + 5 workspace packages + pnpm workspace + CI (typecheck+lint) |
| `paykaribazaronline/supremeai-mcp-control-plane` | 🔴 private | **Phase 3 DONE**: 148 files — Dockerfile, render.yaml, 25+ test files, secret-scanned (0 hardcoded) |
| `paykaribazaronline/supremeai-infrastructure` | 🔴 private | Charter only — Phase 4 deferred (⛔ every config needs value review) |

## 5. Next gates (roadmap §41 order)

- [ ] Phase 1: SDK contract layer populated from `packages/shared-types` + API schemas
- [ ] Phase 2: Studio extraction (low-risk: 0 backend imports)
- [ ] Phase 3: MCP Control Plane extraction (self-contained verified)
- [ ] Phase 4: Infrastructure repo populated with deploy configs (⛔ review each)
- [ ] Phase 5+: Core — blocked by §3 list above


---
**Claim:** Refs #3 (assigned: paykaribazaronline) · **Evaluator re-run trigger:** template-v2 compliant body + conventional title `docs(plans): …` · issue #3 reopened (metadata gap resolved)
