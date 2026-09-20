# Credential Rotation Checklist — Exposed Credentials (Issue #696)

**Issue:** #696 · **Severity:** P0-critical · **Category:** credential-exposure
**Status:** ⚠️ REQUIRES IMMEDIATE OWNER ACTION (rotation cannot be automated from CI)
**Companion docs:** `docs/security/HS-01-REMEDIATION.md` (history leak, Render keys, Infisical) · `docs/security/ENV_HYGIENE_POLICY.md` (where new values may live) · `#697` (history purge) · `#703` (Cloudflare ids)

Repo-side remediation (done in the #696 PR): the live `CI_WEBHOOK_SECRET` value and the
Cloudflare `account_id` / `CLOUDFLARE_ACCOUNT_ID` values were redacted from
`docs/deployment/SUPREMEAI_CLUSTER_MASTER_ENV_SPEC.md`, and the weak literal embedded in
`scripts/devops/_audit.py`'s placeholder detector was removed (detector now describes the
weak-value class without carrying the value). **Redacting files does NOT un-leak anything:**
the repo is public and old commits still contain the values, so every credential below must
be rotated **before** any history purge.

## 0. Ground rules (apply to every step)

1. **Rotate first, purge later.** History purge (`#697`, `scripts/security/purge_history_secrets.sh`)
   is only useful *after* the values are dead. Purging first gives false comfort and destroys
   the evidence list.
