# Infisical Vault Integration Guide (Integrator Contract)

> 🇧🇩 **গুরুত্বপূর্ণ (issue #434):** এই প্রজেক্টের ভল্টে **v1 স্ট্যান্ডার্ড `listSecrets()` ব্যবহার নিষিদ্ধ** — vendor blind-index কারাপশনের কারণে সেই রুট **404/empty** রিটার্ন করে (identity auth-এ)।
> 🇬🇧 **Important (issue #434):** the standard v1 `listSecrets()` route is **corrupted at the vendor REST layer** for this project — it returns **404/empty** with identity auth even though the secrets exist.

## The ONLY supported access path: v3 RAW API

Production's `backend/core/security/secret_vault.py` talks to the **v3 raw secrets API** — that exact path is the tested, guarded interface:

```text
GET https://app.infisical.com/api/v3/secrets/raw?workspaceId={PROJECT_UUID}&environment=prod
GET https://app.infisical.com/api/v3/secrets/raw/{KEY}?workspaceId={PROJECT_UUID}&environment=prod
Authorization: Bearer <universal-auth accessToken>
```

* Login: `POST /api/v1/auth/universal-auth/login` with the project identity's `clientId` / `clientSecret`.
* `environment` slugs: `prod` | `staging` | `dev`.
* Never log secret values; never commit fetched values.

## Guard rails (so silent breakage cannot recur)

| guard | where | behavior |
|---|---|---|
| Weekly synthetic check | `.github/workflows/maintenance.yml` → `infisical-vault-synthetic-check` | fails when raw listing drops below 100 secrets or a boot-critical key stops being served |
| Script | `scripts/maintenance/check_infisical_vault_synth.py` | asserts login + raw list ≥ 100 + boot-key get-by-key; reports v1 status informationally |

Last verified live (2026-09-19): raw listing returned **177 prod secrets**; `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` served via raw get-by-key.

## If the vendor fixes the v1 route

1. The weekly check logs `INFO: v1 standard listSecrets now returns 200`.
2. Re-run parity (`prodMissing=[]` via the ops dashboard).
3. Then — and only then — deliberately remove the raw-path workaround flag.

## Known caveats

* The corrupted v1 route means ANY new integration (rotation tooling, DR scripts, cross-project audits) that calls the SDK's default `listSecrets()` will see an **empty vault** and may fail-closed — this exact gap caused the Sep 14–17 primary-node crash-loop. Route them through `secret_vault.py` (or the v3 raw API) instead.
* Vendor support ticket: to be filed by the owner (requires an Infisical account) — draft text is pinned in issue #434.
