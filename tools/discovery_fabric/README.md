# SupremeAI Discovery Fabric

A reusable discovery layer for SupremeAI to answer four questions before it implements a solution:

1. Where are strong existing solutions?
2. Which sources are trustworthy enough to learn from?
3. Which open-source packages/models/tools are reusable?
4. Which candidate solution is the best trade-off between benefit, effort, risk, and evidence?

## Modules

- `source_scout.py` — searches GitHub, npm, Hugging Face, and an optional PyPI-compatible search endpoint.
- `trust_engine.py` — evidence quality, freshness, authority, reproducibility, directness, conflict scoring.
- `marketplace_scout.py` — turns discovered artifacts into a reusable shortlist.
- `solution_synthesizer.py` — ranks candidate solutions using evidence confidence + benefit/effort/risk.

## Why this is safer than blind web search

The system keeps source URLs and evidence, separates discovery from adoption, and gives weak evidence a low confidence score. It does not install or execute arbitrary code merely because a project ranks highly.

## Example

```bash
python -m supremeai_discovery.source_scout "redis semantic cache python"
```

For larger deployments, treat discovery as a pipeline:

```text
Problem → Search → Candidate Set → Source Trust → License/Security Gate →
Benchmark/Compatibility Check → Solution Ranking → Human/Policy Approval →
Sandbox → Verify → Adopt → Record provenance
```

### Source adapters

The design intentionally uses adapters. More reliable sources can be added later: official product documentation, security advisories, CVE databases, package registries, benchmark datasets, vendor APIs, and organization-approved internal knowledge bases.
