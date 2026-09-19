# Supabase CA certificate (`SUPABASE_DB_CA_CERT`) provisioning

R-13 fix (issue #578): the Supabase root CA certificate (`supabase-ca.crt`,
"Supabase Root 2021 CA") is no longer committed to the repository. It is
provisioned at deploy time and injected through the secret vault.

## Why it was removed

A CA certificate is public by design, so this was never a secret leak — but
committing runtime PKI material into a public repo is a configuration smell:
cert rotation becomes coupled to code releases, and the tracked file silently
drifts out of sync with the CA actually served by Supabase.

## How the backend consumes it

`backend/core/db_ssl.py::build_supabase_ssl_context()` passes the value of
`SUPABASE_DB_CA_CERT` straight into `ssl.SSLContext.load_verify_locations(
cadata=...)` — i.e. it expects the **PEM content itself**, not a file path.
The variable is optional (`OPTIONAL_SECRETS`); when unset the context falls
back to certifi's trust store.

## Provisioning steps

1. Download the current Supabase root CA certificate from Supabase's official
   documentation ("Connecting to your database" → SSL section) — do **not**
   copy it from a repo, vendored bundle, or third-party mirror.
2. Store the PEM value (the whole `-----BEGIN CERTIFICATE-----` block) in the
   Infisical **prod** vault under the key `SUPABASE_DB_CA_CERT` (the backend
   reads it via `backend/core/security/secret_vault.py`, same flow as the
   other vault-backed secrets).
3. Alternatively, set `SUPABASE_DB_CA_CERT` as a plain environment variable in
   your deployment platform (Render/env file). Multi-line PEM values must keep
   their newlines intact.
4. Verify at startup: the backend logs
   `✅ Loaded explicit Supabase CA certificate for Verify-Full SSL.`

## Note on git history

Removing the file from `HEAD` does not erase it from git history. The blob
stays reachable in old commits. Since the CA is public material this is low
risk, but owners who want a tidy history can use the existing purge tooling
(`scripts/security/purge_history_secrets.sh`, see
`docs/security/HS-01-REMEDIATION.md`) — a history rewrite is intentionally
out of scope for this fix and is left to the repository owners.
