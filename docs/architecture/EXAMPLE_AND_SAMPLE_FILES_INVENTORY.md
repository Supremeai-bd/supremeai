# SupremeAI Codebase Inventory: Example, Sample & Demo Files
> **Status:** AUDITED & CATALOGED  
> **Target Phase:** Step-3 Simplification & Consolidation  
> **Total Files Identified:** 16 files  
> **Zero-Regression Invariant:** Verified no production runtime imports exist for dead code examples.

---

## 1. Summary of Identified Example Files

| # | File Path | Size | Category | Step-3 Action | Production Callers |
|---|---|---|---|---|---|
| 1 | `backend/docs/examples/retry_integration_example.py` | 7.2 KB | Dead Python Code | **DELETE** | None (docs only) |
| 2 | `backend/examples/sample_buggy.py` | 5.5 KB | Dead Python Code | **DELETE** | None (audits only) |
| 3 | `backend/tools/langchain_agent_example.py` | 0.4 KB | Dead Python Code | **DELETE** | None (catalog only) |
| 4 | `scripts/demo_agent_communication.py` | 7.7 KB | Standalone Script | **DELETE / ARCHIVE** | None (catalog only) |
| 5 | `tools/intelligence_extensions/scripts/run_examples.py` | 0.4 KB | Tools Example | **DELETE** | None |
| 6 | `tools/knowledge_squeezer/knowledge_squeezer/example_run.py` | 0.5 KB | Tools Example | **DELETE** | None |
| 7 | `tools/autonomy/examples/source_candidates.json` | 0.3 KB | Mock JSON Fixture | **CONSOLIDATE** | None |
| 8 | `tools/discovery_fabric/example_problem.json` | 1.4 KB | Mock JSON Fixture | **CONSOLIDATE** | None |
| 9 | `tools/solution_synthesizer/examples/issue.json` | 0.2 KB | Mock JSON Fixture | **CONSOLIDATE** | None |
| 10 | `tools/solution_synthesizer/examples/self_test_issue.json` | 0.1 KB | Mock JSON Fixture | **CONSOLIDATE** | None |
| 11 | `.env.example` | 25.8 KB | Env Template | **KEEP** (Canonical) | Active CI / Dev setup |
| 12 | `.env.grafana.example` | 1.3 KB | Env Template | **KEEP** | Grafana monitoring |
| 13 | `.env.production.example` | 2.7 KB | Env Template | **KEEP** | Production deploy |
| 14 | `apps/mission-control/.env.example` | 0.8 KB | Env Template | **KEEP** | Frontend / Mission Control |
| 15 | `infrastructure/monitoring/prometheus/secrets/backend_metrics_token.example` | 0.3 KB | Prometheus Secret Template | **KEEP** | Monitoring infra |
| 16 | `scripts/ci/generate_env_example.py` | 13.5 KB | CI Generator Tool | **KEEP** | CI pipeline script |

---

## 2. Detailed Breakdown by Category

### Category A: Dead Python Example Code (Immediate Step-3 Delete)
These files reside inside the `backend/` and `scripts/` directories but have zero active production imports:

1. **`backend/docs/examples/retry_integration_example.py`**
   - **LOC:** ~180 lines | **Size:** 7,238 bytes
   - **Purpose:** Demonstrates standalone retry integration logic.
   - **Step-3 Action:** Delete. Any needed documentation can be represented as inline docstrings in core retry modules.

2. **`backend/examples/sample_buggy.py`**
   - **LOC:** ~140 lines | **Size:** 5,474 bytes
   - **Purpose:** Intentionally buggy code snippet used in ancient self-healing tests.
   - **Step-3 Action:** Delete along with dead `backend/examples/` folder.

3. **`backend/tools/langchain_agent_example.py`**
   - **LOC:** ~15 lines | **Size:** 381 bytes
   - **Purpose:** Stub example demonstrating LangChain agent invocation.
   - **Step-3 Action:** Delete. SupremeAI does not use external LangChain abstractions.

4. **`scripts/demo_agent_communication.py`**
   - **LOC:** ~190 lines | **Size:** 7,690 bytes
   - **Purpose:** Demo script showing console-based agent messaging.
   - **Step-3 Action:** Delete or retire in `docs/archive/` if ever needed.

5. **`tools/intelligence_extensions/scripts/run_examples.py`**
   - **LOC:** ~15 lines | **Size:** 447 bytes
   - **Purpose:** Micro-runner for intelligence extension examples.
   - **Step-3 Action:** Delete.

6. **`tools/knowledge_squeezer/knowledge_squeezer/example_run.py`**
   - **LOC:** ~18 lines | **Size:** 457 bytes
   - **Purpose:** Micro-runner for knowledge squeezer example.
   - **Step-3 Action:** Delete.

---

### Category B: Sample / Example JSON Fixtures
These are static mock data files stored across various `tools/*/examples/` folders:

* `tools/autonomy/examples/source_candidates.json`
* `tools/discovery_fabric/example_problem.json`
* `tools/solution_synthesizer/examples/issue.json`
* `tools/solution_synthesizer/examples/self_test_issue.json`

**Step-3 Action:** Consolidate these static test fixtures into the standard `tests/fixtures/` directory or delete if their parent tools are retired in Step-3.

---

### Category C: Production Environment Templates (Protected — DO NOT DELETE)
These files end with `.example` and are canonical templates for onboarding, CI, and deployment:

* `.env.example` — Main system environment template.
* `.env.production.example` — Production deployment secret keys template.
* `.env.grafana.example` — Observability Grafana dashboard env template.
* `apps/mission-control/.env.example` — Mission control frontend config template.
* `infrastructure/monitoring/prometheus/secrets/backend_metrics_token.example` — Prometheus token template.
* `scripts/ci/generate_env_example.py` — Automated CI tool that generates `.env.example` from schemas.

**Step-3 Action:** Keep as canonical templates. Sanitize to guarantee zero mock or leaked secrets.

---

## 3. Step-3 Execution Plan

When Step-3 begins:
1. **Batch Pruning:** Remove the 6 dead Python example files (`backend/examples/`, `backend/docs/examples/`, `backend/tools/langchain_agent_example.py`, `scripts/demo_agent_communication.py`).
2. **Catalog Cleanup:** Remove entries from `MODULES_LIST.md` and `docs/generated/backend_import_graph.json`.
3. **Fixture Consolidation:** Move remaining active JSON fixtures to `tests/fixtures/`.
4. **Estimated LOC Reduction:** ~550 lines of dead code removed with zero impact on production boot.
