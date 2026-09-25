# SupremeAI — Secrets Operations Runbook (Render ↔ Infisical ↔ GitHub ↔ Cloudflare)

**Purpose:** Operator runbook for syncing backend deployment secrets across the four
surfaces SupremeAI uses. This replaces the orphaned `scripts/sync_render_secrets.py`
(removed in issue #1195 / roadmap 2.4 — it had zero callers and could not be
verified without live vault credentials, vendor-tracked by #434). The automation
requirements below are preserved for a future, verifiable re-wiring.

---

## The variable set

| Variable | Source of truth | Goes to |
|---|---|---|
| `RENDER_PRIMARY_URL` / `RENDER_PRIMARY_SVC_ID` | Render dashboard (primary node) | Infisical `prod`, GH Actions secrets, CF Worker `PRIMARY_URL` |
| `RENDER_API_KEY_1` (fallback `RENDER_API_KEY`) | Render account API key | Infisical, GH Actions |
| `RENDER_WORKER_URL` / `RENDER_WORKER_SVC_ID` | Render (worker service) | Infisical, GH Actions, CF Worker `WORKER_URL` |
| `RENDER_API_KEY_2` (fallback `RENDER_API_KEY_BACKUP`) | Render | Infisical, GH Actions |
| `RENDER_SCRAPER_URL` / `RENDER_SCRAPER_SVC_ID` | Render (scraper) | Infisical, GH Actions, CF Worker `SCRAPER_URL` |
| `RENDER_API_KEY_3` (fallback `RENDER_BACKUP_API_KEY_2`) | Render | Infisical, GH Actions |

Golden rule honored by the removed script and this runbook alike: **an empty
source value never overwrites an existing secret** — skip instead of clobbering.

## Manual procedure

1. **Render** — copy the three service URLs + service IDs from the Render
   dashboard; create/rotate the three API keys.
2. **Infisical (environment `prod`, secretPath `/`)** — upsert each variable via
   dashboard or REST (`PATCH /api/v3/secrets/raw/{key}`, then `POST` on 404),
   authenticated with Universal Auth `INFISICAL_CLIENT_ID`/`_SECRET`,
   workspace `INFISICAL_PROJECT_ID`.
3. **GitHub Actions secrets** —
   `gh secret set <NAME> --body "<value>"` for each variable (or REST
   `PUT /repos/SaifulHaqueNiloy/supremeai/actions/secrets/{name}` with
   libsodium sealed-box encryption of the value using the repo public key from
   `GET /actions/secrets/public-key`).
4. **Cloudflare Worker** (`supremeai-worker`) — dashboard → Workers → Settings →
   Variables: set plain-text `PRIMARY_URL`, `WORKER_URL`, `SCRAPER_URL`.
5. **Verify** — `scripts/verify_render_env.py` (fetches real service env vars via
   Render API and checks them against `secrets_registry.yaml`), then re-run the
   vault reconcile gate `scripts/ci/reconcile_secrets_registry.py`.

## Requirements for re-automation (do NOT wire before these hold)

- Infisical Universal Auth credentials reachable from CI and the vendor
  blind-index corruption (#434) resolved — the vault gate must be blocking, not
  `continue-on-error`.
- A single scheduled entrypoint with dry-run mode + explicit `--check` semantics
  (mirror `regen_all_artifacts.sh` style), and zero hard-coded repo/receivers.
- Secrets rotation evidence appended to `docs/release/RELEASE_EVIDENCE.md`.

---

*Canonical registry: `secrets_registry.yaml` · env template: `.env.example` ·
reconcile gate: `scripts/ci/reconcile_secrets_registry.py`.*
