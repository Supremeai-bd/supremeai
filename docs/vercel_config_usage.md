# Vercel Configuration Usage in SupremeAI

Although SupremeAI's primary frontend is hosted on Firebase, several Vercel environment variables are retained and actively used for infrastructure monitoring and automation. 

## Environment Variables
The following variables are present in the `.env` configuration:
- `VERCEL_TOKEN`
- `VERCEL_ORG_ID`
- `VERCEL_PROJECT_ID`
- `VERCEL_OIDC_TOKEN`

## Exact Usage in Codebase
Based on code analysis, these configurations serve the following exact purposes:

### 1. Cloud Infrastructure Monitoring
**File:** `backend/agents/devops/cloud_watchman.py`
- The `VercelMonitor` class utilizes `VERCEL_OIDC_TOKEN` (mapped to `VERCEL_TOKEN`) to authenticate with Vercel APIs.
- It programmatically checks the deployment status and health metrics of any secondary/legacy Vercel deployments.

### 2. Free-Tier Quota Tracking
**File:** `backend/scripts/superai_free_tier_monitor.py`
- The `VercelChecker` class specifically reads `VERCEL_TOKEN`.
- Its purpose is to monitor bandwidth, execution limits, and other free-tier constraints to prevent unexpected billing or service disruptions.

### 3. MCP Control Plane Automation
**File:** `infrastructure/mcp-control-plane/src/adapters/misc/index.ts`
- The MCP (Model Context Protocol) server requires these credentials to manage infrastructure.
- It explicitly checks for `VERCEL_TOKEN` and `VERCEL_PROJECT_ID` (throws an error if missing) to execute operations like reading logs or managing automated deployments.

### 4. Security Audits & Registry Validation
**Files:** `_audit.py`, `secrets_registry.yaml`
- The tokens are officially tracked in the `secrets_registry.yaml` (synchronized via Infisical).
- `_audit.py` validates the prefixes of these tokens (e.g., ensuring `VERCEL_TOKEN` starts with `vcp_` and `VERCEL_PROJECT_ID` starts with `prj_`).

## Conclusion
These variables are not dead code or artifacts of the past; they are actively integrated into the DevOps, monitoring, and MCP infrastructure of SupremeAI.
