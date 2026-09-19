# Infisical Machine Identity — Verified Scope

> **Status:** verified live 2026-09-19 · **Issues:** #700 (this doc), #434 (vendor defect), #696 (rotation)
> **Owner actions only:** identity re-scoping / permission changes inside Infisical are owner/vendor
> actions tracked in #434 and the rotation checklist
> (`docs/security/CREDENTIAL_ROTATION_CHECKLIST.md`). Do **not** attempt repo-side permission changes.

## 1. Identity & auth method

| Item | Value |
| --- | --- |
| Auth method | **Universal Auth** — `POST /api/v1/auth/universal-auth/login` with `INFISICAL_CLIENT_ID` / `INFISICAL_CLIENT_SECRET` |
| Project | `INFISICAL_PROJECT_ID` (project **SupremeAI**; env slugs `dev` / `staging` / `prod`) |
| Token TTL | access token per login (~30-day TTL stated by vendor at issue time) |
| Where used | backend `backend/core/security/secret_vault.py`, MCP tower `infrastructure/mcp-control-plane/src/adapters/infisical/index.ts`, CI (`INFISICAL_CLIENT_ID/_SECRET` GitHub secrets), weekly synthetic check |

## 2. What the identity CAN do (verified 2026-09-19)

- **Authenticate** via universal-auth → 200 OK, token issued.
- **List** the prod vault through the **v3 RAW path** —
  `GET /api/v3/secrets/raw?workspaceId=…&environment=prod` → **174 prod secrets**.
- **Read by key** through the raw path — boot-critical probes
  (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`) return non-empty values.
- **Write/update** prod secrets through the raw path (vault verified healthy for read/write by the
  orchestrating session on 2026-09-19).

Exact counts drift as secrets are added/removed; the weekly guard below enforces a **≥ 100 floor**
rather than an exact number. (`docs/guides/infisical_vault_integration_guide.md` recorded 177 the
same day — both are snapshots of a live vault.)

## 3. What the identity CANNOT do / known broken

- **Standard encrypted list** — `GET /api/v3/secrets?environment=prod` returns
  `{"secrets":[],"imports":[]}` on **every** environment (dev/staging/prod). This is a **vendor-side
  blind-index defect**, tracked in #434 (kept open as vendor action). It is **not** an empty vault —
  the raw path serves the full inventory.
- **Other environments unverified** — raw-path counts for `dev`/`staging` have not been
  independently verified; only `prod` is in scope for the weekly check.
- **No sync integrations** — the workspace integrations list is **empty** (tower tool
  `infisical.sync_status` → `{"integrations": []}`, verified 2026-09-19). Secrets reach Render
  services via the machine identity at boot
  (`pullSecretsIntoProcessEnv()` in the tower; `secret_vault.py` in the backend), **not** via
  Infisical→Render managed syncs. Any doc claiming "synced via Infisical integrations" is inaccurate.

## 4. Tower visibility (health tooling)

- `infrastructure/mcp-control-plane/src/health/engine.ts` registers the Infisical check via
  `auditSecrets()` (`src/adapters/infisical/index.ts`).
- **#700 fix:** `auditSecrets()` now probes the **raw path** as the authoritative signal and reports
  `rawCount`; the **standard** encrypted path is probed in parallel and reported in a **distinct
  `standardPath` field** (`status: ok | empty | error`, `count`, `message`) so the vendor fix becomes
  visible the moment it lands — without degrading the raw-path health signal.
- The tower previously reported `infisical-primary` as *unconfigured* because its probe hit the
  broken standard path and saw 0 secrets; after the #700 probe fix it reports healthy with the raw
  count.

## 5. Expected-key inventory pointer

- **`secrets_registry.yaml`** (repo root) — canonical inventory of secret *names* + criticality per
  target (`infisical-vault`, `render-backend`, `render-admin`, `github-actions`, `firebase-gcp`).
- **`docs/deployment/ENV_EVIDENCE_MATRIX.md`** — per-variable verification state
  (`verified-live` / `present-in-vault` / `pending`).
- Vault ↔ registry drift beyond the raw-path floor should be investigated manually (registry lists
  expected names; the raw listing gives actual names).

## 6. Weekly synthetic guard

| Artifact | Role |
| --- | --- |
| `scripts/maintenance/check_infisical_vault_synth.py` | read-only guard: universal-auth login, raw list ≥ 100 prod secrets, raw get-by-key for boot-critical keys; reports standard-API status **informationally** |
| `.github/workflows/maintenance.yml` → job `infisical-vault-synthetic-check` | runs the script on the workflow schedule (daily 02:00 UTC cron + Monday 02:30 UTC cron, plus manual dispatch); fails red when the raw contract breaks — the early warning that pre-empts a Sep-14-style crash loop |

If the job goes red: check the raw path first (auth → list → boot keys); a red **raw** check means
production boot is at risk. A changed **standard-path** INFO line means the vendor may have fixed
#434 — re-run parity, then deliberately retire the raw-path workaround per the acceptance notes in
#434 and `docs/guides/infisical_vault_integration_guide.md`.

## 7. References

- #700 — identity reads 0 secrets via the standard API (repo-side remediation, this doc)
- #434 — vendor blind-index defect on the standard REST route (OPEN, vendor action)
- #696 / `docs/security/CREDENTIAL_ROTATION_CHECKLIST.md` — rotation includes the Infisical identity credentials
- `docs/guides/infisical_vault_integration_guide.md` — the raw-path-only access contract
- `docs/plans/infrastructure/infisical_enterprise_secret_management_guide.md` — platform setup guide
