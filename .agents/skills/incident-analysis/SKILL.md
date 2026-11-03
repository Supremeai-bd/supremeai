---
name: incident-analysis
version: 0.1.0
description: Combined skill for incident analysis reports with specs and Mermaid diagrams. Use for incident reports, topology docs, and ADRs.
triggers: [incident, analysis, report, mermaid, topology, adr, spec]
permission_level: read
memory_policy: read
owner: supremeai-skills
verification_required: true
---

# Incident Analysis

Produce structured incident analysis reports combining spec-driven development and Mermaid diagrams.

## Workflow
1. Define scope and impact (spec-driven): problem statement, affected services, timeline, root cause hypothesis.
2. Gather evidence: logs, metrics, topology references (NETWORK_ROUTING_TOPOLOGY.md, RENDER_INFRASTRUCTURE_MATRIX.md).
3. Draft the report in Markdown with clear sections: Summary, Timeline, Root Cause, Impact, Remediation, Prevention.
4. Add Mermaid diagrams: sequence/flow for failure path, topology for affected nodes, gantt for timeline.
5. Verify links and diagram rendering; keep minimal and factual (no hype).

## Evidence bar
- Cite exact files/lines and checked dates.
- Separate observed facts from hypotheses.
- Include rollback/stop conditions for remediation.

## SupremeAI integration notes
- Align with 3-Tier Verify and Reflection Evidence for PRs.
- Use for docs/reports/INCIDENT_ANALYSIS_* and topology docs.
- Redact secrets as <REDACTED>.
