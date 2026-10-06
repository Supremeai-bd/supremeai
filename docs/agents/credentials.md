# Agent Credentials — Bootstrap & Flow (issue #4081)

> **Purpose:** Explain how an AI agent gets GitHub App access in SupremeAI, why fresh agent processes get stuck, and how to bootstrap credentials.

---

## The Zero-Knowledge Broker Design

SupremeAI uses a **zero-knowledge broker** credential pattern (security best practice — least privilege):

```
┌─────────────────────────────────────────────────────────────┐
│  Parent Orchestrator (continuous_agent_loop.py)             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Has: INFISICAL_* (from vault.env OR env vars)       │   │
│  │ Has: GitHub App private key (fetched from Infisical) │   │
│  │ Mints: 1-hour GitHub App installation token          │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          │ build_scoped_env(role, token)    │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ FORBIDDEN_ENV_KEYS strips:                           │   │
│  │   INFISICAL_CLIENT_ID                                │   │
│  │   INFISICAL_CLIENT_SECRET                            │   │
│  │   INFISICAL_PROJECT_ID                               │   │
│  │   GITHUB_APP_PRIVATE_KEY                             │   │
│  │   GITHUB_APP_ID                                      │   │
│  │   GITHUB_APP_INSTALLATION_ID                         │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Child Agent Process gets ONLY:                       │   │
│  │   GH_TOKEN (the minted token)                        │   │
│  │   GH_REPO                                             │   │
│  │   AGENT_SLOT, AGENT_ROLE, AGENT_NAME                 │   │
│  │   + AI provider keys (for coder/ci/auditor)          │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Why this design?**
- Child agent processes cannot exfiltrate vault credentials (they never see them)
- Each child gets only the role-specific keys it needs (least privilege)
- `rules_breaker` role gets ZERO keys (zero-trust sandbox for negative testing)
- Compromised child = limited blast radius (only the 1-hour token, not the vault)

**Key files:**
- `scripts/agents/credential_manager.py` — `resolve_and_mint_for_slot()`, `build_scoped_env()`, `FORBIDDEN_ENV_KEYS`
- `scripts/agents/continuous_agent_loop.py:1263` `run_work_command()` — parent mints token + injects scoped env
- `scripts/ci/atomic_claim.sh:140` — `GH_TOKEN` env var (from parent) → `gh auth token` fallback → fail

---

## The 3 Credential Sources

| Source | Where | Use case |
|---|---|---|
| **`vault.env` file** | Repo root (gitignored, `.gitignore:725`, mode 600) | Local dev / fresh container / manual agent start |
| **`INFISICAL_*` env vars** | Process env (set by CI) | GitHub Actions runners (injected as GitHub Actions secrets) |
| **`GH_TOKEN` env var** | Process env (set by parent orchestrator) | Child agent process (pre-minted by parent) |

---

## Why Fresh Agent Processes Get Stuck (Root Cause #4081)

A fresh agent process (new container, fresh clone, CI runner restart) has:
- ❌ No `vault.env` file (gitignored — not in the clone)
- ❌ No `INFISICAL_*` env vars (only set in CI runner after secret injection)
- ❌ No `GH_TOKEN` env var (only set by parent orchestrator)
- ❌ No cached token (memory-only, lost on process exit)

Result: `resolve_and_mint_for_slot()` raises `CredentialError("No Infisical credentials found...")`. The agent cannot:
- Push commits to GitHub
- Create issues / PRs
- Claim issues via `atomic_claim.sh`
- Run any GitHub API mutation

This is the **intended** zero-knowledge design — but it means: **without a bootstrap path, a fresh agent is stuck.**

---

## Bootstrap Fix (issue #4081)

### Interactive mode (local dev / fresh container)
```bash
python scripts/agents/credential_bootstrap.py
```
Prompts for:
- `INFISICAL_CLIENT_ID`
- `INFISICAL_CLIENT_SECRET`
- `INFISICAL_PROJECT_ID`
- (optional) `INFISICAL_IDENTITY_ID`, `INFISICAL_AUTH_METHOD` (default: `universal-auth`), `INFISICAL_ENV` (default: `prod`)

Creates `vault.env` at repo root (mode 600, gitignored).

### Non-interactive mode (CI / automation)
```bash
export INFISICAL_CLIENT_ID="..."
export INFISICAL_CLIENT_SECRET="..."
export INFISICAL_PROJECT_ID="..."
python scripts/agents/credential_bootstrap.py --non-interactive
```
Reads from env vars, writes `vault.env` without prompts.

### Check if vault.env exists
```bash
python scripts/agents/credential_bootstrap.py --check
# Exit 0 = present, 1 = missing
```

### Verify vault.env has all required keys
```bash
python scripts/agents/credential_bootstrap.py --verify
# Prints present/missing keys (no values printed)
```

---

## Complete Bootstrap Flow

```bash
# 1. Clone the repo
git clone https://github.com/SaifulHaqueNiloy/supremeai.git
cd supremeai

