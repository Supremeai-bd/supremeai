# SECURITY Policy — SupremeAI

## 1. Supported Branches / Releases
- **Main branch (`main`)** is the only customer-facing release branch.
- **SupremeAI-internal** (platform-only) is forbidden in customer projects.
- Releases flow through GitHub Actions + Render Cloud triggers; no direct push to `main`.

## 2. Vulnerability Reporting (Private)
- Submit private findings to GitHub Issues labelled `security` and `vulnerability`.
- Critical CVEs escalated to the executive team within 48 hours.
- Automated scanners: `pip-audit`, `bandit[sarif]`, `trufflehog`, `gitleaks` — run on every PR before merge.

## 3. Secret Exposure & Rotation Procedure
- **Never commit secrets.** All credentials live in environment variables or approved secret stores.
- Rotate Infisical/Render API keys immediately when suspected compromised.
- Run `infisical_bootstrap.py <command>` with injected env vars; **fail closed** if any required env var is absent.
- Every workflow reference must point to secrets, not literal values (see `unified-pipeline.yml`, `ops-maintenance.yml`).

## 4. Dependency & Supply-Chain Process
- Pin third-party GitHub Actions to full commit SHAs (e.g., `uses: actions/checkout@<full-sha>`).
- Commit a lockfile per package manager: `npm ci` (npm), `pnpm install --frozen-lockfile` (pnpm).
- Reproducibility: `npm ci` / `pnpm install --frozen-lockfile` in CI; deps must match `package.json` exactly.
- Run `pip-audit`, `bandit[sarif]`, `trufflehog` on PRs before merge.

## 5. Governance & Memory
- Constitutional memory validates every action against core principles before approval.
- Issue #699 flat env dumps are bootstrap-only and never tracked.
- `SECURITY.md` lives here; update when policies change.
