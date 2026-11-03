# Route → Client Inventory (generated)

> Generator: `scripts/ci/generate_route_client_inventory.py` — issue #480 / GAP-001. Do not edit by hand; assumptions live inside the JSON header.

- backend routes scanned: **594**
- unique frontend `/api/...` refs: **144**
- matched (frontend-reachable): **270**
- orphan backend routes: **324** (118 route families)

## Orphan classifications (heuristic — owners must ratify)

| classification | count | next action |
|---|---|---|
| `internal` | 44 | document as internal; verify not publicly reachable |
| `unclassified-orphan` | 248 | triage: user-facing wiring vs intentional API-only |
| `admin-only` | 32 | wire into admin UI or document as admin-API |

## Top orphan families

| family | orphan routes |
|---|---|
| `/api/v1/gcp` | 3 |
| `/api/v1/skills` | 3 |
| `/api/v1/router` | 1 |
| `/api/v1/meta-ai` | 8 |
| `/api/v1/analytics` | 3 |
| `/api/artifacts` | 1 |
| `/api/artifacts/conversation` | 1 |
| `/api/artifacts/:param` | 4 |
| `/api/v1/auth` | 10 |
| `/api/billing/budget-check` | 1 |
| `/api/billing/history` | 1 |
| `/api/billing/add-funds` | 1 |
| `/api/billing/webhook` | 2 |
| `/api/conversations/:param` | 3 |
| `/api/conversations/tree` | 1 |
| `/api/byoc/credentials` | 1 |
| `/api/byoc/deploy` | 1 |
| `/api/byoc/status` | 1 |
| `/api/v1/cache` | 1 |
| `/api/v1/cdc` | 2 |

Full detail: `docs/audit_reports/route_client_inventory.json`.
