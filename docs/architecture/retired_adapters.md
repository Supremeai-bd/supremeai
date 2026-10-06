# Retired Adapters — Replacement Paths (issue #4057)

> **Purpose:** Document the replacement paths for adapters retired from `backend/integrations/`. This prevents future agents from re-auditing or re-implementing capabilities that SupremeAI already has natively.
>
> **Rule 4 (Evidence Before Adoption):** Every retirement has documented evidence (zero live callers + native replacement). Do NOT revive these adapters without a new audit proving the native capability is insufficient.

---

## Retired Adapters

### Browser Use (`browser_use_adapter.py`) — RETIRED + DELETED (#4044, executed #4068)

| Field | Value |
|---|---|
| **Audit issue** | #4044 |
| **Audit report** | `docs/architecture/audits/browser_use_audit.md` |
| **Execution PR** | #4068 |
| **Decision** | RETIRE + DELETE |
| **Date** | 2026-10-06 |
| **Zero callers confirmed** | Yes (grep: only `__init__.py` export) |
| **Replacement** | Native Playwright stack (15+ files) |

**Native replacements:**
- `backend/core/playwright_manager.py` — Playwright session manager
- `backend/tools/browser/playwright_browser_agent.py` — Agentic browser via Playwright
- `backend/core/browser_session_manager.py` — Session lifecycle management
- `backend/browser/autonomous_browser.py` — Autonomous browser control
- `backend/tools/browser/browser_stealth.py` — Stealth mode (anti-detection)
- `backend/tools/browser/web_scraper.py` — HTTP scraping with SSRF guard

**Why retired:** Upstream `browser_use` package was never declared in `backend/pyproject.toml` (`import_available("browser_use")` always returned `False`). Adapter had been silently running its zero-cost fallback (Jina Reader → Firecrawl → WebScraper) since it was written. Native Playwright stack supersedes.

---

### OpenHands (`openhands_adapter.py`) — RETIRED + DELETED (#4045, executed #4068)

| Field | Value |
|---|---|
| **Audit issue** | #4045 |
| **Audit report** | `docs/architecture/audits/openhands_audit.md` |
| **Execution PR** | #4068 |
| **Decision** | RETIRE + DELETE |
| **Date** | 2026-10-06 |
| **Zero callers confirmed** | Yes (grep: only `__init__.py` export) |
| **Replacement** | Native SupremeAI coder (20+ files) |

**Native replacements:**
- `scripts/agents/continuous_agent_loop.py` — CLAIM → WORK → VERIFY → PR → EXIT loop
- `backend/core/agents/framework/task_runner_agent.py` — AutonomousAgent + StepResult
- `backend/external_agents/` — providers/control/verification (native external agent governance)
- `scripts/agents/agent_identity.py` — Git-push-CAS identity + role lock
- `scripts/agents/credential_manager.py` — Infisical JIT credential minting

**Why retired:** OpenHands requires a separate agent-server deployment (`OPENHANDS_SERVER_URL`) that was never configured. `config_validation.py:259` raises `ValueError` if enabled without URL. Flag was never `true` in production. Native SupremeAI coder system supersedes. External policy escape valve avoided.

---

### mem0 (`mem0_adapter.py`) — RETIRED + DELETED (#4057)

| Field | Value |
|---|---|
| **Retire issue** | #4057 |
| **Decision** | RETIRE + DELETE |
| **Date** | 2026-10-06 |
| **Zero callers confirmed** | Yes (grep: only `__init__.py` export) |
| **Replacement** | Canonical MemoryRepository + pgvector |

**Native replacement:**
- `backend/core/ai_memory/repository.py` — Canonical persistent memory (pgvector). Single source of truth per Roadmap v2 Rule 5 (Consolidation Over Expansion).

**Why retired:** mem0 was a redundant memory layer. SupremeAI already has a canonical `MemoryRepository` backed by Supabase pgvector (Roadmap v2 Rule 5). mem0's zero-cost fallback (keyword-cosine + consolidation) was inferior to pgvector's vector similarity search. No live callers existed.

---

### E2B (`e2b_adapter.py`) — RETIRED + DELETED (#4057)

| Field | Value |
|---|---|
| **Retire issue** | #4057 |
| **Decision** | RETIRE + DELETE |
| **Date** | 2026-10-06 |
| **Zero callers confirmed** | Yes (grep: only `__init__.py` export) |
| **Replacement** | Native sandbox/docker_sandbox.py |

**Native replacement:**
- `sandbox/docker_sandbox.py` — Native SupremeAI sandbox for isolated code execution.

**Why retired:** E2B was a redundant sandbox. SupremeAI already has its own Docker-based sandbox. E2B would add an external dependency (E2B API + quota) for a capability SupremeAI has natively. No live callers existed.

---

### Graphiti (`graphiti_adapter.py`) — RETIRED + DELETED (#4057)

| Field | Value |
|---|---|
| **Retire issue** | #4057 |
| **Decision** | RETIRE + DELETE |
| **Date** | 2026-10-06 |
| **Zero callers confirmed** | Yes (grep: only `__init__.py` export) |
| **Replacement** | Native episodic + long-term memory |

**Native replacements:**
- `backend/memory/episodic_memory.py` — Time-ordered episode storage
- `backend/memory/long_term_memory.py` — Consolidated long-term store
- `backend/evolution/memory_consolidator.py` — Episodic → long-term promotion

**Why retired:** Graphiti was a redundant temporal knowledge-graph memory. SupremeAI already has native episodic + long-term memory + consolidator. Graphiti's zero-cost fallback (timestamped episode triples + recency/keyword ranking) was inferior to the native system. No live callers existed.

---

## Revival Policy (Rule 4 — Evidence Before Adoption)

If a future task genuinely needs one of these capabilities:

1. **Do NOT reopen the closed issue.** Open a NEW audit issue referencing the prior decision.
2. **Provide evidence** that the native replacement cannot meet the requirement (benchmark + gap analysis).
3. **Address the governance boundary concerns** documented in the audit reports (for Browser Use + OpenHands).
4. **Follow the Evidence Before Adoption pipeline:** benchmark → security review → maintenance cost → decision.
5. **If approved**, implement as a Governed Provider (Roadmap v2 Phase 2.3 pattern) — NOT as a direct dependency.

---

## Cross-References

- **Capability Inventory:** `docs/architecture/CAPABILITY_INVENTORY.md` §1 (Integration Adapters)
- **Machine-readable inventory:** `docs/architecture/inventory.yaml` (tier: retired entries)
- **Browser Use audit:** `docs/architecture/audits/browser_use_audit.md` (#4044)
- **OpenHands audit:** `docs/architecture/audits/openhands_audit.md` (#4045)
- **Roadmap v2 §1.2:** `docs/architecture/ECOSYSTEM_INTELLIGENCE_ROADMAP.md` — Orphaned Adapter Audit
- **Roadmap v2 Rule 4:** Evidence Before Adoption
- **Roadmap v2 Rule 5:** Consolidation Over Expansion

---

*Bengali note (AGENTS.md Rule #6): এই ডক ৫টি retired adapter-এর replacement path নথিভুক্ত করে — Browser Use (#4044), OpenHands (#4045), mem0 (#4057), E2B (#4057), Graphiti (#4057)। সবই zero live caller ছিল এবং native capability দ্বারা প্রতিস্থাপিত। ভবিষ্যতে revive করতে হলে নতুন audit issue খুলতে হবে — পুরনো issue reopen করবে না। Evidence Before Adoption (Rule 4) বাধ্যতামূলক।*
