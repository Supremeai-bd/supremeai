# SUPREMEAI DISTRIBUTED MULTI-AGENT WORKSPACE REGISTRY (SHARED BLACKBOARD)

This living registry synchronizes work across all concurrent/sequential AI agents (Gemini, Claude, Kilo, Cline, Antigravity, Cursor, etc.). It enforces the **Recon-First, Issue-Driven, Non-Regression Lifecycle** defined in [.agents/rules/supremeai_universal_guardian.md](file:///f:/supremeai/.agents/rules/supremeai_universal_guardian.md).

---

## 📌 PROTOCOL FOR ALL AGENTS

1. **Step 1 — Full Recon First:** Before editing, run automated checks (builds, tests, linters, git status) to see if existing features are broken.
2. **Step 2 — Register Discovered Issues:** If bugs, regressions, or drift are detected from prior features, append them under `## 📋 UNRESOLVED ISSUES & DISCOVERED GAPS`.
3. **Step 3 — Claim or Pick Alternative:** 
   - Check `## 🚀 ACTIVE WORK IN PROGRESS`. 
   - If an issue or file is already claimed by another agent, **DO NOT TOUCH IT**. Pick the next unassigned issue.
   - Record your claim under `## 🚀 ACTIVE WORK IN PROGRESS` with your Agent Name, Intent, and Target Files.
4. **Step 4 — Non-Regression Verification:** After coding, verify your changes AND run regression tests to ensure prior features remain 100% intact.
5. **Step 5 — Peer Review / Release:**
   - If peer verification is required, change status to `PENDING_PEER_REVIEW`.
   - Once verified and passing, remove your entry from `ACTIVE WORK IN PROGRESS`, log in `## ✅ RECENTLY VERIFIED & RELEASED (LAST 10)`, and clear the issue from `UNRESOLVED ISSUES`.

---

## 🚀 ACTIVE WORK IN PROGRESS (LOCKED BY AGENTS)

<!--
Format for claiming work:
- **Agent:** [e.g., Agent-Gemini-1 / Agent-Claude-2 / Agent-Cursor]
  - **Issue / Goal:** [Brief description of the task being executed]
  - **Target Files / Scope:** [list of files or directories being modified]
  - **Status:** [IN_PROGRESS | PENDING_PEER_REVIEW]
  - **Started At:** [Timestamp]
-->

*(No active locks currently. The workspace is clear for recon and task claiming.)*

---

## 📋 UNRESOLVED ISSUES & DISCOVERED GAPS (AUDIT QUEUE)

<!--
Format for logged issues from recon:
- [ ] **[ISSUE-ID]**: [Summary of issue or regressed feature] | Priority: [CRITICAL|HIGH|MEDIUM|LOW] | Found By: [Agent Name] | Impacted Components: [paths]
-->

*(No unresolved issues logged. Run a system health/build audit to discover and record gaps.)*

---

## 🛡️ FEATURE INVARIANTS & PRESERVED CONTRACTS (DO NOT BREAK)

When working in the codebase, you MUST NOT silently disable or break the following core features established by previous agents:
1. **SRE Mission Control Dashboard:** Complete frontend views (Command Deck, Log Stream, Governance HITL Queue, AI Router, Topology, Alerts, Vault).
2. **AI Routing Strategy:** Exhaust Tier-0 (Free/Local) providers before Tier-1 (Paid Quarantined).
3. **Emergency Kill-Switch:** Preserves read-only telemetry mode when autonomy is disengaged.
4. **Tenant & RLS Scoping:** Never bypass database tenant isolation or multi-tenant contracts.
5. **Zero-Gap Execution:** Mocks or superficial stubs without real functional engine are forbidden.

---

## ✅ RECENTLY VERIFIED & RELEASED (AUDIT TRAIL)

<!--
Keep last 10 completed and peer-verified items here for context:
- **[Date]** [Agent Name] completed [Task] - Verified with [Test/Proof]
-->
