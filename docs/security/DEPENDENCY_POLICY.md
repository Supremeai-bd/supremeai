# Dependency Policy & Exceptions (AUD-7.8)

> Complements `backend/pyproject.toml` inline comments and
> `scripts/ci/check_free_tier_limits.py` (Runtime Memory Guard).

## 1. Rules

1. **Production image installs only the `main` group** (`poetry install --only main`).
2. **Heavy stacks are optional Poetry groups:**
   - `browser` → playwright (standalone scraper image only)
   - `ml` → torch / sentence-transformers / opencv / pandas / scipy / plotly
   The `ml` group is intentionally NOT installed anywhere in CI (verified in
   `.github/actions/setup-backend/action.yml`). Evolution modules that historically
   imported torch are dead/scaffold code; their callers degrade gracefully via
   `try/except ImportError`.
3. **CVE floors:** `pydantic-settings>=2.14.2`, `python-dotenv>=1.2.2`,
   `aiohttp>=3.14.3`, `pillow>=12.3`, `cryptography>=50.0`, `pyasn1>=0.6.4`,
   `litellm>=1.84,<2` (see AUDIT-014 notes in `pyproject.toml`).
4. **Toolchain pinning:** Poetry itself is pinned to `2.4.1` (matches the
   `poetry.lock` generator, lock-version 2.1) in `backend/Dockerfile`,
   `backend/Dockerfile.ci`, and `.github/actions/setup-backend/action.yml` —
   upgrading Poetry is a deliberate, reviewed change, never floating.
5. **New runtime deps require:** justification comment in `pyproject.toml`, size
   estimate, and a `check_free_tier_limits.py` clean run.

## 2. Intentionally retained dependencies (exceptions)

| Dependency | Why retained despite indirect/heavy |
|---|---|
| `openai` | Hard transitive requirement of `litellm` (provider SDK surface); no direct import in our code. |
| `anthropic` | litellm provider adapter for Claude models; loaded lazily by litellm at call time. |
| `websockets` | Transitive of `uvicorn[standard]` (ws protocol support); not imported directly. |
| `pyasn1` | Transitive via `google-auth`; explicit floor pinned for the CVE fix. |
| `cachetools` | Justified: per-user TTLCache in `rate_limit.py`, `free_tier_tracker.py`, `token_budget.py`. |
| `firebase-admin` | Active ONLY for the legacy Firestore tenant path (`database/tenant_db.py`) and backup tooling; production data plane is Postgres/Supabase. Candidate for removal after the Firestore retirement completes — see MANUAL_STEPS. |

## 3. Removed in this audit (AUD-7.2)

The following declared-but-unused production deps were removed from the `main`
group after a repo-wide import scan (0 imports outside tests):

`requests`, `passlib`, `pydantic-extra-types`, `pytz`, `python-dateutil`,
`google-auth-oauthlib`, `aiofiles`

Notes:
- `requests` is additionally banned by `scripts/check_no_requests_in_backend.sh`
  (backend must use httpx).
- `passlib` was superseded by the PyJWT migration (password hashing path uses
  stdlib pbkdf2 via `passlib`'s removal being safe — verified no importers).
- `lxml` / `infisical-python` kept under observation: no direct imports today,
  removed in the same pass (verify `poetry lock` diff in the patch).
- `ecdsa` / `google-auth-httplib2` were already removed previously (see
  `pyproject.toml` comments).

## 4. Scanning posture (AUD-7.5)

| Scanner | Workflow | Blocking? |
|---|---|---|
| Trivy (fs, CRITICAL/HIGH) | `ci.yml` per push | Yes (exit-code 1) |
| TruffleHog (verified secrets) | `ci.yml` per push | Yes |
| pip-audit | `audit-release.yml` nightly | Yes (added, no `|| true`) |
| `check_dependencies.py` (pnpm audit + poetry check) | `audit-release.yml` nightly | Advisory |
| Dependabot (pip + npm + github-actions) | weekly/monthly | Version updates + alerts |

SBOM: `scripts/security/auto_vulnerability_scanner.py` generates a CycloneDX-style
SBOM from `poetry.lock`; the nightly workflow now uploads it as a build artifact.
