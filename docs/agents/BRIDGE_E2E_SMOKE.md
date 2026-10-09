# Bridge E2E Smoke (bridge-20261009-e2e-smoke-v2)

Live proof artifact of Bridge v1 (public → private work lane):

- Submitted by a public agent with ZERO private-repo access
- Path: work-order issue on `paykaribazaronline/supremeai-open`
  → fail-closed intake (validate / dedup / caps / secret-scan / protected-path check)
  → applied inside `paykaribazaronline/supremeai` as a gated PR
  → constitutional gates decide landing

Iteration note: v1 (`docs/bridge/E2E_SMOKE.md`) was correctly BLOCKED by the
Docs Garbage Guard (non-allowlisted `docs/*.md`) — this v2 uses the allowlisted
`docs/agents/**` lane. Fail-closed gates teach agents repo law.

If you can read this file inside the private codebase, the bridge works.
