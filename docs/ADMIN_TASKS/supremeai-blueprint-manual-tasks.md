# SupremeAI blueprint implementation handoff

The repository now provides a governed intelligence router, bounded execution budgets, evidence-based verification, and a non-secret manual-task registry. These controls intentionally keep irreversible actions proposal-only.

## Manual tasks

- Rotate any previously exposed Render API key and GitHub PAT; verify revocation.
- Verify `ENCRYPTION_KEY`, `INFISICAL_CLIENT_SECRET`, `INFISICAL_TOKEN`, `SUPREMEAI_ADMIN_PASSWORD_HASH`, and `SUPREMEAI_JWT_SECRET` in the managed cloud secret store; do not commit them.
- Provision and verify the durable `ai_memory` schema, pgvector extension, HNSW/index strategy, tenant ownership, and RLS using canonical Alembic migrations.
- Confirm the live database revision matches `backend/alembic_migrations/`; archive legacy SQL only after a schema-drift backup and DBA/release-owner approval.
- Connect and authorize GitHub, Supabase, Render, notification, and AI providers with least privilege; rotate or revoke any credential exposed outside the managed secret store.
- Review the six deferred/skipped tests, assign an owner and due date, and either implement or formally accept each deferral.
- Review and approve generated PRs, migrations, configuration changes, deployments, rotations, and production mutations.
- Configure cloud schedules for memory consolidation and risk watchers with alerts, retention limits, and an explicit failure escalation path.
- Run DAST/ZAP review, staging login/OTP/Deck/module smoke tests, payment smoke tests, restore drills, canary checks, and production deployment verification.
- Approve retention/privacy policy for audit artifacts and autonomous remediation boundaries; attach evidence to the release or audit record.

No secret, token, provider authorization, production deployment, destructive migration, DAST run, or direct default-branch mutation is performed by this implementation.
