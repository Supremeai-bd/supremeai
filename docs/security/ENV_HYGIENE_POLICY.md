# Environment Variable & Secret Hygiene Policy (Issue #699)

**Issue:** #699 · **Severity:** P1 · **Category:** env-hygiene
**Companion docs:** `docs/security/CREDENTIAL_ROTATION_CHECKLIST.md` (#696) ·
`docs/security/HS-01-REMEDIATION.md` (#504 history leak) · `docs/deployment/SUPREMEAI_CLUSTER_MASTER_ENV_SPEC.md`

This policy documents the *actual* rules for how environment variables and secrets are named,
stored, and retired in this repo. It is enforceable by review; scanners
(`scripts/security/`, `scripts/devops/_audit.py`) flag violations.

## 1. Secrets come from the Infisical vault — flat files are bootstrap-only

1. Every application secret's **storage of record is the Infisical Cloud vault (`prod`)**.
   The 130+ app secrets are injected at container start; they are never baked into images,
   docs, or committed files.
2. Flat env files (`.env`, `.env.clean`, `env.txt`, `render.env`, "production environment"
   dumps) are **bootstrap conveniences only**: allowed transiently on a local machine or in a
   CI ephemeral workspace to seed a vault sync, and **must be destroyed immediately after
   use**. They are git-ignored and must never be committed, pasted into issues/PRs, or
   attached to tickets.
3. If a real value is ever found in a tracked file: redact it (placeholder + pointer to the
   rotation checklist), rotate the value, then purge history (`#697`) — in that order.
4. Docs may carry **placeholders** (`<INFISICAL_CLIENT_SECRET>`, `<REDACTED — …>`) and key
   *names* only. Verified pattern: `docs/deployment/SUPREMEAI_CLUSTER_MASTER_ENV_SPEC.md`.

## 2. One canonical key name per secret

| Canonical | Deprecated alias | Reality in backend/core (verified #699) |
|---|---|---|
| `SUPREMEAI_API_KEY` | `SUPREMEAI_API_TOKEN` | `config_secrets.py` resolves the vault key `supremeai_api_key` → `SUPREMEAI_API_KEY` and is the only consumer path. `env_validator.py:95` still *declares* `SUPREMEAI_API_TOKEN` as a standalone LOW-severity var, but **no code resolves or reads the alias** — it is a stale declaration, not an implemented alias. |

Rules:

1. **`SUPREMEAI_API_KEY` is canonical.** New code, vault entries, dashboards, and docs must
   use it. Do not introduce new aliases.
2. **`SUPREMEAI_API_TOKEN` is deprecated.** Since the backend has no alias resolution for it,
   provisioning it produces a dead var. Prune it from vault entries and dashboards; remove the
   stale `env_validator.py` declaration when the backend config is next touched.
3. The same one-name-one-secret rule applies elsewhere: e.g. `SUPREMEAI_JWT_SECRET` is
   canonical with `JWT_SECRET` as a warned deprecated alias (see `backend/core/secret_policy.py`,
   issue #567). If a second name is ever genuinely needed, implement an explicit, warned
   alias resolver in `backend/core/` — never an undocumented duplicate.

## 3. `ADMIN_EMAILS` must be double-quoted JSON

1. The **value** of `ADMIN_EMAILS` must be valid JSON whose strings are double-quoted, e.g.
   the process must receive `["ops@example.com","admin@example.com"]`. Shell single-quoted
   JSON payloads such as `ADMIN_EMAILS=['ops@example.com']` are **forbidden** — that is not
   valid JSON, and `json.loads` consumers in `backend/core/` must not be fed it. In a dotenv
   line, wrap the double-quoted JSON in shell single quotes (`ADMIN_EMAILS='["ops@example.com"]'`)
   or double quotes with escaped inner quotes — either way the parsed value is double-quoted JSON.
2. Verified in #699: root `.env.example:222` already ships `ADMIN_EMAILS=""` (empty,
   double-quoted) — compliant; `apps/mission-control/.env.example` does not define the key.
   Any env file carrying a single-quoted `ADMIN_EMAILS` payload must be rewritten to
   double-quoted JSON before use.
3. Validation-side: treat malformed `ADMIN_EMAILS` as a boot-time error, not a silent empty
   list.

## 4. TOTP seeds are per-environment and freshly generated

1. Every environment generates its **own** admin TOTP seed at provisioning time
   (`backend/api/routes/admin_routes.py` mints one via pyotp and emits the `otpauth://` URI).
2. **Library example values are forbidden** — the public pyotp README seed must never be a
   live seed. `scripts/devops/_audit.py` classifies that exact example value as FAKE and must
   keep doing so (issue #696; the live admin seed equaled the example — re-enrollment is part
   of the #696 rotation, step 4 of `docs/security/CREDENTIAL_ROTATION_CHECKLIST.md`).
3. Seeds live in the vault per environment; they are never shared across dev/staging/prod and
   never written to flat files or docs.

## 5. Stale references are pruned, not accumulated

1. Environment keys whose backing resource no longer exists must be removed from docs and
   registries. **`RENDER_BACKUP_SVC_ID` points to a deleted Render service** — its doc rows
   are pruned by #699:
   - `docs/plans/infrastructure/third_party_env_and_secrets_operational_checklist.md`
   - `docs/plans/infrastructure/SUPREMEAI_CONFIGURATION_CONTROL_REGISTRY_V2.md`
2. Remaining non-doc references (kept functional in #699, prune candidates for owners):
   - `.github/workflows/ci-deploy-production.yml` declares/falls back to
     `RENDER_BACKUP_SVC_ID` after `RENDER_WORKER_SVC_ID` — the fallback can never succeed
     against a deleted service; remove it in a CI-owned change.
   - `secrets_registry.yaml` entry and the `scripts/security/generate_secrets.py` writer.
3. Rule of thumb: when a service/database/integration is deleted, the same PR retires its env
   key from `.env.example`, docs, `secrets_registry.yaml`, and workflow secrets lists.

## 6. Scanner false-positive allowlists are time-boxed

`.secrets-allowlist.json` entries are never permanent: each carries a `decided_at` and is
re-justified quarterly (90-day box), with immediate pruning when the target file disappears.
Full policy and prune triggers: [`SECRETS_ALLOWLIST_POLICY.md`](SECRETS_ALLOWLIST_POLICY.md)
(#705 — the stale `apps/studio-client/dist-admin/...` entry was pruned there).
