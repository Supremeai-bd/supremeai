# SECRETS_AUDIT.md — SupremeAI tracked-files secrets audit

## Audit metadata

- **Date:** 2026-09-02 (UTC)
- **Scope:** every file returned by `git ls-files` in the working tree at
  commit `784d761` (+ local Task 9-c2 changes) — 2,896 tracked files.
  Git history and the local `.git/config` remote were assessed separately
  (see "Residual risks").
- **Method:** pattern scan of file contents (case-sensitive regexes) for:
  - `rnd_[A-Za-z0-9]{16,}` — Render API keys
  - `sbp_[A-Za-z0-9]{10,}` — Supabase personal access tokens
  - `sk-or-…`, `sk-proj-…`, `sk-ant-…` — OpenRouter / OpenAI / Anthropic keys
  - `AIza[0-9A-Za-z_-]{30,}` — Google API keys
  - `ghp_`, `gho_`, `ghs_`, `github_pat_…` — GitHub tokens (classic / OAuth / server / fine-grained)
  - `eyJ…` triple-segment JWTs
  - `xoxb-…` — Slack bot tokens
  - `postgres://…:…@`, `postgres://…:…@`, `rediss?://…:…@` — credentialed DB/Redis URLs
  - `-----BEGIN … PRIVATE KEY-----` blocks
  - Cross-checked against the repo's own gitleaks configuration (`.gitleaks.toml`,
    gitleaks v8.30.1 custom Render rule + test/mock allowlist).

## Result: **CLEAN on tracked files**

Zero live-looking secrets found in any tracked file. All 28 raw pattern hits
were manually reviewed and are benign:

- **Test fixtures** (excluded from the finding per scope):
  - `backend/tests/api/test_byoc_endpoints.py` (×2),
    `backend/tests/byoc/test_cloud_connector.py` — service-account JSON with
    `[REDACTED:ssh_private_key]` placeholder keys (`pkey123`, `sa@valid-gcp-project`).
  - `backend/tests/core/test_db_coverage.py`, `backend/tests/core/test_core_config_comprehensive.py`,
    `backend/tests/security/test_database_readiness_regression.py` — `postgres://u:p@…`,
    `user:pass` connection-string mocks.
  - `.github/workflows/ci.yml` (×3) — `postgresql://dummy:…`, `postgresql://test_user:…` CI service containers.
  - `apply_tier_patch.py` (×4) — `postgresql://test_user:test_password` heredoc fixtures.
  - `backend/tools/learning/Diagnosed deployment failures and orches.ini` — `postgresql://test_user:…` log transcript.
- **Env lookups / documentation placeholders** (excluded from the finding per scope):
  - `.env.example` — `rediss://default:<password>@<host>.upstash.io:6379` (documented placeholder).
  - `docker-compose.production.yml` — `redis://:${REDIS_PASSWORD}@…` (env-var interpolation, no literal secret).
  - `backend/core/config_validation.py`, `backend/core/env_validator.py`,
    `scripts/security/auto_vulnerability_scanner.py`, `.github/scripts/surface_advanced_audit_summary.py` —
    regex/format literals describing the URL *shape*, not credentials.
  - `MANUAL_STEPS.md`, `patch_v4/MANUAL_STEPS.md` — `postgresql://postgres.[project-ref]:[password]@…` docs placeholders.
  - `.agents/rules/AI_AGENT_ANTIPATTERN_PLAYBOOK.md` — `postgresql://user:password@…` example.

## Residual risks (action required)

1. **Render API keys + GitHub PAT exist in GIT HISTORY from before the scrub
   commits — rotation required.** Verified: reachable history blobs (e.g. commit
   `056b733`, `069d100`) still contain `check_render.py` / `check_services*.py` /
   `delete_render_services.py` with literal `rnd_…` Render API keys. The current
   working-tree copies are scrubbed, but history retains them. All four Render
   API keys and the historical GitHub PAT must be treated as compromised:
   rotate/revoke them, then rewrite history (e.g. `git filter-repo` + force-push)
   if the repo must be cleansed. A shallow local clone cannot see whether even
   older commits hold more (see risk 3).
2. **Local `.git/config` embeds a fine-grained PAT in the remote URL** —
   `https://<github_pat_…>@github.com/SaifulHaqueNiloy/supremeai.git`. Anyone with
   read access to this clone's `.git/` can extract it. Rotate the PAT, then switch
   the remote to a credential helper:
   `git remote set-url origin https://github.com/SaifulHaqueNiloy/supremeai.git`
   + `git config credential.helper store` (or `gh auth login` / SSH deploy key).
3. **Shallow clone limits the audit** — `git rev-parse --is-shallow-repository`
   → `true` (89 commits locally). A full-depth `gitleaks detect --redact` scan
   (`gitleaks git --follow` over the complete history) is recommended once the
   repo is fetched with `git fetch --unshallow`; history beyond the shallow
   boundary was NOT scanned here.
4. **Stale `.secrets-allowlist.json` entry** — the allowlist still references
   `apps\studio-client\dist-admin\assets\index-kPhqL1CO.js` ("admin marked false
   positive", decided 2026-08-06), but the `apps/studio-client/dist-admin/`
   bundle is no longer tracked/present. The entry is harmless but should be
   removed so a future re-introduction of that path isn't silently ignored.
   (Audit tooling config files are themselves allowlisted by `.gitleaks.toml`,
   so this file is never flagged.)

## Tooling

- Repo scanner config: `.gitleaks.toml` (gitleaks v8.30.1; custom
  `render-api-key` + `supremeai-key` rules; test/mock allowlist for
  `tests/`, `docs/`, `_archive/`, CI fixture strings).
- Keep the scanner in CI (`.github/workflows` + `scripts/security/auto_vulnerability_scanner.py`)
  and re-run this audit after any history rewrite.
