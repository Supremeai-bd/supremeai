# SupremeAI — Multi-Platform Workspace Implementation Roadmap

> **Companion Document to:** [`MULTI_PLATFORM_AGENT_WORKSPACE_PLAN.md`](MULTI_PLATFORM_AGENT_WORKSPACE_PLAN.md)  
> **Status:** Active Roadmap · Phased Delivery  
> **Target:** Zero Local Compute Bottleneck · Multi-Account Capacity Scheduling

---

## 1. Executive Implementation Overview

This roadmap details the concrete milestones, engineering contracts, and file deliverables required to operationalize the Multi-Platform & Multi-Account Workspace ecosystem.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             DELIVERY PHASES                                 │
├──────────────┬──────────────┬──────────────┬──────────────┬─────────────────┤
│   Phase 1    │   Phase 2    │   Phase 3    │   Phase 4    │     Phase 5     │
│  Foundation  │  CI Ingest & │   Governed   │ Multi-Account│  Auto-Failover  │
│  & Codespace │  Auto-Fixer  │   Execution  │  Scheduler   │  & Checkpoint   │
│  [DELIVERED] │   Workflow   │  [DELIVERED] │  & Gitpod    │   Governance    │
└──────────────┴──────────────┴──────────────┴──────────────┴─────────────────┘
```

---

## 2. Phase Breakdown

### Phase 1: Workspace Foundation & Codespaces (COMPLETED ✅)
- [x] **DevContainer Modernization**: Updated `.devcontainer/Dockerfile` and `devcontainer.json` to Node 24 LTS, Python 3.11, and native DB tools. *(Delivered via PR #2197 & merged via Batch #2198).*
- [x] **Secure Port Configuration**: 8000 and 5173 forwarded; 5432 (Postgres) and 6379 (Redis) kept strictly internal/private.
- [x] **Resilient Bootstrap**: `.devcontainer/setup.sh` handles warm and cold virtualenvs gracefully.

### Phase 2: Governed Untrusted Code Execution Plane (COMPLETED ✅)
- [x] **Contract Definitions**: `backend/core/sandbox/base.py` defining `SandboxProvider`, `SandboxConfig`, and `ExecutionResult`. *(Delivered via PR #2200).*
- [x] **Zero Secret Leakage**: Strict `environment_policy` strips `SUPREMEAI_*`, `DATABASE_URL*`, `JWT_*`, `INFISICAL_*`, `REDIS_*` from execution contexts.
- [x] **Pluggable Registry**: `backend/core/sandbox/registry.py` for vendor-neutral runtime switching (`codesandbox`, `e2b`, `local_dev`).
- [x] **Local Dev Provider**: `backend/core/sandbox/local_dev_provider.py` with honest non-trusted labeling (`is_trusted_boundary = False`).
- [x] **Cloud MicroVM Provider**: `backend/core/sandbox/cloud_sandbox_provider.py` fails closed when credentials/endpoints are missing.
- [x] **Contract Verification**: 8/8 comprehensive pytest suites passing in 9.75s.

### Phase 3: CI Failure Ingestion & Temporary Fixer Workspaces
- [ ] **Target Module**: `backend/core/workspace/ci_fixer.py`
- [ ] **Workflow Integration**: Parse failing GitHub Actions annotations and logs automatically.
- [ ] **Temporary Fixer Workspace**: When CI goes red, spawn a lightweight, disposable workspace (or run locally in sandbox) to analyze failure deltas and commit minimal fixes.
- [ ] **Loop Prevention**: Max 2 retry attempts per PR to prevent infinite automated CI loops.

### Phase 4: Multi-Account Capacity Pool & Gitpod Integration
- [ ] **Target Module**: `backend/core/workspace/account_registry.py` & `scheduler.py`
- [ ] **Capacity Registry Schema**:
  ```yaml
  account_id: gh-seat-01
  provider: github
  workspace_type: codespaces
  status: available  # available | busy | exhausted | blocked
  quota_remaining: 52.4  # hours remaining this billing cycle
  ```
- [ ] **Dynamic Scheduler**: Selects provider and account based on capability, health, and available quota (target pool 3–5 active).
- [ ] **Gitpod Provider Adapter**: `backend/core/workspace/providers/gitpod.py` providing seamless fallback when Codespace capacity is exhausted.

### Phase 5: Checkpoint Failover & Governance Gates
- [ ] **Target Module**: `backend/core/workspace/checkpoint.py`
- [ ] **Zero-Data-Loss Failover**: Every significant milestone (edit → test → commit) syncs progress to remote branches.
- [ ] **Automated Migration**: If a cloud workspace crashes or times out, the Scheduler boots a new workspace on another account/provider, checks out the last commit, and resumes.
- [ ] **70/30 PR Evaluation Gate**: Integrates with the `PR_EVALUATION_POLICY.md` to ensure all generated changes deliver tangible system benefit before entering the merge train.

---

## 3. Recommended Immediate Next Step
With Phase 1 and Phase 2 foundational code already merged and queued, the next priority is wiring **Phase 3 (CI Failure Ingestion)** and **Phase 4 (Account Registry & Capacity Pool)** to dynamically route agent tasks across available cloud seats.
