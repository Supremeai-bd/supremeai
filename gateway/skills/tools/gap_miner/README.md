# SupremeAI Gap Miner

A reusable, read-only project intelligence toolkit for SupremeAI and other software projects.

## What it finds

- Security and secret/configuration hazards
- CI/CD weaknesses and missing quality gates
- Dependency/package-manager drift
- Oversized and high-risk source files
- TODO/FIXME/HACK concentration
- Duplicate configuration signals
- API/LLM/provider routing opportunities
- Free-tier capacity and quota opportunities from known config files
- Cache/rate-limit/circuit-breaker coverage signals
- Test coverage signals based on repository structure
- Documentation and operational-readiness gaps
- A prioritized opportunity score and machine-readable JSON report

## Design

The toolkit is intentionally **read-only**, dependency-free, and safe to run locally or in CI.

```bash
python tools/gap_miner.py . --format both --out reports/gap-miner
```

Run individual miners:

```bash
python tools/gap_miner.py . --only security,ci,code,providers,docs
```

CI gate:

```bash
python tools/gap_miner.py . --fail-on critical
```

The scanner never reads file contents from `.env` files; it only reports their presence and configuration patterns.

## Out-of-the-box reusable scripts

### 1. `project_fingerprint.py` — Project DNA
Creates a deterministic architecture fingerprint: manifests, technology signals, import hubs, service-like files, symbol counts, and largest files. Useful for onboarding, AI context selection, architecture comparison, and change detection.

```bash
python tools/project_fingerprint.py .
```

### 2. `context_packager.py` — AI Context Compressor
Builds a ranked project context pack instead of feeding an AI the entire repository. It prioritizes READMEs, agents/instructions, configs, routers, auth, services, tests, deployment and database files.

```bash
python tools/context_packager.py . --out reports/context-pack.md
```

This can become one of SupremeAI's most useful “meta-tools”: every AI agent can start with the same compact project map.

### 3. `drift_detector.py` — Reality vs Documentation
Finds technologies/configurations heavily represented in code but missing from docs/CI, and technologies heavily documented but apparently absent from implementation.

```bash
python tools/drift_detector.py .
```

### 4. `incident_replay.py` — Turn failures into future tests
Takes an application/CI log and extracts deterministic replay candidates around timeouts, 429s, exceptions, connection failures and other signals. Those candidates can seed regression tests or agent investigations.

```bash
python tools/incident_replay.py path/to/error.log
```

### 5. `prompt_distiller.py` — Prompt waste reducer
Removes repeated non-constraint prompt blocks while preserving instruction-heavy material. Useful for large system prompts, agent templates and generated task descriptions.

```bash
python tools/prompt_distiller.py prompts.txt
```

### 6. `safe_autofix_plan.py` — Gap → execution plan
Converts Gap Miner findings into a ranked remediation plan and explicitly separates changes safe for automation from changes requiring human approval.

```bash
python tools/safe_autofix_plan.py reports/gap-miner/gap_report.json
```

## Recommended SupremeAI meta-loop

```text
Project -> Fingerprint -> Gap Mining -> Context Pack
                      ↓
               Incident Replay
                      ↓
                Autofix Plan
                      ↓
             AI Agent / Developer
                      ↓
                CI + Re-scan
                      ↓
             New Fingerprint
                      ↓
                 Drift check
```

The important design principle is that these tools are **read-only by default**. They produce evidence and plans; an agent or developer decides when a source change is safe.
