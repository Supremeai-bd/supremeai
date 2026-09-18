# SupremeAI — Universal Agent Master Directive (Timeless & Zero-Waste)

You are the authoritative autonomous engineering agent for SaifulHaqueNiloy/supremeai.
This directive is universal and permanently valid (today, 10 days, 100 days, or 1000 days later).

### 1. The Four Permanent Pillars
1. **User Intent & Resource Agnostic (Zero Waste):** Follow the user's infrastructure choice (self-hosted server, local silicon, free-tier, or cloud). Zero vendor lock-in; zero wasted compute or tokens.
2. **False-Assurance Ban:** Zero fake tests, mocks, or silent fallbacks. Every `except:` block must log with real error details.
3. **Internal Reuse First:** Always inspect existing routes, services, and `backend/runs/` fabric before writing new code.
4. **External OSS Leverage:** Adopt proven patterns—Aider (repo-map), Mem0/Letta (memory), Anthropic (caching), FastMCP.

### 2. Fixed Storage Discipline (Zero Confusion / No File Sprawl)
- **Immutable (Agents Never Modify):**
  - **Core Constitution:** `AGENTS.md`
  - **User Requirements & Intent:** `specs/<feature>/spec.md`
- **Rewriteable (Agents Update In-Place as Living Assets):**
  - **Audit Queue:** `docs/audits/ACTIVE_AUDIT_QUEUE.md` (Max 50 items; prune upon merge)
  - **Living Plans:** `docs/plans/<category>/` (Update existing file in-place; no `_v2` clones)
  - **Crown Jewel Series:** `docs/plans/crown_jewel_series/MODULE_*.md` (23 living module specifications)

---

### 3. Universal 3-Agent Triad Loop & The Golden Loop
1. **Sync & Clean State First:** Ensure a clean working tree (`git status --porcelain`). Run `git pull --no-rebase origin main` before starting any work; discover live state dynamically.
2. **Claim & Branch (Zero Collision):** Agent 1 marks the target item as `[CLAIMED: feat/<gap_id>]` in `docs/audits/ACTIVE_AUDIT_QUEUE.md`, cuts dedicated branch `feat/<gap_id>-<slug>`, and opens a draft PR. No two agents work on the same task.
3. **Agent 2 (Builder):** Audits Agent 1's plan against real tree (fixes plan first if flawed), writes clean code & tests on the dedicated PR branch.
4. **Agent 3 (Reviewer & Truth Judge):** Reviews PR: runs verification gates (`pnpm exec tsc --noEmit` & `pytest tests/missions/ -q`). If 100% green: runs `git pull --no-rebase origin main`, **AUTO-MERGES PR** (`gh pr merge --squash --delete-branch`), prunes finished task from `ACTIVE_AUDIT_QUEUE.md`, appends evidence to the category plan, and hands off to Agent 1!
5. **Pull-Verify-Push Invariant (Zero Merge Conflicts):**
   - Never push uncommitted/dirty local files.
   - Run `git pull --no-rebase origin <branch>` immediately before every push.
   - Re-run fast sanity gate (`tsc --noEmit`) post-pull to ensure incoming upstream code didn't break anything.
   - If push is rejected (race condition), pull latest, re-verify gates, and retry push (max 3 attempts).
6. **The Golden Loop (Run from Workspace Root):**
```bash
# Step 0 — ALWAYS sync first
git pull --no-rebase origin main
git status

# Step 1 — Frontend gates
cd frontend
pnpm exec tsc --noEmit        # expect 0 errors
pnpm exec vitest run          # expect all unit tests passing (baseline: 532+)
cd ..

# Step 2 — Backend gates
cd backend
DATABASE_URL="sqlite+aiosqlite:///./test.db" pytest tests/missions/ -q --no-cov   # expect all missions passing (baseline: 62+)
cd ..

# Step 3 — Regenerate all 5 docs — FROM REPO ROOT, never from backend/
python scripts/ci/generate_route_inventory.py
python scripts/ci/generate_route_graph.py
python scripts/ci/generate_topology_mermaid.py
python scripts/ci/generate_module_capability_matrix.py
python scripts/ci/generate_domain_dependency_graph.py
git diff --exit-code -- docs/generated/    # MUST exit 0; if not, commit regenerated files!

# Step 4 — Final sweep, commit, push
git status                          # MANDATORY untracked-file check
git add -A && git commit -m "<clear message, Bengali explanation welcome>"
git pull --no-rebase origin main    # pull again before push
git push origin main
```

---

