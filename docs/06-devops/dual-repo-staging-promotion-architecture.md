# SupremeAI 2.0 — Dual-Repo Staging & Promotion Architecture
_Status: ACTIVE_
_Last Updated: 2026-08-04_

---

## 🏗️ Architecture Overview

SupremeAI 2.0 employs a **Zero-Downtime Dual-Repository Staging & Promotion Strategy** designed to ensure complete CI/CD testing safety without risking premature production deployments.

```
+-----------------------------------------------------------------------------------+
| 1. MAIN REPOSITORY (paykaribazaronline/supremeai)                                |
|    - Developer pushes commits directly to main or feature branches.                |
|    - CI Workflow triggers and mirrors the codebase to the Secondary Repo.        |
+-----------------------------------------------------------------------------------+
                                         |
                                         v (Automatic Git Push / Mirroring)
+-----------------------------------------------------------------------------------+
| 2. SECONDARY REPOSITORY (SaifulHaqueNiloy/supremeai)                              |
|    - Acts as the Isolated Staging Sandbox & Integration Testbed.                  |
|    - Full CI Test Pipeline runs (Pytest, Vitest, Lint, Preflight, Build Audit).   |
|    - NO REAL PRODUCTION DEPLOYMENTS occur from this repository.                   |
|    - Once Workflow is GREEN 🟢, an Automated Pull Request (PR) is opened back     |
|      to the Main Repository.                                                      |
+-----------------------------------------------------------------------------------+
                                         |
                                         v (Automated PR Creation on Success)
+-----------------------------------------------------------------------------------+
| 3. ADMIN REVIEW & PRODUCTION PROMOTION                                            |
|    - Admin reviews the Green PR on the Main Repository.                           |
|    - Admin approves and merges the PR.                                            |
|    - Production Deployments (Render, Vercel, Firebase, Cloud Run) execute live.   |
+-----------------------------------------------------------------------------------+
```

---

## ⚙️ Core Rules & Policies

1. **Secondary Repo Sandbox Isolation:**
   - The secondary repository (`SaifulHaqueNiloy/supremeai`) **MUST NEVER** execute live production deployments (Cloud Run, Render Web Services, Vercel Projects, or Firebase Hosting).
   - All deployment steps in the secondary repo are strictly disabled or configured as dry-run validations.

2. **Automated PR Dispatch:**
   - Whenever all CI test gates (Preflight, Ruff, Pytest, ESLint, Vitest, Build Audit) pass on the secondary repository, the pipeline automatically creates or updates a Pull Request targeting `paykaribazaronline/supremeai:main`.

3. **Admin Promotion Approval:**
   - Production deployment is strictly governed by Human-in-the-Loop admin approval via PR merge in the Main Repository.

---

## 🛠️ Step-by-Step Workflow Cycle

| Phase | Repository | Action / Trigger | Result |
| :--- | :--- | :--- | :--- |
| **1. Mirror** | Main (`paykaribazaronline`) | Developer pushes commit | Code automatically mirrored to Secondary Repo |
| **2. Test Sandboxing** | Secondary (`SaifulHaqueNiloy`) | `supreme-core-ci.yml` runs | Executed: Pytest, Vitest, Preflight, Linters.<br>Skipped: Real Production Deploys |
| **3. Automated PR** | Secondary (`SaifulHaqueNiloy`) | CI Status = GREEN 🟢 | Auto-creates PR to `paykaribazaronline/supremeai:main` |
| **4. Final Release** | Main (`paykaribazaronline`) | Admin merges PR | Live production deployment executes across Cloud Services |

---

## 📄 Configuration Reference

- **Secondary Repo Mirror Trigger:** [.github/workflows/supreme-core-ci.yml](file:///c:/Users/n/supremeai/supremeai_2.0/.github/workflows/supreme-core-ci.yml#L1405-L1430)
- **Staging Sync Handler:** [.github/workflows/sync-from-prod.yml](file:///c:/Users/n/supremeai/supremeai_2.0/.github/workflows/sync-from-prod.yml)
- **Workflows Registry:** [docs/06-devops/github-actions-workflows-registry.md](file:///c:/Users/n/supremeai/supremeai_2.0/docs/06-devops/github-actions-workflows-registry.md)

---
_Generated for SupremeAI 2.0 — Dual-Repo DevOps Architecture_
