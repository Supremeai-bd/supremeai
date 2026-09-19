# `.secrets-allowlist.json` — Policy & Time-Boxing

> **Issues:** #705 (policy introduced) · Related: `.gitleaks.toml`, docs/security/ENV_HYGIENE_POLICY.md (credential hygiene policy)

## Purpose

`.secrets-allowlist.json` (repo root) records **audited false-positive suppressions** for the
secret-scanning tooling — entries an admin has explicitly marked as "not a secret" (e.g. test
tokens, fixture data) that would otherwise re-fire on every scan.

Entry schema:

```json
{
  "file": "<repo-relative path of the flagged file>",
  "line": <line number>,
  "pattern": "<detector/pattern id>",
  "token_hash": "<sha1 of the flagged token, never the token itself>",
  "reason": "<why this is a false positive>",
  "decided_at": "<ISO-8601 timestamp of the decision>"
}
```

## Current state

**Empty (`[]`) as of 2026-09-19 (#705).** The single historical entry pointed at
`apps/studio-client/dist-admin/assets/index-kPhqL1CO.js` — a file that is **no longer tracked in
git**, making the "admin marked false positive" claim unverifiable. Stale entries are pruned.

## Time-boxing policy

Allowlist entries are **time-boxed, never permanent**:

1. **`decided_at` starts the clock.** Every entry must carry a decision date.
2. **Re-justification cadence:** each entry is re-justified at the **quarterly security review**, or
   **90 days** after `decided_at`, whichever comes first. An entry that cannot be re-justified is
   removed.
3. **Immediate prune triggers** (no waiting for the review):
   - the target file is deleted or no longer tracked in git;
   - the detector pattern no longer fires on the target;
   - the underlying code changed so the original reason no longer applies.
4. **Prefer fixing over allowlisting.** A flagged real credential is rotated and the line scrubbed
   (see `docs/security/ENV_HYGIENE_POLICY.md`); the allowlist is only for genuine false positives.

## Enforcement note (honest limitation)

No in-repo consumer currently reads this file programmatically — `.gitleaks.toml` only excludes the
allowlist file itself from scanning (its `paths` regex `secrets-allowlist`), and no script in
`scripts/` or `.github/workflows/` parses the JSON. Time-boxing is therefore **procedural** (items
1–4 above, checked at review time). If/when a consuming script is introduced, it should support an
**`expires_at`** field and fail the build on expired entries — the JSON above leaves room for it.

## Related files

- `.gitleaks.toml` — scanner configuration; its `[allowlist]` covers test/mock/fixture regexes and
  excludes scanner-config files only (docs/ is **not** allowlisted — see #705 items 1–2, fixed in
  a591926).
- `docs/security/ENV_HYGIENE_POLICY.md` — what to do when a *real* secret is found.
