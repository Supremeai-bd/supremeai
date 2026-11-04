# Feature Parity Retirement Queue

Generated: 2026-11-05 | Source: scripts/ops/feature_parity_baseline.json (preserved)

Total findings: 650

## Summary by category

| Category | Count | Recommended action |
|---|---|---|
| ghost-ui | 35 | deprecate |
| missing-backend-route | 77 | fix-or-remove |
| orphan-endpoint | 532 | deprecate |
| unmounted-router | 6 | fix-now |

## Summary by action

- **deprecate**: 567
- **fix-now**: 6
- **fix-or-remove**: 77

## Retirement ladder (per plan)

1. Mark deprecated
2. Stop new references
3. Add usage telemetry
4. Add replacement/error response
5. Wait for retention window
6. Remove with regression tests

## Entries

See scripts/ops/feature_parity_retirement_queue.json for the full structured list.