2. **New values go ONLY into the Infisical Cloud vault (`prod`)** — or into the platform-native
   store when the platform is the consumer (GitHub Actions secrets, Render env, Cloudflare
   dashboard). **Never** into flat files in the repo, never into `.env.clean`/`env.txt`
   (bootstrap-only, destroy after use — see `docs/security/ENV_HYGIENE_POLICY.md`).

   > **⚠️ Vault write limitation (verified live 2026-09-19, vendor defect → issue #434):**
   > the machine identity used by CI/automation **can update existing vault keys but cannot
   > create new ones** via the API. `PATCH /api/v3/secrets/raw/{KEY}` works (plaintext body,
   > server-side encryption); `POST /api/v3/secrets/raw` and bulk `PATCH` are rejected with
   > `422` demanding client-side E2EE ciphertext fields that identity tokens cannot produce
   > (the workspace API exposes no wrapped project key to identities). **Practical
   > consequence for rotation:** when a rotation needs a *new* key name (or the first value
   > for a key that does not exist yet), create it once in the **Infisical web dashboard**
   > (or with an admin *user* token); after that, automated updates via the identity keep
   > working. Do not build rotation tooling that assumes identity-token creates.
3. **Verify the old credential is dead** after each rotation (the verification commands below
   must return `401`/`403`). A rotation is not done until the old value fails.
4. **Rotate in the order below** — least-coupled first; CI_WEBHOOK_SECRET/admin password are
   grouped because the admin password currently equals the CI webhook secret.

## 1. GitHub admin PAT (personal access token with admin scope)

* **Where it lives:** GitHub → Settings → Developer settings → PATs; referenced as
  `SUPREMEAI_GITHUB_TOKEN` (Node 4 MCP Tower env, `scripts/devops/_audit.py` validator table) and
  fine-grained PATs granted to helper workflows. Render API sweeps in prior sessions found
  additional fine-grained PATs mounted on services — revoke anything unrecognized.
* **Rotate:** revoke the PAT, mint a new fine-grained PAT limited to this repo +
  `contents:read` unless a workflow provably needs more.
* **Verify old dead:** `curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer <OLD>" https://api.github.com/user` → must be `401`.
* **Store new:** Infisical `prod` vault (+ GitHub Actions secret only if a workflow consumes it). Never in docs or flat files.

## 2. Render API keys ×4 (`RENDER_API_KEY_1` … `RENDER_API_KEY_4`)

* **Where it lives:** four Render accounts (one per node); consumed by Node 4 MCP Tower env
  and GitHub Actions secrets; also present in git history (see HS-01).
* **Rotate:** each Render account → Account Settings → API Keys → regenerate. Keys are
  account-scoped: regenerate on all four accounts.
* **Verify old dead:** `curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer <OLD>" https://api.render.com/v1/services` → must be `401`.
* **Store new:** Infisical `prod` vault + GitHub Actions secrets (`RENDER_API_KEY_1..4`) + Node 4 service env. Update `RENDER_*_SVC_ID` references only if service ids changed (they shouldn't).

## 3. Upstash Redis tokens ×5

* **Where it lives:** five Upstash databases (REST tokens + `rediss://` passwords embedded in
  URLs); consumed via `REDIS_URL` / `REDIS_REST_URL` + tokens from Infisical.
* **Rotate:** Upstash console → per database → Reset password / Roll REST tokens. Five
  databases = five resets.
* **Verify old dead:** `curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer <OLD_REST_TOKEN>" https://<db>.upstash.io` → must be `401`; for the TLS password, `redis-cli -u "rediss://default:<OLD>@<host>:6379" ping` must fail auth.
* **Store new:** Infisical `prod` vault only (`REDIS_URL`, `REDIS_REST_URL`, `REDIS_REST_TOKEN`).

## 4. CI_WEBHOOK_SECRET + admin password + admin TOTP re-enroll (one blast radius)

* **Where it lives:** GitHub Actions secret `CI_WEBHOOK_SECRET`; the admin login password
  (currently **equal** to the CI webhook secret — rotate both together) stored as
  `SUPREMEAI_ADMIN_LOGIN_PASSWORD` / bcrypt `SUPREMEAI_ADMIN_PASSWORD_HASH`; admin TOTP seed
  (currently **equals the public pyotp example seed** — `scripts/devops/_audit.py` classifies
  that exact value as FAKE, and `docs/plans/design/*` reference the same library example).
* **Rotate:**
  1. Generate a fresh high-entropy `CI_WEBHOOK_SECRET` (`openssl rand -hex 32`) → update the
     GitHub Actions secret and every consumer that compares webhook signatures
     (`backend/core/config_secrets.py`, `config_validation.py`, CI deploy workflows).
  2. Set a new admin password (NOT derived from any domain/brand string); re-bcrypt
     (`bcrypt.hashpw`, cost ≥ 12) → update `SUPREMEAI_ADMIN_PASSWORD_HASH` in Infisical.
  3. **Re-enroll TOTP:** generate a fresh per-environment seed (never a library example
     value), re-scan the QR on the admin's authenticator app.
* **Verify old dead:** a request signed with the OLD secret must be rejected `401/403` by the
  webhook/auth path; admin login with the old password must fail; a TOTP code derived from
  the old seed must be rejected.
* **Store new:** GitHub Actions secret + Infisical vault. `scripts/devops/_audit.py` will keep
  flagging bare-domain-style values as PLACEHOLDER — that check is intentional.

## 5. Infisical client secret + machine-identity re-scope

* **Where it lives:** Infisical machine identity used by all four Render nodes and GitHub
  Actions (`INFISICAL_CLIENT_ID` / `INFISICAL_CLIENT_SECRET`, Universal Auth).
* **Rotate:** Infisical → Machine Identities → rotate client secret; **re-scope** the identity
  to the minimum projects/environments it actually needs (identity re-scope per issue #696).
* **Verify old dead:** `curl -s -o /dev/null -w "%{http_code}\n" -X POST https://app.infisical.com/api/v1/auth/universal-auth/login -H "Content-Type: application/json" -d '{"clientId":"<OLD_ID>","clientSecret":"<OLD_SECRET>"}'` → must be `401`.
* **Store new:** the identity's own bootstrap locations (4× Render node env + GitHub Actions
  secrets) — these are the unavoidable bootstrap credentials; everything else stays vault-only.

## 6. SUPREMEAI_API_KEY (master API key)

* **Where it lives:** Infisical key `supremeai_api_key` → surfaced as `SUPREMEAI_API_KEY`
  (`backend/core/config_secrets.py`; canonical name — `SUPREMEAI_API_TOKEN` is a deprecated
  alias, see `docs/security/ENV_HYGIENE_POLICY.md`). Expected format `sk-supreme-…`.
* **Rotate:** generate a new key with the same `sk-supreme-` prefix convention, update the
  vault entry, then update every service-to-service caller out of band.
* **Verify old dead:** `curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: <OLD>" https://<render-primary-url>/api/v1/health` (or any authenticated probe) → must be `401/403` for the old key while the new key passes.
* **Store new:** Infisical vault only.

## 7. Render deploy-hook URLs

* **Where it lives:** per-service Deploy Hook URLs (Render → service → Settings → Deploy
  Hook); anyone with the URL can trigger a deploy, and the old URLs are in git history.
* **Rotate:** Reset the deploy hook URL for each of the four services; update the GitHub
  Actions secret / Infisical entry that stores it (`RENDER_DEPLOY_HOOK_URL` references in
  `docs/plans/infrastructure/*`).
* **Verify old dead:** `curl -s -o /dev/null -w "%{http_code}\n" -X POST <OLD_HOOK_URL>` → must be `404`/`401`-class failure; the NEW URL must return `200` and trigger a deploy.
* **Store new:** Infisical vault + GitHub Actions secret (never docs/flat files).

## 8. Cloudflare account id / KV namespace ids (tracked by #703)

* The account/KV **ids** are identifiers, not authenticators, but they were tracked as exposed
  (#703) and are now redacted in the master env spec. The rotation that actually matters here
  is the **Cloudflare API token** (`CLOUDFLARE_API_TOKEN`): roll it in Cloudflare → My
  Profile → API Tokens, verify the old token returns `401` on
  `https://api.cloudflare.com/client/v4/user/tokens/verify`, store the new one in GitHub
  Actions secrets + Infisical. KV ids do not need "rotation", only restraint (keep them out of
  tracked files; see `infrastructure/cloudflare/wrangler.toml` env contract from #573).

## 9. Only after ALL of the above: history purge (#697)

* Follow `docs/security/HS-01-REMEDIATION.md` + `scripts/security/purge_history_secrets.sh`.
* Post-purge verification: `git log --all -p -G '<rotated-value-shape>'` returns nothing; force-push
  coordination required for all clones/forks (public repo — assume crawled; that is why
  rotation, not purge, is the real fix).
* Re-run `scripts/devops/_audit.py` and the secret scanners (`scripts/security/`) to confirm
  zero live-value hits.
