# Token Rotation Verification (R10 — Wave 0.4, issue #1234)

> Status: **Harness + runbook active — actual revocation verification pending (owner action)**.
> Register: `docs/architecture/PROJECT_STATUS_DISCREPANCY_REGISTER.md` **R10** —
> the deleted pseudo-config file (`Diagnosed deployment failures and orches.ini`)
> carried 1,544 lines of pasted CI logs of possible secret-bearing content.

## Why "I rotated" is not evidence

Rotation is only real when the OLD credential is verified dead. This runbook
makes that verification executable and repeatable.

## 1. GitHub personal access tokens

**Rotate (if not already):** GitHub → Settings → Developer settings → Personal
access tokens → delete/revoke every token that existed at the time of the R10
leak (2026-09-13 or earlier).

**Verify (the proof):** for each OLD token you believe is dead:

```bash
GITHUB_PROBE_TOKEN=<old-token> python scripts/security/verify_token_rotation.py --github
```

| Result | Meaning | Action |
| --- | --- | --- |
| `[REVOKED] status=401` | token dead — rotation **VERIFIED** for this token | paste the verdict line into this doc's log |
| `[ACTIVE] status=200` | leaked token STILL ALIVE — **CRITICAL** | revoke NOW, audit recent usage (Settings → Audit log), then re-verify |
| `[INCONCLUSIVE]` | rate limit / network / unexpected | retry later; escalate if persistent |

The token is read from the environment only — it is never accepted as an
argv value, never printed, and never written to any log by the harness
(`--self-test` proves non-disclosure offline).

## 2. Render API keys + service tokens

**Rotate:** Render → Account Settings → API Keys → roll the key; also roll any
deploy-hook URLs (they are bearer credentials too).

**Verify:** the old key must fail against `GET https://api.render.com/v1/owners`
(`401/403`). Do this from a throwaway shell; Render has no CLI probe in-repo —
the manual curl is acceptable evidence if pasted with the key redacted.

## 3. Supabase keys (precautionary)

The R10 logs were CI logs; if any Supabase `service_role` key ever appeared in
CI output anywhere, roll it: Supabase → Settings → API → rotate JWT secret /
legacy keys. Verify by confirming old-key requests return `401`.

## Evidence log

<!-- Append one line per verified credential. A rotation without a verdict
     line below is a claim, not evidence. Format:
     - 2026-09-XX · GitHub PAT (suffix-masked label, e.g. `github_pat_…MWWI0`) · [REVOKED] status=401 · verified by <name> -->

_(no verification logged yet — pending owner execution; see issue #1234)_
