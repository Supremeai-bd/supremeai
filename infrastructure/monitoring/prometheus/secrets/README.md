# Prometheus scrape token for the admin-gated metrics endpoint

The backend exposes Prometheus metrics at `GET /api/admin/metrics`, which is
mounted with `get_current_user_token` (admin-gated). Prometheus therefore
needs a bearer token to scrape.

`backend_metrics_token` is gitignored and therefore absent from a fresh
clone — until it exists, `docker compose --profile observability up` ABORTS
because the prometheus bind-mount source (docker-compose.production.yml,
prometheus.volumes) is missing. Provision it with one of the flows below
BEFORE enabling the observability profile.

## Provisioning (manual)

1. Mint a long-lived admin/service JWT from your backend auth flow.
2. `cp backend_metrics_token.example backend_metrics_token`
3. Paste the JWT (single line) into `backend_metrics_token`.
4. `docker compose --profile observability up -d prometheus`

## Provisioning from Infisical (deploy-step friendly)

R-12 fix (issue #540): keep the token in the Infisical **prod** vault the
backend itself reads (`backend/core/security/secret_vault.py`,
environment=prod; the v3 raw secrets API is the tested interface — see
`docs/guides/infisical_vault_integration_guide.md`), then fetch it into this
file as a deploy step before `compose up`:

    # 1. store the JWT once in the vault under BACKEND_METRICS_TOKEN
    #    (Infisical UI → prod environment, or the v3 raw POST endpoint)
    # 2. fetch it at deploy time (INFISICAL_TOKEN = a machine identity with
    #    read access to the prod vault; INFISICAL_PROJECT_ID = workspace UUID)
    curl -fsS \
      -H "Authorization: Bearer $INFISICAL_TOKEN" \
      "https://app.infisical.com/api/v3/secrets/raw/BACKEND_METRICS_TOKEN?workspaceId=$INFISICAL_PROJECT_ID&environment=prod" \
      | python3 -c 'import json,sys; print(json.load(sys.stdin)["secret"]["secretValue"], end="")' \
      > backend_metrics_token
    chmod 600 backend_metrics_token
    docker compose --profile observability up -d prometheus

If the vault key is missing, fall back to the manual flow above — the file
must exist either way, or the profile cannot start.

`backend_metrics_token` is gitignored — NEVER commit the real token.
The file is read per scrape, so rotating it needs no prometheus restart
(update the file or re-run the Infisical fetch; prometheus picks up the new
bearer token on the next scrape interval).
