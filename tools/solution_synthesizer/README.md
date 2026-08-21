# SupremeAI Solution Synthesizer — The Hand

`solution_synthesizer.py` is the repair half of the autonomous engineering loop.
It accepts a diagnostic issue, gathers targeted code context, asks a configurable AI solver for a **minimal structured patch**, validates the patch, applies it in an isolated copy, runs tests/verification commands, and only then optionally applies the winning patch to the real project.

## Flow

`diagnosis -> evidence -> solution hypothesis -> patch -> sandbox -> tests -> verified patch -> optional apply -> backup`

## Safety defaults

- Dry-run by default. Real changes require `--apply`.
- Only approved relative project roots may be changed.
- `.git`, dependency/vendor/build directories are ignored.
- Workflow deletion is blocked.
- Every real apply gets a timestamped `.supremeai_backups/` backup.
- Patch output is structured JSON, not free-form shell commands.

## Configure a solver

The solver endpoint is OpenAI-compatible:

```text
SUPREMEAI_SOLVER_URL=https://your-endpoint/v1/chat/completions
SUPREMEAI_SOLVER_API_KEY=...
SUPREMEAI_SOLVER_MODEL=...
```

This makes SupremeAI's own router/provider layer usable as the repair brain.

## Run

```bash
python tools/solution_synthesizer.py . --issue examples/issue.json
python tools/solution_synthesizer.py . --issue examples/issue.json --apply
```

The report defaults to `reports/solution_synthesizer.json`.
