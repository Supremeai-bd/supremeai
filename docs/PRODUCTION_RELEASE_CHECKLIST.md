# Production Release Checklist

This checklist is evidence-driven. It does not rotate secrets, mutate production databases, or deploy automatically.

## Human-controlled blockers

- [ ] Render API key and any previously exposed GitHub PAT are revoked/rotated.
- [ ] Required production secrets are present in the production secret manager.
- [ ] Staging and production repositories/services are explicitly identified.
- [ ] Release owner and rollback owner are recorded.

## Automated evidence

- [ ] CI is green for the exact release commit.
- [ ] Root/tooling Ruff and Python compilation gates pass.
- [ ] Backend and frontend tests pass with truthful coverage reports.
- [ ] Migration safety and schema-contract checks pass.
- [ ] Secret and dependency scans pass.
- [ ] Skipped tests are documented with owner, ticket, risk, evidence, and review date.
- [ ] Staging smoke tests pass for health, auth/RBAC, agent, memory, worker, and billing callback contracts.

## Promotion evidence

- [ ] Read-only production schema parity is verified against `schema_contract.yaml`.
- [ ] A tested rollback target is available.
- [ ] Monitoring and alert thresholds are active.
- [ ] Release evidence bundle is attached to the candidate release.
- [ ] Human approval is recorded before production promotion.

## Post-deploy verification

- [ ] Health/readiness endpoints pass.
- [ ] Login and one authorized agent action pass.
- [ ] Memory access and worker processing pass.
- [ ] Payment callback smoke test passes.
- [ ] Error rate, latency, queue backlog, and database connectivity are monitored.
