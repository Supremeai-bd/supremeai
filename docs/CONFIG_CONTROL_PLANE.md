# Configuration Control Plane — Phase 3

PR #107 is treated as **Phase 2 enforcement**, not the final architecture. It fixed the Python 3.11 dynamic-loader failure and restored the registry CI check.

## Current source of truth

`backend/core/config_classification.py` is the canonical vocabulary: names, aliases, classes, scopes and declared sources. It intentionally contains metadata only and no secret values.

`secrets_registry.yaml` is still a large legacy inventory and must **not** become a competing authority. Its entries currently include deployment-specific criticality and historical scan notes.

## Phase 3 delivered by this patch

1. `backend/core/config_control_plane.py` provides a facade over the canonical registry.
2. Runtime health reports only presence/metadata — never secret values.
3. The facade exposes one contract for future CI, admin and external provenance adapters.
4. `scripts/ci/check_config_control_plane.py` provides the stricter structural gate needed before unknown sensitive ENV references can become CI failures.

The existing workflow already invokes the canonical registry validator and deployment hardcode policy.

## Remaining migration work

### P0 — canonicalization
- Expand the canonical registry until every **currently used** ENV key has an explicit classification.
- Add stable IDs, owner, lifecycle (`active|deprecated|removed`), and validation semantics to each spec.
- Keep aliases explicit; never silently duplicate canonical keys.

### P1 — legacy registry migration
- Convert `secrets_registry.yaml` into a generated/compatibility view of the canonical registry.
- Preserve deployment criticality as metadata, not as a second key inventory.
- CI should eventually fail when a newly introduced key is absent from the canonical registry.

### P1 — AI/provider alignment
- Make `backend/services/dynamic_ai/provider_registry.py` and `backend/brain/model_registry.py` consume configuration metadata by canonical key instead of independently describing credential names.
- Provider records should reference config IDs and capabilities, not copy secret definitions.

### P1 — integration alignment
- `backend/core/integrations/registry.py` should reference canonical configuration IDs for its `config_note` requirements. It owns integration metadata and runtime state, so it remains a consumer, not the configuration authority.

### P1 — provenance
Implement adapters with a common interface:

`declared → runtime-env → vault → deployment → verified`

Infisical and Render adapters must return only key presence/status, source, timestamp and verification error class. Never return secret values to CI or Admin UI.

### P1 — admin health
Expose the control-plane health snapshot through the existing admin dashboard/health stack. The repository already has health aggregation, admin dashboard routes and admin service components, so this should be an integration rather than a new dashboard subsystem.

### P1 — hardcoded scanner
Make the existing deployment hardcode scanner registry-aware. A hardcoded URL/value should be rejected only when the canonical contract says it must be externally configured; documented build-time constants remain allowed.

### P2 — automatic new-ENV gate
After the registry reaches full current-state coverage, compare the PR diff against the canonical key set. A new security-sensitive ENV reference must fail CI unless the same PR adds/updates its canonical spec.

## Target architecture

```text
                    Canonical Registry
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
        Runtime Config    CI          Admin
             │             │             │
             ▼             ▼             ▼
          Backend      Drift Gate    Health View
                           │
                           ▼
                    Infisical / Render
```

The key architectural rule is: **one vocabulary, many consumers**. Provider registries, integration registries, CI, runtime configuration and admin observability must reference the canonical contract rather than recreate it.
