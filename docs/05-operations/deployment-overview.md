# 🚀 Deployment Overview

This document describes the deployment workflows and infrastructure configurations for SupremeAI 2.0.

---

## 🏭 Staging → Production Pipeline

We utilize a double-repository Staging/Canary Deployment Pattern to isolate automated AI development and prevent untested or buggy code from reaching production.

```mermaid
graph TD
    Agent[SupremeAI Agent] -->|Push Code| Staging[saifulhaqueniloy/supremeai Staging Repo]
    Staging -->|GitHub Actions CI/CD| Validation[Test, Lint, Build & Scan]
    Validation -->|All Passed| Dispatch[repository_dispatch event]
    Dispatch -->|Trigger Auto Deploy| Main[paykaribazaronline/supremeai Main Repo]
    Main -->|Deploy| Live[Live Production Server]
```

### 🧪 Staging Repository
- **URL**: https://github.com/saifulhaqueniloy/supremeai
- **Purpose**: All automated AI code commits are pushed here first.
- **Access**: SupremeAI system (write), Admin (read/write)

### 👑 Main / Production Repository
- **URL**: https://github.com/paykaribazaronline/supremeai
- **Purpose**: Production branch containing only verified and validated code.
- **Access**: Admin only (AI agent has no direct push access)

### 🔄 Trigger Sequence
1. AI commits code changes to the Staging Repository.
2. GitHub Actions on Staging runs unit tests, linter checks, build validation, and security audit scans.
3. If all validation runs successfully, a `repository_dispatch` trigger containing the event `staging-passed` is sent to the Main repository.
4. The Main repository pulls verified updates from Staging and automatically deploys them to production.
5. If validation fails, the build halts, the agent is notified to resolve the bugs, and no deployment is made.
