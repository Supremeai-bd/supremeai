# Configuration Registry Migration — Evidence-First Plan

## Decision

Do **not** auto-classify the 118 unclassified runtime keys with a name heuristic and inject them directly into `config_classification.py`.

The proposed heuristic is too weak for a configuration control plane:

- `KEY`, `TOKEN`, `SECRET`, `PASSWORD`, and `DSN` are useful secrecy hints, but naming alone is not proof.
- A key without those substrings is not necessarily public.
- `optional=True` by default can hide a production-critical dependency and turn a real outage into a configuration-health false negative.
- `ConfigClass` currently combines orthogonal dimensions (`REQUIRED`, `OPTIONAL`, `CONDITIONAL`, `SECRET`, `PUBLIC`), so guessing both secrecy and requiredness independently is error-prone.

The canonical registry should become a **control-plane contract**, not a generated guess list.

## Current repository reality

`backend/core/config_classification.py` is already the canonical metadata module and explicitly states that it contains names, aliases, classification and source policy, not secret values.

`scripts/ci/check_config_contract.py` discovers runtime aliases from Pydantic `Field(validation_alias=...)` declarations and fails on any alias absent from the canonical registry.

The runtime configuration surface is materially broader than the current registry. `backend/core/config_fields.py` contains many environment aliases with concrete defaults, including operational limits, security settings, provider URLs, model names, paths and credentials. Therefore the registry must be reconciled against runtime semantics rather than generated from key spelling.

## Target architecture

```text
                 Canonical Config Contract
                           │
             ┌─────────────┼──────────────┐
             ▼             ▼              ▼
        Runtime Model      CI           Admin
             │             │              │
             ▼             ▼              ▼
       typed settings   drift gate   health/diagnostics
                           │
                           ▼
                    Provenance Adapters
                      /             \
                 Infisical         Render
```

One vocabulary, many consumers. Provider registries, integration registries and legacy inventories reference canonical config IDs; they do not redefine configuration semantics.

## Phase 0 — inventory, not mutation

Generate an evidence report for every runtime configuration key from:

1. Pydantic `Field(validation_alias=...)` declarations.
2. Direct `os.getenv`, `os.environ.get`, and `os.environ[...]` references.
3. Frontend `import.meta.env.*` references.
4. Existing `config_classification.py` entries and aliases.
5. `secrets_registry.yaml` entries.
6. Provider/integration registries that reference configuration names.
7. Deployment manifests/workflows and environment declarations.

The report must identify the owning source file and evidence used for each key.

## Phase 1 — classify from evidence

For each key determine these dimensions independently:

### Exposure
- `secret`: disclosure grants access or enables credential abuse.
- `sensitive`: operational/security data that should not be exposed in public health output.
- `public`: safe to ship to a browser/build artifact.

### Requirement
- `required`: startup/runtime cannot operate correctly without it.
- `optional`: feature can remain disabled or has a safe, intentional default.
- `conditional`: required only when a feature/deployment mode is enabled.

### Source/provenance
Use actual provenance rather than assuming ENV:
- `env`
- `vault`
- `deploy`
- `build`
- `generated`
- `code_default`

### Scope
Record where the value is valid: backend, frontend, CI, deploy, local, provider, integration, etc.

## Phase 2 — make the schema orthogonal

Before adding all missing entries, evolve `ConfigSpec` so security classification is not coupled to requirement classification.

Recommended conceptual model:

```text
ConfigSpec
├── name / stable_id
├── aliases
├── exposure: public | sensitive | secret
├── requirement: required | optional | conditional
├── sources[]
├── scopes[]
├── owner
├── lifecycle: active | deprecated | removed
├── required_when
├── validation
└── description
```

Keep backward-compatible `ConfigClass` values temporarily if needed, but stop encoding multiple independent axes in one set as the long-term model.

## Phase 3 — canonical migration

Add entries in small, reviewable groups:

1. core runtime/network/security;
2. database/cache/storage;
3. authentication and secrets;
4. AI/provider configuration;
5. integrations;
6. frontend/build variables;
7. deployment/CI variables;
8. legacy compatibility aliases.

Every entry must have evidence. A generated candidate may accelerate editing, but it must not be considered authoritative until reviewed.

## Phase 4 — legacy registry reconciliation

Do not maintain `secrets_registry.yaml` as a second authority.

After coverage reaches 100%:

- map every legacy entry to a canonical config ID;
- preserve useful legacy metadata as fields in the canonical model;
- generate a compatibility/export view if existing tooling still requires YAML;
- fail CI when a new legacy-only key appears.

## Phase 5 — registry consumers

Update consumers to reference canonical IDs:

- dynamic AI/provider registry;
- model registry;
- integration registry;
- deployment scanners;
- runtime config loaders;
- admin health views.

Do not copy secret names into each registry.

## Phase 6 — provenance verification

Introduce a provider-neutral provenance interface:

```text
DECLARED → RUNTIME_ENV → VAULT → DEPLOYMENT → VERIFIED
```

Infisical and Render adapters should report only metadata such as presence, source, verification timestamp and error category. Secret values must never enter CI logs, admin responses, or health telemetry.

## Phase 7 — enforcement

Only after current-state coverage is complete:

- new security-sensitive ENV reference without a canonical entry → CI failure;
- new canonical key without runtime/deployment evidence → CI warning or failure depending on lifecycle;
- stale canonical key → warning, then failure after deprecation window;
- legacy registry divergence → CI failure;
- provider/integration duplicate credential definitions → CI failure.

## What the original plan gets right

- Start from the CI-discovered missing-key set.
- Automate extraction and report generation.
- Re-run the contract validator after migration.
- Run formatting/lint checks.

## What must change

Automation should **generate an evidence report and candidate classifications**, not directly mutate the canonical registry. Requiredness, secrecy, source and scope need runtime/deployment evidence.

The real success criterion is not simply `0 unclassified keys`; it is:

```text
0 unclassified runtime keys
+ 0 unexplained legacy keys
+ 0 duplicate authorities
+ 0 provenance contradictions
+ CI green
```

That is the point at which the registry becomes a real Configuration Control Plane rather than another inventory file.
