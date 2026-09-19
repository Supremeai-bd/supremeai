# HS-01 — Remediation Runbook: Live Secrets in Public Git History

**Issue:** #504 · **Severity:** P0-critical · **Category:** history-leak
**Status:** ⚠️ REQUIRES IMMEDIATE OWNER ACTION (rotation cannot be automated from CI)

## 1. What leaked (evidence)

`git log --all -p -G 'rnd_[A-Za-z0-9]{20,}'` returns real Render API keys that
still authenticate against the production Render accounts:

| Key | Node |
|---|---|
| `RENDER_API_KEY` / `RENDER_API_KEY_1` | Primary node |
| `RENDER_API_KEY_2` | Worker node |
| `RENDER_API_KEY_3` | Scraper node |
| `RENDER_API_KEY_4` | MCP Tower node |

`git log --all -p -G 'INFISICAL_CLIENT_SECRET'` also returns 64-hex
client-secret-shaped values. `.gitignore` (SECURITY HOTFIX block) documents
the files that carried real credentials into history, including:

- `render_*.json`, `run.json`
- `docs/Enviorment vs secret key/env_security_auth.md`
- `scripts/sync_secrets_to_frontend.py`, `scripts/sync_secrets_to_render.py`
- `scripts/check_deploys.py`, `scripts/check_health_path.py`, `scripts/check_key.py`,
  `scripts/fetch_logs.py`, `scripts/status.py`, `scripts/sync_both.py`,
  `scripts/test_render_api.py`, `scripts/trigger.py`, `scripts/trigger_deploys.py`

The repo is **public** (`private: false`): anyone can clone and extract these.

## 2. Immediate actions (TODAY) — rotate, do NOT just delete files

Deleting files from `HEAD` does **not** remove them from history.

1. **Rotate all four Render API keys** — Render Dashboard → Account Settings →
   API Keys, per account. Update the new keys in:
   - GitHub Actions secrets (`RENDER_API_KEY*` on the repo)
   - The MCP tower env (`RENDER_API_KEY*` on MCP Tower service)
   - Any local `.env` files
2. **Rotate the Infisical client secret(s)** used by CI/CD identities
   (Infisical → Organization → Identities → regenerate client secret) and the
   same values wherever they are deployed.
3. **Audit usage** — Render/Infisical access logs: look for API calls from
   unknown IPs since the earliest leak date, and for `render_get_env_vars` /
   deploy calls not made by your CI.
4. **Rotate anything else that ever appeared in history**: JWT secrets, Stripe,
   Supabase `service_role`, OPENAI/GEMINI keys, TELEGRAM bot token, Cloudflare
   API token, Kaggle token (scan: `git log --all -p` + your secret patterns).

## 3. Purge history (AFTER rotation)

Use the helper script (dry-run by default):

```bash
pip install git-filter-repo        # once
bash scripts/security/purge_history_secrets.sh --dry-run   # see what would change
bash scripts/security/purge_history_secrets.sh             # rewrite history
```

What it does:
- Replaces every `rnd_<id>` Render key and 64-hex Infisical-client-secret-shaped
  string in **all** blobs with `***REMOVED***`
- Removes the known leaked files/blobs entirely
- Leaves one commit rewriting the repo

Then coordinate the force-push (this rewrites every SHA):

```bash
git push --force --all
git push --force --tags
```

**Everyone must re-clone** afterwards; old clones keep serving the secrets.
Unmatched/open PRs may need to be re-based onto the rewritten `main`.

## 4. Prevent recurrence

1. GitHub → Repo → Settings → Code security → **enable Secret scanning** and
   **Push protection** (blocks future pushes containing recognized secrets).
2. Keep secret-material in GitHub Actions secrets / Render env / Infisical —
   never in tracked files (the SECURITY HOTFIX block in `.gitignore` stays).
3. Add the `gitleaks` pre-commit hook (or CI job) using
   `.gitleaks.toml` patterns for `rnd_*` + hex client secrets.

## 5. Verification checklist

- [ ] All 4 Render keys rotated (old keys return 401)
- [ ] Infisical client secrets rotated
- [ ] Access-log review completed
- [ ] History rewritten (`git log --all -p -G 'rnd_[A-Za-z0-9]{20,}'` returns nothing)
- [ ] Force-pushed to `origin` (all branches + tags)
- [ ] Team re-cloned
- [ ] Secret scanning + push protection enabled
