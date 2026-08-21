# SupremeAI Autonomy Pack

Reusable, dependency-light scripts designed to turn SupremeAI into a self-improving engineering platform.

## Control loop

Observe -> Diagnose -> Plan -> Patch -> Verify -> Deploy -> Monitor -> Learn -> Update capabilities

## Tools

- `tools/self_heal_loop.py` — turns failures into a bounded repair plan, patch candidates, and verification commands.
- `tools/test_synthesizer.py` — converts traceback/log/API examples into regression-test skeletons.
- `tools/deploy_guard.py` — pre-deploy risk gate: changed-file risk, secrets, missing tests, rollback readiness, and blast radius.
- `tools/maintenance_watchdog.py` — detects stale dependencies, TODO debt, oversized files, flaky-pattern hints, and maintenance pressure.
- `tools/capability_builder.py` — maps a user goal to missing capabilities, tools, skills, data sources, and an implementation plan.
- `tools/source_trust_engine.py` — ranks learning sources using authority, freshness, corroboration, provenance, and conflict checks.
- `tools/knowledge_ingestor.py` — converts verified source material into small auditable knowledge records with provenance.
- `tools/agent_change_budget.py` — assigns a change-risk budget and approval tier before an agent edits/deploys anything.
- `tools/autonomy_cycle.py` — orchestrates the tools into one reusable lifecycle report.

## Safety model

All tools are read-only or plan-first by default. Real patching, deployment, or external learning should be performed only through explicit adapters in the host system after policy approval.

## Example

```bash
python tools/autonomy_cycle.py /path/to/project --output reports/autonomy.json
```

You can also run individual tools. Each emits JSON suitable for an admin dashboard, agent memory, or CI artifact.