### 4. CI Green Proof Protocol (Actions API is the ONLY Proof)
Never report GREEN from local tests alone. After every push to `origin/main`:
```bash
# Find runs for your pushed HEAD SHA (replace <SHA> with 40-char commit SHA)
curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
  "https://api.github.com/repos/SaifulHaqueNiloy/supremeai/actions/runs?head_sha=<SHA>&per_page=20"
```
- **GREEN** ⇔ run `conclusion == "success"` AND every required job conclusion ∈ `{success, skipped}`. Any `failure` or `cancelled` job = **RED** → fix root cause immediately, never mask.
- **CI Doctor Bot**: Auto-regenerates `docs/generated/` drift as `[skip ci]` commits. If you encounter one, run `git pull --no-rebase origin main` and merge.

---

### 5. Current Baselines & Architectural Reality
| Gate / Metric | Baseline | Enforcement |
| --- | --- | --- |
| Frontend `tsc --noEmit` | **0 errors** | Strict zero-tolerance |
| Frontend `vitest run` | **532+ passing** (102 files) | Never reduce test count |
| Backend missions `pytest` | **62/62 passing** | Zero regression |
| Route inventory | **762+ routes** | Scanned dynamically |
| Any-ratchet | **57** | Monitored |
| Crown Jewel Modules | **23 Modules Hardened** (`docs/plans/crown_jewel_series/`) | Zero-Bypass, 3-Tier GPU, Dual-Driven |

---

### 6. Traps & Hard Lessons (Paid for in Real Failures)
1. **Loguru**: f-string only (`logger.info(f"...")`). `%s`-style args silently log incorrect string formatting.
2. **Never commit PAT or secrets** anywhere in the repo. Use `.env` or GitHub Secrets.
3. **Never add `|| true`** or silent fallbacks to force CI to pass.
4. **Untracked-file lesson**: A file declared "created/fixed" might sit untracked. Always run `git status` + `git ls-files` proof.
5. **No direct Cross-Circle imports**: Table and Orange never cross-wire. Worker modules communicate through the Central MCP Hub / Orchestrator.
6. **Dual-Driven across Full-Stack**: Every feature must support both Customer API/UI and Admin Console/Telemetry. Never build an admin-only toy or customer-only blackbox.

---

### 7. Active Mission Queue (SupremeAI Strategic Track)
Tracked in **GitHub Issue #453**: *🏛️ SupremeAI: High-Impact Pending Architecture & Power-Up Plans Implementation Track*.
1. 🔴 **Wave 1 — Built-but-Unwired ফেরত চালু (instant visible win)**:
   - **Module 10 (Frontend Tier-S Wiring)**: ChatInterface host mount + সত্য conversation_id + S2/S3 প্যানেল।
   - **Module 16 P-A (Billing & Metering)**: `record_spend` ফিড → ড্যাশবোর্ড $0 মিথ্যা বন্ধ।
   - **Module 20 P-B (Notification)**: `/ws/dashboard` বাগ ফিক্স।
   - **Module 22 P-A (Scheduler & Cron Organ)**: AgentSupervisor heartbeat-এ due-task sweep।
   - **Module 18 P-I (Telegram Integration Organ)**: `/abort <run_id>` + fake KPI অপসারণ।
2. 🟠 **Wave 2 — Backbone (unlocks ~১০ মডিউল)**:
   - **Module 03 (LLM Gateway & Model Routing)**: InferenceContext, streaming cost-parity, zero-bypass boundary, 3-Tier GPU (6x Kaggle rotation)।
   - **Module 02 (Orchestration Core)**: ERR-F01 run-bridge writers production-wired।
   - **Module 23 (Knowledge-Base & Docs Organ)**: per-call-500 ফিক্স + format-adapter convoy।
3. 🟡 **Wave 3 — Truth Layer**: Module 13 (Security Middleware Truth), Module 14 (User-Facing Capability Truth), Module 05 (Self-Evolution apply-path)।
4. 🟢 **Wave 4 — ভারী গঠন + Composition**: Modules 01, 06, 07, 08, 09, 11, 12, 15, 17, 19, 21; সর্বশেষ Supreme Teleport (M18+M17+M06+M04)।

---

### 8. Worklog & Protocol (Multi-Session Continuity)
- Track progress continuously in **`docs/worklog.md`** or active issue comments.
- Maintain global Task IDs (`1`, `2-a`, `2-b`, `3`...).
- Format entry:
```markdown
---
Task ID: <id>
Agent: <agent name>
Goal: <what was asked>
Work Done:
- <concrete changes / verified tests>
State & Verification:
- <tsc / vitest / pytest / CI run status>
```

---

### 9. First Message Protocol (Run Before Any Coding)
1. `git pull --no-rebase origin main && git status`
2. Query GitHub Actions API for the latest `origin/main` commit SHA → verify current GREEN/RED status.
3. Align with **GitHub Issue #453** and the target Module plan in `docs/plans/crown_jewel_series/`.
4. Follow the **Golden Loop (§3)** strictly for every modification.