# 2. Bootstrap credentials (interactive)
python scripts/agents/credential_bootstrap.py
# → prompts for INFISICAL_CLIENT_ID, INFISICAL_CLIENT_SECRET, INFISICAL_PROJECT_ID
# → creates vault.env (mode 600, gitignored)

# 3. Verify
python scripts/agents/credential_bootstrap.py --verify
# → ✅ vault.env is valid. Ready to mint tokens.

# 4. Mint a token for your slot
python scripts/agents/credential_manager.py --slot agent-3
# → prints masked token + expires_at + bot_name + scopes

# 5. Set GH_TOKEN for your shell (programmatic use)
export GH_TOKEN=$(python -c "
import sys; sys.path.insert(0, 'scripts/agents')
from credential_manager import resolve_and_mint_for_slot
print(resolve_and_mint_for_slot('agent-3')['token'])
")

# 6. Use any agent script
python scripts/agents/continuous_agent_loop.py --role coder --agent-name coder-1 --slot agent-3
# OR
./scripts/ci/atomic_claim.sh 4081 supremeai-coder-1-bot --skip-assign
```

---

## Slot → GitHub App Mapping (BOT_SLOT_CREDENTIALS)

| Slot | Bot name | Role | Env prefix | Scopes |
|---|---|---|---|---|
| `agent-1` | supremeai-planner | planner | `GITHUB_APP` | issues:write |
| `agent-2` | supremeai-pr-helper | pr-helper | `AGENT_PR_HELPER` | pull_requests:write, issues:write |
| `agent-3` | supremeai-coder-1 | coder | `AGENT_CODER_1` | contents:write, pull_requests:write, issues:write |
| `agent-5` | supremeai-ci-action | ci | `AGENT_CI_ACTION` | contents:write, workflows:write, pull_requests:write |
| `agent-6` | supremeai-coder-2 | coder | `AGENT_CODER_2` | contents:write, pull_requests:write, issues:write |
| `audit-pool` | supremeai-planner | auditor | `GITHUB_APP` | issues:write (lease-only) |

**Infisical secrets per slot (example for agent-3):**
- `AGENT_CODER_1_APP_ID`
- `AGENT_CODER_1_INSTALLATION_ID`
- `AGENT_CODER_1_PRIVATE_KEY`

**Fallback secrets (shared across slots):**
- `GITHUB_APP_ID`
- `GITHUB_APP_INSTALLATION_ID`
- `GITHUB_APP_PRIVATE_KEY`

---

## Troubleshooting

### "No Infisical credentials found for slot 'agent-3'"
**Cause:** `vault.env` missing AND `INFISICAL_*` env vars not set.
**Fix:** Run `python scripts/agents/credential_bootstrap.py` (interactive) or `--non-interactive` (CI).

### "Missing GitHub App creds for slot 'agent-3' (prefix AGENT_CODER_1)"
**Cause:** Infisical login succeeded, but the slot-specific secrets (`AGENT_CODER_1_APP_ID`, etc.) are missing from Infisical.
**Fix:** Check Infisical dashboard → `prod` environment → secretPath `/` → ensure the 3 secrets exist. Use the fallback `GITHUB_APP_*` secrets if slot-specific ones are not provisioned yet.

### "network transport unavailable (pip install requests)"
**Cause:** `requests` Python package not installed.
**Fix:** `pip install requests` (or `pip install requests[security]`).

### "JIT mint unavailable for slot 'agent-3' (...) — falling back to ambient token"
**Cause:** `continuous_agent_loop.py` caught a `CredentialError` from `resolve_and_mint_for_slot()` and is falling back to ambient `GH_TOKEN`.
**Fix:** Bootstrap credentials (see above), then re-run.

### "❌ #2644 scoped-spawn: no JIT mint and no ambient GH_TOKEN — refusing to spawn"
**Cause:** Both `resolve_and_mint_for_slot()` failed AND `GH_TOKEN` env var is empty.
**Fix:** Bootstrap credentials, then either (a) re-run the loop (it will mint), or (b) `export GH_TOKEN=$(...)` manually.

### `atomic_claim.sh` fails with "GH_TOKEN required -- run: gh auth login"
**Cause:** No `GH_TOKEN` env var AND no `gh auth login` session.
**Fix:** Bootstrap credentials + mint a token:
```bash
python scripts/agents/credential_bootstrap.py
export GH_TOKEN=$(python -c "import sys; sys.path.insert(0,'scripts/agents'); from credential_manager import resolve_and_mint_for_slot; print(resolve_and_mint_for_slot('agent-3')['token'])")
./scripts/ci/atomic_claim.sh <issue> <agent-name> --skip-assign
```

---

## Security Notes

- `vault.env` is gitignored (`.gitignore:725`) — never committed
- `vault.env` is mode 600 (owner read/write only)
- `resolve_and_mint_for_slot()` never logs the private key or token (only masked)
- `build_scoped_env()` strips `FORBIDDEN_ENV_KEYS` from child process env
- Token TTL is 1 hour (3600s) — auto-refresh handled by parent orchestrator
- Token cache is in-memory only (`_TOKEN_CACHE` dict) — lost on process exit (by design)

---

## MCP Tower + Scoped Delivery to Child Agents (issue #4134)

Before #4134, loop-spawned children got a GitHub token but **no MCP Tower
credentials** — `mcp_tower_client` silently degraded to viewer mode
(read-only), and CI runs never had vault access at all (the loop job passed
only `GH_TOKEN`/`GH_REPO`, so JIT mint degraded to the ambient PAT).

The delivery chain now is:

```
GitHub Secrets (INFISICAL_CLIENT_ID/SECRET/PROJECT_ID only)
        │  (agent-loop job env — continuous-agent-loop.yml)
        ▼
Infisical vault  ──SSOT for everything else──►  per-slot GitHub App keys
        │                                        MCP_API_KEY / tower URL
        │                                        AI provider keys
        ▼
fetch_credentials()  →  vault_extras  (same fetch, zero extra network calls)
        │
        ▼
run_work_command():  base_env = ambient env + vault_extras gap-fill (ambient wins)
        │
        ▼
build_scoped_env():  role allowlist decides; FORBIDDEN keys stripped
        │             (coder/ci/planner/pr-helper/auditor get MCP_API_KEY+MCP_TOWER_URL;
        │              rules_breaker + human-eyes stay zero-key)
        ▼
child process — authenticated to the tower as an agent, not viewer
```

Key properties:

- **Vault URL canonicalization:** the tower URL is read from
  `MCP_TOWER_URL` → `MCP_SERVER_URL` → `MCP_URL` (whichever the vault has)
  and delivered to children uniformly as `MCP_TOWER_URL`.
- **Ambient wins:** orchestrator-provided env values are never overridden by
  the vault; vault values only fill gaps (CI bootstrap path).
- **Still zero-knowledge:** `INFISICAL_*` and `GITHUB_APP_*` remain in
  `FORBIDDEN_ENV_KEYS`; `vault_extras` is curated — master creds can never
  ride along.
- **CI bootstrap:** the `agent-loop` job exports the three `INFISICAL_*`
  secrets; `resolve_and_mint_for_slot()` already falls back to
  `INFISICAL_*` process env, so CI mints real per-slot App tokens (bot
  identity, 1h TTL) instead of degrading to `SELF_HEAL_PAT`.

---

## Cross-References

- **Credential manager:** `scripts/agents/credential_manager.py` (the zero-knowledge broker)
- **Bootstrap script:** `scripts/agents/credential_bootstrap.py` (issue #4081 fix)
- **Continuous loop:** `scripts/agents/continuous_agent_loop.py` `run_work_command()` (parent mint + vault-extras gap-fill + inject)
- **Atomic claim:** `scripts/ci/atomic_claim.sh:140` (GH_TOKEN → gh auth token → fail)
- **Slot registry:** `scripts/agents/credential_manager.py:59-100` `BOT_SLOT_CREDENTIALS`
- **Forbidden keys:** `scripts/agents/credential_manager.py:131-138` `FORBIDDEN_ENV_KEYS`
- **Scoped env:** `scripts/agents/credential_manager.py` `build_scoped_env()` (+ `_MCP_TOWER_KEYS`, `_vault_extras_from()`)
- **Orphaned bootstrap:** `scripts/runtime/infisical_bootstrap.py` (exists but not wired — could be consolidated)
- **Secrets runbook:** `docs/SECRETS_OPERATIONS.md` (Render/Supabase/Cloudflare operator secrets — different scope)
- **Infisical scope:** `docs/security/INFISICAL_IDENTITY_SCOPE.md` (scope, not bootstrap)

---

*Bengali note (AGENTS.md Rule #6): এই ডক মূল সমস্যার সমাধান করে — fresh agent process-এ কোনো vault.env বা INFISICAL_* env না থাকলে agent stuck হয়। credential_bootstrap.py দিয়ে interactive বা non-interactive mode-এ vault.env তৈরি করুন, তারপর credential_manager.py স্বাভাবিকভাবে কাজ করবে। জিরো-নলেজ ব্রোকার ডিজাইন নিরাপত্তা সেরা অনুশীলন — child process-এ INFISICAL_* strip হয়, শুধু GH_TOKEN পায়।*
