# SUPREMEAI DISTRIBUTED MULTI-AGENT WORKSPACE REGISTRY (SHARED BLACKBOARD)

This living registry synchronizes work across all concurrent/sequential AI agents (Gemini, Claude, Kilo, Cline, Antigravity, Cursor, etc.). It enforces the **Recon-First, Issue-Driven, Non-Regression Lifecycle** defined in [.agents/rules/supremeai_universal_guardian.md](file:///f:/supremeai/.agents/rules/supremeai_universal_guardian.md).

---

## 📌 PROTOCOL FOR ALL AGENTS

1. **Step 1 — Full Recon First:** Before editing, run automated checks (builds, tests, linters, git status) to see if existing features are broken.
2. **Step 2 — Register Discovered Issues (GitHub First):** 
   - Open a GitHub Issue: `gh issue create --title "[<Category>] <Title>" --body "<Specs>" --label "enhancement"`
   - If GitHub is unreachable (offline fallback), append under `## 📋 UNRESOLVED ISSUES & DISCOVERED GAPS`.
3. **Step 3 — Claim or Pick Alternative (Process Sign & Working Assignment):** 
   - Check open GitHub Issues (`gh issue list --state open`). Avoid any issue marked `in-progress`.
   - **Assign Working Sign on GitHub:**  
     `gh issue edit <id> --add-label "in-progress"`
   - **Post Agent Heartbeat Comment:**  
     `gh issue comment <id> --body "🤖 **[Work Claimed]** Agent: <Name> | Branch: feat/issue-<id>-<slug> | Started: <Timestamp>"`
   - Cut dedicated branch: `feat/issue-<id>-<slug>`.
   - Record claim under `## 🚀 ACTIVE WORK IN PROGRESS` if working in a shared local filesystem workspace.
4. **Step 4 — Non-Regression Verification:** After coding, verify your changes AND run regression tests to ensure prior features remain 100% intact.
5. **Step 5 — Peer Review / Auto-Close Release:**
   - When PR is opened, include `Fixes #<id>` in description.
   - Update issue label: `gh issue edit <id> --remove-label "in-progress" --add-label "in-review"`
   - Once merged, GitHub automatically closes the issue! Remove local entry from `ACTIVE WORK IN PROGRESS`.

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
- **2026-09-19 00:34 (+06)** Agent-Cline completed Crown Jewel Module 18 §P-B (Telegram admin-identity truth) — `handler.py` `_configured_admin_ids()` + sender-aware `is_admin(chat_id, user_id)`, fail-closed, zero hardcode; sender propagation through `updates.py` / `keyboards.py` / `conversations.py`; hardcoded personal admin ID removed from `admin_handlers.py`; new suite `backend/tests/security/test_telegram_admin_identity.py` (12/12 PASS). Verified with `pytest tests/security tests/tools/test_teldrive_storage.py` → 353/353 PASS (`DATABASE_URL=sqlite+aiosqlite:///./test.db`), `ruff format --check` + `ruff check` clean, doc-regeneration diff gate clean. Landed on `main` as `52fa97da`.

  > **Workspace coordination note:** this workspace is **live-shared**. An automated committer/agent ("SupremeAI Agent") committed, merged, and pushed during this session (`3d2ba273`, `52fa97da`, `2687a346`, `afe5429a`) and renamed `docs/plans/crown_jewel_series/*` (date suffixes dropped). Peer agents: re-verify file paths and `git log` before assuming a plan path, and expect a clean-tree state to change under you.
- **2026-09-16 05:35 (+06)** Agent-Zai-Code completed ERR-A01/A02/A05 agent-execute contract repair (`agentService.ts`, `AgentWorkspace.tsx` + coherent test updates) - Verified with `tsc --noEmit` PASS, targeted vitest 15/15 PASS, full frontend suite 486/486 PASS (94 files), eslint clean on all 4 changed files. Delivered via PR `fix/agent-execute-contract-a01-a02-a05`.
