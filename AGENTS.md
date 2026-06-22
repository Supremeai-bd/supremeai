# SupremeAI 2.0 — AGENTS.md
_Status: ACTIVE_
_Last Updated: 2026-06-22_

---

## Project Overview

SupremeAI 2.0 is a multi-cloud AI orchestration platform built on FastAPI with React/Vite frontend, Flutter mobile, and VS Code extension. It targets zero-cost operation through aggressive free-tier utilization across 8+ AI providers.

## Core Directories

| Directory | Purpose |
|-----------|---------|
| `backend/` | FastAPI backend (Python 3.11+, Poetry) |
| `apps/studio-client/` | React/Vite web client |
| `apps/mobile/` | Flutter mobile app |
| `tools/vscode-extension/` | VS Code extension |
| `admin/` | Admin god mode |
| `skills/` | Dynamic skills registry |
| `evolution/` | Self-learning engine |
| `infrastructure/` | Terraform, Cloudflare, Firebase |
| `docs/` | Project documentation |
| `scripts/` | Helper scripts (bootstrap, deploy, worktrees, runner, benchmark) |

## Key Commands

```bash
# Bootstrap environment
python scripts/bootstrap_env.py

# Setup worktree for isolated task
bash scripts/worktrees/setup_worktree.sh create <task-name>

# Run task in worktree
bash scripts/worktrees/run_task.sh <task-name> pytest

# Setup local or docker runner
bash scripts/runner/setup_runner.sh local

# Create isolated test environment
bash scripts/testenv/setup_test_env.sh create

# Run performance benchmark
python scripts/benchmark/perf_benchmark.py --url http://127.0.0.1:8000 --requests 50

# Backend dev server
pnpm backend:dev

# Run tests
pnpm backend:test
```

## Coding Standards

- Python: Ruff lint, MyPy typecheck, pytest tests
- TypeScript: ESLint, Prettier, Vitest
- No hardcoded secrets
- All admin endpoints require JWT admin role
- Use `settings` from `core.config` (single source of truth)
- Test coverage target: >= 38%

## Branching Strategy

- `main` / `master` — production
- `develop` — integration
- `feature/*` — new features
- `fix/*` — bug fixes
- `agent/*` — Agent Manager worktrees

## CI/CD

- GitHub Actions: `.github/workflows/monorepo_ci_cd.yml`
- Change detection via `dorny/paths-filter`
- Backend: Poetry + pytest + coverage
- Frontend: pnpm + turbo + build
- Deploy: Cloud Run (GCP) + Firebase Hosting
- Notify: Discord webhooks

## Next Actions

1. Run `kilo.json` commands to bootstrap
2. Execute rerun checklist in `docs/02-admin/rerun-checklist.md`
3. Separate test env via `scripts/testenv/setup_test_env.sh`

---

_Generated for SupremeAI 2.0 — Admin Plan Execution_
