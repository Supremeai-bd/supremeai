# SupremeAI Root-Level & Repository Organization Plan

## Goal

Keep the repository visually clean and predictable so a human developer or AI agent can immediately understand where code, documentation, tooling, deployment assets and experiments belong.

## Current observation

The repository root contains many project/tooling files and multiple AI-agent/editor configuration areas. The tree also contains substantial `.agents` and `.clinerules` material. This is useful, but root-level clutter should be controlled rather than allowing every temporary script or generated artifact to accumulate there.

## Target root

Aim for a root that looks approximately like:

```text
supremeai/
├── README.md
├── LICENSE
├── AGENTS.md                         # if a root-level agent contract is required
├── pyproject.toml / backend config
├── package.json / workspace config   # only if truly root workspace config
├── docker-compose.yml                # if used for local orchestration
├── Dockerfile                        # only if root build requires it
├── .gitignore
├── .dockerignore
├── .env.example
├── .github/
├── .agents/                          # AI-agent system/config
├── .clinerules/                      # Cline-specific rules if retained
├── .devcontainer/
├── backend/
├── frontend/
├── packages/
├── database/
├── scripts/
├── infra/
├── docs/
├── tests/
├── knowledge/
└── tools/                            # developer-only utilities when appropriate
```

## Root-level rule

A file should stay at root only if a standard tool expects it there, it is a primary project manifest, or it is a top-level project contract.

Examples that normally belong at root:

- README
- LICENSE
- package/workspace manifest
- Python project manifest
- standard ignore/config files required by tooling
- primary Docker/deployment entrypoint when tooling expects it
- top-level agent contract when intentionally supported

## Move candidates

### 1. One-off scripts

Move operational/developer scripts into:

```text
scripts/
├── dev/
├── ci/
├── deploy/
├── maintenance/
├── migration/
└── audit/
```

Do not delete a script because it looks old. Move it first and preserve its purpose/documentation.

### 2. Deployment/infrastructure assets

Use:

```text
infra/
├── render/
├── docker/
├── cloud/
└── environments/
```

Keep `.github/workflows/` for GitHub Actions only.

### 3. Documentation

Use:

```text
docs/
├── architecture/
├── operations/
├── security/
├── development/
├── audits/
├── decisions/
├── refactor/
└── archive/
```

Historical reports should be archived rather than mixed with active developer instructions.

### 4. Tests

Keep tests close to their domain when practical, but use a predictable top-level integration/e2e structure:

```text
tests/
├── integration/
├── e2e/
├── security/
├── contracts/
└── fixtures/
```

Do not move tests blindly; preserve discovery configuration.

### 5. Knowledge assets

Keep reusable knowledge/seed corpora under `knowledge/`. Large generated datasets should not be scattered through source directories.

## AI-agent/editor configuration

Do not automatically merge `.agents`, `.clinerules`, `.cursor*`, `.gemini`, etc. Different tools may require their own conventions.

Instead:

1. Identify which configuration is active.
2. Identify duplicated rules.
3. Create one canonical project policy.
4. Keep tool-specific adapters thin.
5. Never delete agent instructions without human review.

## Naming rules

- Use descriptive, stable names.
- Avoid names such as `final`, `new`, `temp`, `test2`, `old`, `backup`, unless they are explicitly historical/archive labels.
- Prefer domain names over implementation names.
- Keep one naming convention per language.

## Organization workflow

For every root-level item:

```text
Identify purpose
   ↓
Check tool requirements
   ↓
Check references/config/scripts
   ↓
Choose canonical folder
   ↓
Move (do not delete)
   ↓
Fix references
   ↓
Run CI/tests
   ↓
Document exceptional cases
```

## Important: do not over-organize

Do not create ten nested folders for three files. Folder structure must reduce cognitive load, not increase it.

Rule of thumb:

> Create a folder when it represents a stable domain or contains enough related assets to justify a boundary.

## Final cleanliness target

A developer opening the repository root should be able to answer within seconds:

- Where is frontend?
- Where is backend?
- Where are capabilities?
- Where are tests?
- Where are deployment scripts?
- Where is infrastructure?
- Where is documentation?
- Where are AI-agent rules?
- Where are knowledge assets?

If the answer requires searching the entire repository, organization is not finished.

## Safety rule

This document is an organization plan, not a deletion plan. **No dead-code removal is authorized by this plan.** Any uncertain asset remains preserved and may be placed under an appropriate active, experimental, archive, or review area only after its purpose is understood.
