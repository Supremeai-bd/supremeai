# Module Rationalization Queue

**Date:** 2026-09-11
**Source:** `MODULES_LIST.md` (224 entries; 102 marked partially wired)
**Status:** Evidence classification only. No modules were deleted, renamed, or rewired.

## Key finding

The current dormant count is not equivalent to unused production capability. The catalog includes test files as modules (for example `frontend/src/services/*.test.ts` and `frontend/src/store/*.test.ts`) and reports callers from vendored paths such as `backend/services/scraper/.venv`. These entries must be normalized before any deletion or wiring decision.

## Classification policy

| Class | Definition | Action |
|---|---|---|
| `catalog-error` | Test fixture, test-only file, generated artifact, vendored dependency, or directory aggregate incorrectly treated as a production module. | Remove from the production module count through the catalog generator; retain the file. |
| `core-dormant` | Importable production capability with no active inbound caller and strategic relevance to central control, tenant safety, billing, memory, or execution. | Assign an owner and add a governed entrypoint or explicit roadmap decision. |
| `candidate-reuse` | Dormant capability that overlaps an existing operational capability. | Route through the existing registry/control plane; do not add a parallel entrypoint. |
| `environment-dependent` | Valid capability whose activation depends on an external service or host runtime. | Keep cataloged with prerequisite and verification command. |
| `archive-candidate` | Dormant capability with no caller, no tests, no owner, and no current roadmap dependency. | Require explicit approval before archive/removal. |

## Immediate catalog corrections

These should be fixed in the generator/reporting layer before evaluating the 102 entries:

1. Exclude `*.test.ts`, `*.test.tsx`, and test-only Python files from production module counts.
2. Exclude vendored trees such as `.venv`, `node_modules`, generated clients, and build output from caller/test evidence.
3. Distinguish a directory aggregate from an executable module.
4. Record `verified_at`, `verification_command`, `owner_circle`, and `decision` for every production entry.
5. Preserve the current 224-entry list as historical evidence until the corrected report is generated.

## First-pass action queues

### Candidate reuse / central-control review

- `tools/discovery_fabric`
- `tools/gap_finder`
- `tools/gap_miner`
- `tools/intelligence_extensions`
- `tools/knowledge_squeezer`
- `tools/solution_synthesizer`
- `backend/tools/ensemble_router.py`
- `backend/tools/parallel_agent_executor.py`
- `backend/tools/resource_catalog.py`
- `backend/tools/mcp/mcp_cloud_deploy.py`
- `backend/tools/mcp/mcp_github_cicd.py`
- `backend/tools/mcp/mcp_neon.py`
- `backend/tools/mcp/mcp_observability.py`
- `backend/tools/mcp/mcp_workspace.py`

These capabilities should be evaluated against the existing MCP control plane, capability registry, unified router, and tool policy before new routes are created.

### Environment-dependent verification

- `backend/tools/launchdarkly_agent_adapter.py`
- `backend/tools/devops/docker_sandbox.py`
- `backend/tools/social/telegram_bot.py`
- `backend/tools/mcp/mcp_telegram.py`

Keep these available, but document prerequisites and run explicit smoke checks in the environment-health workflow.

### Specialized capability review

- `backend/tools/localization/*`
- `backend/tools/media/music_generator.py`
- `backend/tools/media/presentation_generator.py`
- `backend/tools/media/threed_model_generator.py`
- `backend/tools/media/video_generator.py`
- `backend/tools/creative/*`
- `backend/tools/learning/rlhf_pipeline.py`
- `backend/tools/security_tools/multi_account_rotator.py`

These are not safe deletion candidates. Each needs an owner-circle decision: integrate, retain as an explicitly invoked capability, or archive after dependency and roadmap review.

### Frontend test-only false positives

The following catalog pattern should be removed from production-module accounting rather than wired into the application:

- `frontend/src/services/*.test.ts`
- `frontend/src/store/*.test.ts`
- `frontend/src/services/test_budget_check.test.ts`

The associated implementation modules must be evaluated independently using actual imports and route/component callers.

## Verification sequence

1. Update the catalog generator filters and schema; do not change runtime behavior.
2. Regenerate the catalog and compare counts with the historical 224-entry report.
3. Review all count changes and false-positive removals.
4. Assign owner circles and decisions only to remaining production entries.
5. Open implementation work for the highest-reuse candidates; archive only with explicit approval.

## Exit criteria

Phase 2 is complete when the catalog is generated from reproducible filters, every production module has a verification timestamp and owner circle, dormant labels distinguish no-caller from not-enabled, and no removal decision is made solely from a zero-caller count.
