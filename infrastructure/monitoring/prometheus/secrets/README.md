# Prometheus scrape token for the admin-gated metrics endpoint

The backend exposes Prometheus metrics at `GET /api/admin/metrics`, which is
mounted with `get_current_user_token` (admin-gated). Prometheus therefore
needs a bearer token to scrape.

## Provisioning

1. Mint a long-lived admin/service JWT from your backend auth flow.
2. `cp backend_metrics_token.example backend_metrics_token`
3. Paste the JWT (single line) into `backend_metrics_token`.
4. `docker compose --profile observability up -d prometheus`

`backend_metrics_token` is gitignored — NEVER commit the real token.
The file is read per scrape, so rotating it needs no prometheus restart.
