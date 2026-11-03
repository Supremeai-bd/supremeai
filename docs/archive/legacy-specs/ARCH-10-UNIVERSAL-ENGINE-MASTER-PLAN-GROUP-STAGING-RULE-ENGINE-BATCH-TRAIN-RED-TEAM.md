# ARCH-10 — Universal Engine Master Plan: Group-Scoped Staging, Rule-Repackaged Auditor, Batch Train Engine এবং Red Team Adversary Protocol

> **ডকুমেন্ট আইডি:** ARCH-10 · **স্ট্যাটাস:** ড্রাফট (DRAFT — Founder Approved Roadmap) · **ভার্সন:** ১.০ (২০২৬-০৯-২৮)  
> **প্রযোজ্য:** সুপ্রিমএআই প্ল্যাটফর্মের মাল্টি-এজেন্ট ফ্লিট, Universal Solver Engine, CI/CD কন্সটিটিউশন এবং অ্যাডভার্সারিয়াল হার্ডেনিং প্রোগ্রাম।  
> **মূল রেফারেন্স:** [`ARCH-01`](ARCH-01-MASTER_CONSTITUTION.md) · [`OPS-05`](OPS-05-PR-HELPER-LIFECYCLE.md) · [`OPS-06`](OPS-06-MULTI-AGENT-BRANCHING-LIFECYCLE.md) · [`OPS-09`](OPS-09-POST-GROUP-JANITOR-AND-HYGIENE-PROTOCOL.md) · [`AGENTS.md`](../../AGENTS.md) (Living Protocols 1–10)  
> **ল্যান্ডিং টার্গেট:** Phase A = ইস্যু #2277 → #2328 → Batch Landing → Janitor · Phase B = Rule Engine → Orchestrator → 22→5 Workflow Consolidation → Step-3 · Phase C = Red Team Agent

---

## 🎯 পর্ব ০: মূল উদ্দেশ্য ও দর্শন (Core Philosophy)

### ০.১ Universal Solver Model
পুরনো multi-agent system-এর artificial silos (Coder vs Planner vs PR Helper) সম্পূর্ণ বাদ দিয়ে **"Universal Solver Model"**-এ রূপান্তর। যেকোনো এজেন্ট যখন আসবে, সে শুধু একটাই কাজ করবে: **"Issue দেখবে, পুরো কাজ শেষ করবে"** — No guessing, no role drama।

### ০.২ Group-Scoped Staging Law (GSPQ)
কোনো single PR একা একা `main`-এ merge হবে না। পুরো group-এর সব PR staging-এ থাকবে (`queue:hold`)। Full group-এর কাজ শেষ হলে automated orchestrator সব diff একসাথে macro audit করবে (101% real benefit ও zero regression verify করবে), তারপর **Merge Train Rollup**-এর মাধ্যমে পুরো group একসাথে single batch-এ `main`-এ land করবে। এরপর [OPS-09](OPS-09-POST-GROUP-JANITOR-AND-HYGIENE-PROTOCOL.md) Janitor সব stale branch ও label instant clean করে দেবে।

### ০.৩ Rules-as-Code নীতি
১০০০ rule থাকলেও সবগুলো Python rule engine-এ কোড হিসেবে থাকবে — এজেন্টদের মাথায় prompt বোঝানো হবে না। Almost dynamic, zero technical hassle, deterministic execution।

### ০.৪ 🆕 Adversarial Ratchet নীতি (Red Team)
প্রতিরক্ষা তখনই প্রমাণিত, যখন আক্রমণ অভ্যাসে পরিণত হয়। একটি স্থায়ী **Red Team Agent** প্রতিদিন নিয়ম ভাঙার ও হ্যাক করার চেষ্টা করবে — প্রতিটি blocked attack হবে গেট-কনফিডেন্সের প্রমাণ, আর প্রতিটি breach হবে একটি P0/P1 hardening ইস্যু। **একবার একটি attack block হওয়ার পর সেটি permanently probe battery-তে যুক্ত হবে — ওই ভাঙন আর কখনো ফিরে আসতে পারবে না (Ratchet Effect)।**

---

## 📊 পর্ব ১: বর্তমান অবস্থার সম্পূর্ণ ম্যাপিং (As-Is Evidence — 2026-09-28, main @ `b8cabe29`)

### ১.১ Main Branch State

| বিষয় | অবস্থা | প্রমাণ (commit/PR) |
|---|---|---|
| Phase-0 Governance | ✅ Landed | `b8cabe29` — Hard Rule 5, OPS-09 doc, `group_closeout_janitor.py`, `create_group_issue.py`, ২টি inventory doc |
| Step-2.1 (#2274) | ✅ Merged | `82f814a4` (PR #2322) — in-memory handoff events অবসর |
| Step-2.2 (#2275) | ✅ Merged | `e1c7ba20` (PR #2325) — swarm orchestrator অবসর, ~−2,388 লাইন |
| Step-2.3 (#2276) | 🔄 PR held | PR **#2345** — ৯ ফাইল, ~−1,207 লাইন, gate-passed, `queue:hold` |
| Step-2.4 (#2277) | 🔄 আংশিক | PR **#2327** মাত্র `__all__` residue (−5 লাইন); `ephemeral_synthesizer.py` (211 ln) **এখনো main-এ জীবিত** |
| Step-2.5 (#2328) | ⏳ Unclaimed | `handoff:planner` — পুরো group-এর harvest audit gate |
| #2317 (P0 catalog) | ✅ Closed | MODULES_LIST truth-sync সম্পন্ন |

### ১.২ শিক্ষা: PR #2326 Supersession Lesson (Institutionalized)
PR #2326 (আগের Step-2.4 attempt) বন্ধ হয়েছে: *"superseded by #2327 — cleanly resolved **without docs drift**"*। মূল কারণ: surgical deletion-এর সাথে **+10,263/−3,896 লাইনের `openapi.json` artifact regen মিশে গিয়েছিল**।

> 📌 **নিয়ম (আজ থেকে permanent):** Deletion/cleanup PR-এ কখনো artifact regen mix করা যাবে না — surgical PRs only। Artifact regen আলাদা `artifact-regen.yml` bot-এর কাজ।

### ১.৩ PR Queue — ১৪টি PR সবই ফ্রোজেন 🧊

সবগুলো open PR `queue:pending-rollup` + `queue:hold`-এ আটকে আছে (verified: `merge_train_rollup.py:59` → `EXCLUDE_LABELS = ("queue:hold", ...)` — hold থাকলে train batch-এ নেয় না):

```
group:step-2 (৩):  #2345 (seq:3) · #2327 (seq:4) · <আসন্ন seq:4 surgical redo PR>
স্বতন্ত্র fix (১১): #2343 · #2342 · #2340 · #2339 · #2338 · #2336 · #2335 ·
                     #2332 · #2245 · #2176 · #2175 · #2171
```

**Landing mechanics:** hold-release + `integration-gate` workflow_dispatch (bot actor-এর `labeled` event GitHub-suppressed — dispatch-ই নির্ভরযোগ্য লিভার)।

### ১.৪ Infrastructure Gap Analysis

| Module | লক্ষ্য | বর্তমান অবস্থা |
|---|---|---|
| `scripts/ci/auditor_rule_engine.py` | Step 2 | ❌ MISSING — নতুন বানাতে হবে |
| `scripts/ci/group_batch_orchestrator.py` | Step 3 | ❌ MISSING — নতুন বানাতে হবে |
| `scripts/ci/group_closeout_janitor.py` | Step 4 | ✅ EXISTS (main @ b8cabe29) — #2331 bind + close বাকি |
| `acquire_role_slot.py` self-healing | Step 3.5 | 🟡 আংশিক — open-PR fetch (L139) + occupancy detect (L256) + has-pr skip (L388) আছে; **has-pr label auto-writeback + seq K+1 unblock নেই** |
| `.github/workflows/` consolidation | Phase 3 | ❌ ২২টি ফাইল (লক্ষ্য: ৫টি) |

### ১.৫ 💎 মূল আবিষ্কার: ৩টি Unwired Gate = নতুন প্ল্যানের Reserved Slot

`.github/constitution/rules.yml`-এর gates সেকশনে ঠিক ৩টি gate `wired: false` — নতুন প্ল্যানের module গুলো সংবিধানে ইতিমধ্যে রিজার্ভকৃত:

| Unwired Gate (rules.yml) | নতুন প্ল্যানের Implementation |
|---|---|
| `test_guard_gate` — *"constitution audit engine extension"* | → **`auditor_rule_engine.py`** |
| `post_merge_watch` — *"merge-train land job"* | → **`main-land.yml`** 15-min auto-revert watch |
| `self_merge_gate` — *"branch protection follow-up"* | → Branch protection + red-team probe |

অর্থাৎ এই মাস্টার প্ল্যান নতুন কিছু চাপাচ্ছে না — **সংবিধান নিজেই এদের জায়গা রিজার্ভ করে রেখেছে।** এটাই প্ল্যানের legitimacy-র প্রমাণ।

---

## 🏁 পর্ব ২: Phase A — Step-2 সমাপ্তি ও Batch Landing (আগে এটা)

### A1: #2277 Surgical Redo (🥇 Head of the Queue — founder-sanctioned)

মাত্র **৪ ফাইল, ~−435 লাইন**, কোনো artifact regen নয়:

| ফাইল | অ্যাকশন | Evidence |
|---|---|---|
| `backend/tools/ephemeral_synthesizer.py` (211 ln) | **DELETE** | 0 production importer (coder-1 correction confirm: `codegen_gate.py:3` comment-only ref) |
| `backend/tests/test_swarm_and_ephemeral.py` (47 ln) | **DELETE পুরোটা** | Post-#2325 ফাইলটি ephemeral-only — উভয় test-ই synthesizer import করে |
| `backend/tests/security/test_codegen_gate_fail_closed.py` (150 ln) | **TRIM** — ২টি ephemeral test বাদ (L35-66) + import + docstring | রাখব: tool_forge×2, safe_executor×2, skill_manager×1 — Test Guard satisfied (শুধু deleted module-এর test retire) |
| `backend/core/security/codegen_gate.py:3` | Comment ref পরিষ্কার | 1-line docstring mention |

**যাচাই:** 3-Tier (reflection grep → boot smoke → targeted pytest `tests/security/test_codegen_gate_fail_closed.py` + `tests/test_swarm_and_ephemeral` absence check)। PR body-তে #2326-closure প্রসঙ্গ উল্লেখ করে "no docs drift" guarantee। #2327-এর সাথে **zero collision** (disjoint files)।

### A2: #2328 — Step-2.5 Capability Harvest & Benefit Audit (Planner Lane)

পুরো group-এর gate। Audit বিস্তার:

```
Audit対象:  PR #2322 (merged) + #2325 (merged) + #2345 (held) + #2327 (held) + <A1-PR>
মোট ছাঁটাই: ~−5,400+ লাইন (2.1 −1,4xx + 2.2 −2,388 + 2.3 −1,207 + 2.4 −440)
```

**4-Pillar Checklist (Protocol 9):**
1. **Zero Capability Loss:** প্রতিটি deleted ফাইলের algorithm/prompt/memory-handler কি canonical system-এ reuse-যোগ্য ছিল? (বিশেষ যাচাই: `swarm_pubsub`-এর Redis-backed TTL purge, `agent_mailbox`-এর topic_subscribe pattern → উভয়ই Supabase Collective Memory/GitHub threads দিয়ে covered কি না)
2. **101% Real Benefit:** Bug source স্থায়ীভাবে বন্ধ? সিস্টেম হালকা অথচ বেশি কর্মক্ষম?
3. **Zero Regression:** পুরো group diff একসাথে apply করে boot smoke + full shard
4. **Verdict:** #2328-এ evidence comment → `group:step-2` completion ঘোষণা

### A3: Hold-Release → Merge Train Batch Landing

```
1. Audit PASS হওয়া মাত্র: ধাপে ধাপে queue:hold remove (group:step-2 PRs আগে)
2. ১১টি non-group held PR founder-approval-এ release
3. workflow_dispatch integration-gate → batch formation from queue:pending-rollup
4. Single batch-এ main-এ land → linked issues cascade-close (#2276, #2277, #2328)
```

> ⚠️ ১৪-PR একসাথে বড় batch — প্রয়োজনে ২ ব্যাচে ভাগ (group:step-2 আগে, fix-PRs পরে)। Strict single-flight rule বজায় থাকবে (একসাথে ১টি inflight batch)।

### A4: OPS-09 Janitor Clean + #2331 Close

```bash
python scripts/ci/group_closeout_janitor.py --group step-2   # প্রথমে dry-run, তারপর --apply
```
→ Stale remote branch purge + temporary label strip (queue:hold, has-pr, status:in-progress) + #2331 (OPS-09 binding) close।

---

## 🏗️ পর্ব ৩: Phase B — Rule Engine, Orchestrator ও Self-Healing

### B1: `scripts/ci/auditor_rule_engine.py` — Pluggable Rule Engine (Step 2)

পুরনো সব protocol/gate Python function হিসেবে repackage — ১০টি rule module:

| পুরনো Protocol/Gate | Main File (বর্তমান) | New Module | দায়িত্ব |
|---|---|---|---|
| Protocol 1: Slot Lease | `scripts/agents/acquire_role_slot.py` | `rules.lease_guard` | Slot gap (1..N) check ও branch lease control |
| Protocol 2 & 4: Blast Radius | `scripts/ci/atomic_claim.sh`, Scope Gate | `rules.scope_guard` | Max 1-2 files diff, declared files strict check |
| Protocol 3: 3-Tier Verification | CI Verification Gate | `rules.verification_guard` | Reflection + Boot smoke (`python -c "import main"`) + Pytest |
| Protocol 5: Mandatory has-pr | Label check | `rules.pr_lifecycle_guard` | Duplicate PR stop — instant has-pr label + auto-recovery |
| Protocol 6: Collision Gate | `cross_pr_collision_detector` (pr-gate job) | `rules.collision_guard` | Active PR-দের মধ্যে direct file collision block + draft-exclusion |
| Protocol 7: Group Staging | GSPQ + `issue_queue_manager.py` | `rules.group_staging_guard` | Group PR `queue:hold`-এ lock; isolated merge বন্ধ |
| Protocol 8: Control Tower | `scripts/agents/mcp_tower_client.py` | `rules.tower_presence_guard` | MCP mesh-এ agent presence ও slot liveness verify |
| Protocol 9: 4-Pillar Harvest | 4-Pillar Rubric | `rules.composite_harvest_guard` | Full group diff audit: Zero Loss, Real Benefit, No Regression |
| OPS-09: Zero-Debris | `scripts/ci/group_closeout_janitor.py` | `rules.janitor_purge_guard` | Merged branch, temporary label ও scratch purge |
| 🆕 Test Guard (unwired) | rules.yml reserved slot | `rules.test_guard` | Test delete/skip/threshold-নামানো BLOCK — সংবিধানের রিজার্ভকৃত gate-এর implementation |

**Architecture নীতি:**
- প্রতিটি rule = `check(context) -> RuleResult(passed, evidence, remediation)` — pure function, deterministic
- Engine = registry + parallel execution + single JSON report
- **Reverse-Gated Execution:** PR-এ শুধু প্রাসঙ্গিক gate চলবে (coder PR → lease/scope/verification/collision; merge-train → harvest/collision only; main-land → কিছুই না)
- ১০০০ rule হলেও seconds-এ সম্পন্ন — agents-এর prompt-এ কোনো rule বোঝানোর দরকার নেই

### B2: `scripts/ci/group_batch_orchestrator.py` — Group Lifecycle Automation (Step 3)

State machine: `group:open → all-PRs-gate-passed → audit-ready → audit-passed → hold-release → train-dispatch → landed → janitor → group:closed`

- Group-এর সব PR `queue:hold`-এ lock রাখা
- Full group complete হলে P0 Macro Review (Protocol 9) trigger
- Sign-off-এর পর `merge_train_rollup.py` চালু
- OPS-09 Janitor-এর সাথে auto-wire (A4-এর manual কাজগুলোই ভবিষ্যত group-এর জন্য automated)

### B3: Self-Healing সম্পূর্ণকরণ — `acquire_role_slot.py` (Step 3.5)

| ফিচার | বর্তমানে | কাজ |
|---|---|---|
| Open-PR fetch + head-branch থেকে issue inference | ✅ আছে (L139-155) | — |
| Occupancy reason: "Active open PR exists for branch" | ✅ আছে (L256) | — |
| `has-pr`/`status:in-progress` skip | ✅ আছে (L388) | — |
| **has-pr label auto-writeback** (PR খোলা কিন্তু label মিসিং → auto-set) | ❌ নেই | ~৩০ লাইন addition: PR head-branch → issue# parse → `gh issue edit --add-label has-pr` |
| **Staging-aware seq K+1 unblock** (seq:K staging-এ থাকলেও K+1 claimable) | ❌ নেই | শর্ত: seq:K-এর PR verified থাকলে successor unblock |
| **Draft auto-isolation** (পরের seq-এর draft PR আগের seq-কে block করতে পারবে না) | 🟡 collision detector-এ partial | collision_guard-এ draft-exclusion policy formalize |

### B4: ২২ → ৫ Workflow Consolidation (Steps 10-15) — ৩টি সংশোধনসহ

**🔒 অপরিহার্য Sequencing Law:** Queue না land হওয়া পর্যন্ত workflow rename/consolidation শুরু হবে না — ১৪টি held PR পুরনো workflow name-এর check-run-এর উপর চড়ে আছে; mid-flight rename = সব check reference ভাঙা।

**সংশোধনী (মূল mapping-এ ৩টি বাগ):**

| # | সংশোধন | কারণ |
|---|---|---|
| ১ | `ci.yml` mapping-এ ছিল না → **pr-gate.yml-এ fold** | ci.yml = main CI pipeline (backend tests) — reverse-gated model অনুযায়ী full suite PR level-এ |
| ২ | `reusable-e2e-runner.yml` = `workflow_call` library → **caller migrate আগে, তারপর fold (ops-console-এ adhoc E2E)** | Caller na migrate করে fold করলে breakage |
| ৩ | Ghost workflow `setup-branch-protection.yml` — API-তে "active" কিন্তু ডিরেক্টরিতে নেই | Consolidation PR-এ note রাখা হবে, বিভ্রান্তি এড়াতে |

**চূড়ান্ত Mapping (22 → 5, 17 purge — গণিত মিলবে ✓):**

```
pr-gate.yml (Gatekeeper)      ← pr-gate + system-gates + pr-helper(checks)
                                 + slot-registry-drift + ★ci.yml
merge-train.yml (Consolidator)← integration-gate + pr-helper(rollup)
                                 + merge_train_rollup wrapper
main-land.yml (Live Guard)    ← ci-deploy-production + staging-deploy
                                 + 09-post-deploy-smoke + auto-delete-closed-pr-branch
                                 + artifact-regen + audit-release
scheduled-sweeps.yml (Hygiene)← nightly-ops + issue-ops + ci-doctor
                                 + 08-production-preflight
ops-console.yml (Emergency)   ← ops-console + ci-advanced-checks + ci-docker
                                 + ci-mcp-build + qa-contract
                                 + ★reusable-e2e-runner (caller-migrated)
```

**Reverse-Gated ৫-পাইপলাইন দায়িত্ব ম্যাট্রিক্স (Zero Redundancy):**

| Workflow | Trigger | কাজ | যা করবে না |
|---|---|---|---|
| `pr-gate.yml` | `pull_request` | সম্পূর্ণ gatekeeper: Lease, Scope (1-2 files), Collision, Reflection, Boot smoke, **Full Unit+Regression Suite** → সব সবুজ হলে `queue:hold` + `has-pr` sync | Production deploy নয়, merge নয় — *খারাপ কোড staging-এ ঢুকবেই না* |
| `merge-train.yml` | dispatch / `queue:pending-rollup` | Non-overlapping batch rollup, 4-Pillar Macro Audit, fast squash merge, issue cascade-close | PR-এ পাস করা check-এর পুনরাবৃত্তি নয় (No double testing) |
| `main-land.yml` | `push: [main]` | Production Deploy (Render/Cloudflare), Post-Deploy Smoke, **15-Min Auto-Revert Watch**, artifact regen, OPS-09 Janitor trigger | NO basic unit tests, NO linting — *merge-train-এর আগেই 100% verified* |
| `scheduled-sweeps.yml` | cron (৪-৬ ঘণ্টা) | External Infra Audit (Render/Supabase/Cloudflare/Infisical/Redis via MCP), Stale lease/lock/branch sweep, backlog health, constitution drift audit | Code push ছাড়া rebuild নয় |
| `ops-console.yml` | manual dispatch | Kill-switch (`autonomy_kill_switch`), manual deploy/rollback, manual janitor, adhoc diagnostics | Background-এ কখনো নয় — manual only |

### B5: Step-3 Consolidation Group (Phase 4)

`create_group_issue.py` দিয়ে ২টি inventory থেকে group:step-3 sequence তৈরি:
- **Category 1** (একই নাম, ২ কাজ): `app.py`, `autonomous_agent.py`, `sentinel_agent.py`, `agent_registry.py`, ৩×`Header.tsx`
- **Category 2** (একই কাজ, ২ নাম): `web_scraper.py`×3, `churn_prophet.py`, `insight_mage.py`, `task_contract.py`
- **16 demo/sample ফাইল** ছাঁটাই (inventory অনুযায়ী)

---

## 🔴 পর্ব ৪: 🆕 Red Team Agent — অনুমোদিত প্রতিপক্ষ প্রোটোকল (Adversarial Hardening)

> **ভবিষ্যৎ প্রোটোকল নম্বর:** OPS-10 (implementation-এ split হবে) · **Agent Slot:** `red-team-1`  
> **মূলনীতি:** *"যে দেয়াল কখনো ধাক্কা খায়নি, তার শক্তি সম্পর্কে কেউ কিছুই প্রমাণ করতে পারে না।"*

### ৪.১ দর্শন (Why)

বর্তমান সিস্টেমে gates আছে — কিন্তু **প্রমাণ নেই** যে সেগুলো আসল attack-এ টিকবে। #2326-এর supersession ও #2157 false-red family দেখিয়েছে: gate-গুলোর আচরণ আমরা জানি না যতক্ষণ না কেউ ইচ্ছাকৃতভাবে সেগুলো ভাঙতে চেষ্টা করে।

**Red Team Agent = permanent authorized adversary** — Netflix Chaos Monkey-এর governance + security version:
- প্রতিটি blocked attack = **live proof** যে gates কাজ করছে (confidence, not hope)
- প্রতিটি breach = একটি P0/P1 hardening issue — **real attacker বা দুর্ঘটনা খুঁজে দেওয়ার আগেই**
- এজেন্ট সন্দেহভাজন নয়, চোর নয় — এটি ফাউন্ডার-অনুমোদিত নিয়মিত নিরাপত্তা-পরীক্ষক, যার প্রতিটি আক্রমণ পূর্ব-ঘোষিত, সীমাবদ্ধ ও audit-trailed

### ৪.২ Agent Charter (কে, কী, কোথায়)

| বিষয় | মান |
|---|---|
| Slot / Lane | `red-team-1` (`AGENT_SLOT_REGISTRY.yaml`-এ নতুন lane; janitor-এর `AGENT_PREFIXES`-এ `red-team-` যোগ) |
| Identity | `supremeai-red-team-1-bot` (আলাদা GitHub App identity — যাতে self-merge gate খারিজ হয় না, তবু detect হয়) |
| State | **State C — Attack** (Dual-State Loop-এর সম্প্রসারণ: State A=Solve, State B=Review, **State C=Attack**) |
| Motto | *"আক্রমণই আমার সেবা"* (Attack is my service) |
| Cadence | প্রতিদিন N-টি attack probe (budget-capped); মাসিক full battery report |

### ৪.৩ Attack Taxonomy (৩ স্তরের আক্রমণ ম্যাপ)

**Level 1 — Governance Attacks (১০ Living Protocol ভাঙার চেষ্টা):**

| # | Attack Vector | Target Protocol/Gate | প্রত্যাশিত Block |
|---|---|---|---|
| 1.1 | atomic_claim ছাড়া issue-তে code push (claim mutex bypass) | Protocol 2 | Branch protection + Scope Gate |
| 1.2 | ৩+ ফাইলের PR (Blast Radius লঙ্ঘন) | Protocol 4 / Scope Gate | `rules.scope_guard` |
| 1.3 | "Touching files" ঘোষণার বাইরের ফাইল touch | Scope Gate | declared-files diff check |
| 1.4 | `has-pr` লেবেল যুক্ত issue-তে duplicate PR | Protocol 5 | `rules.pr_lifecycle_guard` |
| 1.5 | অন্য এজেন্টের slot branch-এ push | Protocol 1 | Lease Gate (bot slot-mismatch) |
| 1.6 | `queue:hold` সরিয়ে isolated merge | Protocol 7 / GSPQ | Branch protection + `rules.group_staging_guard` |
| 1.7 | Test delete/skip করে suite সবুজ করা | Protocol 3 / Test Guard | `rules.test_guard` (নতুন!) |
| 1.8 | Test Evidence ছাড়া PR body | Verification Gate | pr-gate BLOCK |
| 1.9 | নিজের PR নিজে approve/merge | Self-Merge Gate | Branch protection (require review) |
| 1.10 | মিথ্যe "Touching files" ঘোষণা (claim-এ নাম, diff-এ অন্য ফাইল) | Protocol 2+4 | Scope Gate cross-check |

**Level 2 — Pipeline Attacks (CI/CD ভাঙার চেষ্টা):**

| # | Attack Vector | প্রত্যাশিত Block |
|---|---|---|
| 2.1 | Issue/PR body-তে prompt injection (CI bot-কে malicious command চালাতে বাধ্য করা) | Bot-এর tool-allowlist + instruction firewall |
| 2.2 | PR-এ `.github/workflows/` পরিবর্তন smuggle | Workflow-scope block (bot workflow permission নেই) |
| 2.3 | CI থেকে secret exfiltration (`printenv`, curl leak) | Secret masking + egress deny |
| 2.4 | paths-filter bypass — untested path-এ code sneak (Phase-C rot pattern!) | Reverse-gated pr-gate: full suite সব PR-এ |
| 2.5 | Red check-কে সবুজ দেখানো (conclusion spoof / required-check rename) | Immutable check-name registry |
| 2.6 | Dependency confusion (malicious package injection) | pinned-actions check + lockfile diff guard |
| 2.7 | Merge conflict quarantine escape (`hold:merge-conflict` উপেক্ষা) | integration-gate re-verify |

**Level 3 — Application Security Attacks (ব্যাকএন্ড হ্যাক প্রচেষ্টা — staging only):**

| # | Attack Vector | Probe Target |
|---|---|---|
| 3.1 | JWT forgery (`alg=none`, weak secret, role escalation) | Auth middleware |
| 3.2 | SQL/NoSQL injection (route params, filters) | API routes + parameterized query audit |
| 3.3 | Rate limit bypass (IP rotation, header spoof) | Rate limiter |
| 3.4 | SSRF (URL-accepting endpoint-এ internal metadata IP) | Egress allowlist |
| 3.5 | Path traversal (file read/upload endpoints) | Path normalization |
| 3.6 | IDOR (অন্য user-এর resource access) | Ownership middleware |
| 3.7 | Secret exposure (logs/error messages-এ credential leak) | Log scrubbing |
| 3.8 | GitHub App token scope abuse (token-দিয়ে unapproved repo write) | Least-privilege token check |

### ৪.৪ Safety Rails (নিষেধ — যা কখনোই করবে না) 🛡️

1. **Production user data-তে কোনো attack নয়** — শুধু staging/sandbox/dry-run
2. **কোনো destructive merge/push নয়** — attack যদি succeed করতে দেখে, শেষ controlled step-এ থামবে ও রিপোর্ট করবে (proof-of-concept, not destruction)
3. **কোনো real credential theft নয়** — শুধু detection probe (secret-এর existence প্রমাণ, value exfiltrate নয়)
4. **Attack budget** — প্রতি cycle-এ N-টি probe (CI-minutes ও rate-limit রক্ষা)
5. **Kill switch** — `ops-console.yml`-এর `autonomy_kill_switch` দিয়ে instant disable; Tower heartbeat-এ `state=red-team-suspended`
6. **সম্পূর্ণ audit trail** — প্রতিটি attack telemetry Control Tower-এ log হবে (কখন, কোন vector, ফলাফল)
7. **Coordinated disclosure** — Level-3 security finding প্রথমে private রিপোর্ট (public issue-তে exploit detail নয়, যতক্ষণ না fix land)

### ৪.৫ Reporting Protocol (Issue-তে রিপোর্ট)

**নতুন Labels:** `red-team` (সব attack report) · `attack:blocked` (প্রতিরোধিত) · `attack:breached` (ভাঙন ঘটেছে — P0/P1) · `red-team:report` (মাসিক সারসংক্ষেপ)

**Attack Issue Template (বাংলিশ):**

```markdown
### 🎯 Attack Vector
[Level + সংক্ষিপ্ত বর্ণনা]

### 🎯 Target Gate/Protocol
[কোন rule/gate/protocol ভাঙার চেষ্টা]

### 🧪 Reproduction Steps
[ধাপে ধাপে কমান্ড/API call]

### 📊 ফলাফল (Result)
[BLOCKED ✅ / BREACHED 🔴 + evidence: logs, check-run link]

### 🔧 Suggested Hardening
[যদি BREACHED: কীভাবে বন্ধ করা যায়]

### 🛡️ Safety Declaration
[ঘোষণা: কোনো production data/user প্রভাবিত হয়নি — sandbox-only প্রমাণসহ]
```

### ৪.৬ Rule ↔ Probe Pairing এবং Ratchet Effect (Integration Architecture)

**মূল ইন্টিগ্রেশন:** `auditor_rule_engine.py`-এর প্রতিটি rule-এর বিপরীতে একটি **attack probe** — `rules/red_team_battery.py`:

```
auditor_rule_engine.py
├── rules/lease_guard.py          ⇄  probe: unauthorized slot push attempt
├── rules/scope_guard.py          ⇄  probe: undeclared file diff attempt
├── rules/verification_guard.py   ⇄  probe: evidence-less PR attempt
├── rules/pr_lifecycle_guard.py   ⇄  probe: duplicate PR attempt
├── rules/collision_guard.py      ⇄  probe: overlapping PR attempt
├── rules/group_staging_guard.py  ⇄  probe: isolated merge attempt
├── rules/test_guard.py           ⇄  probe: test-deletion attempt
├── rules/janitor_purge_guard.py  ⇄  probe: debris resurrection attempt
└── red_team_battery.py           →  সব probe একসাথে চালায়, JSON report দেয়
```

**Ratchet Effect (একমুখী নিয়ন্ত্রণ):**
1. প্রথমবার attack block হলে → probe-টি **permanent battery-তে যোগ** (regression-test style)
2. Breach হলে → P0/P1 hardening issue → fix land → probe battery-তে যোগ → **ওই ভাঙন চিরতরে বন্ধ**
3. মাসে মাসে battery শুধু বাড়বে, কখনো কমবে না — প্রতিরক্ষা একমুখী ভাবে শক্ত হবে

### ৪.৭ Metrics ও Success Criteria

| মেট্রিক | টার্গেট |
|---|---|
| Attack Block Rate | 100% (কোনো probe BREACHED অবস্থায় থাকবে না — breach পেলেই fix) |
| Gate Coverage | প্রতিটি Living Protocol-এর অন্তত ৩টি active probe |
| Breach MTTR | < ২৪ ঘণ্টা (hardening fix land) |
| Ratchet Count | মাসিক রিপোর্টে cumulative probe সংখ্যা (শুধু বাড়বে) |
| False-Positive Rate | < ৫% (blocked-কিন্তু-আসলে-বৈধ কেস) |

### ৪.৮ Implementation Steps (নতুন Issue Backlog)

| Step | Issue | কাজ |
|---|---|---|
| R1 | `OPS-10 protocol doc` | এই পর্ব ৪-কে full `OPS-10-ADVERSARIAL-RED-TEAM-PROTOCOL.md` হিসেবে split |
| R2 | `rules/red_team_battery.py` | Probe battery module (auditor_rule_engine-এর sibling) |
| R3 | `rules.yml Protocol 11` | সংবিধানে Adversarial Red Team charter + rails + reporting যোগ |
| R4 | `AGENT_SLOT_REGISTRY.yaml` | `red-team-1` slot + janitor `AGENT_PREFIXES`-এ `red-team-` |
| R5 | Labels + issue template | `red-team`, `attack:blocked`, `attack:breached`, `red-team:report` + attack report template |
| R6 | `scheduled-sweeps.yml`-এ hook | মাসিক full battery + report generation (`red-team:report`) |
| R7 | `ops-console.yml`-এ kill-switch arm | Red-team instant suspend lever |
| R8 | প্রথম battery run | Level 1 (governance) দিয়ে শুরু → ফলাফল অনুযায়ী Level 2/3 phase-in |

---

## 📚 পর্ব ৫: বাংলা/বাংলিশ ম্যান্ডেট (Banglish Rollout)

১. **Code Comments:** সব logic change-এ বাধ্যতামূলক — `# বাংলা মন্তব্য: [কেন/কী সিদ্ধান্ত]`
২. **PR Body Template:** `## 🎯 কী কাজ করা হলো` / `## 💡 কেন করা হলো` / `## 🧪 টেস্ট এভিডেন্স`
৩. **Issue Template:** `### 🎯 মূল উদ্দেশ্য` / `### 📂 স্পর্শ করা ফাইলসমূহ` / `### 🧪 যাচাই কমান্ড`
৪. **Agent Interaction:** Admin-এর সাথে সব কথা, report ও plan 100% বাংলা/বাংলিশ
৫. **Enforcement:** `rules.yml` Hard Rule 4 — pr-gate comment-format check

---

## ⚠️ পর্ব ৬: Risk Register

| # | ঝুঁকি | সম্ভাবনা | Mitigation |
|---|---|---|---|
| ১ | ১৪-PR batch landing-এ merge conflict cascade | মাঝারি | Held PR-গুলোর disjoint-file verify সম্পন্ন (#2332/#2335 ইত্যাদি); প্রয়োজনে ২ ব্যাচ |
| ২ | Workflow consolidation-এ hidden caller breakage | মাঝারি | `workflow_call` dependency audit আগে; ১৭ delete এক PR-এ নয় — phase-wise |
| ৩ | `test_guard_gate` wiring-এ false-positive family (#2157 প্যাটার্ন) | মাঝারি | Allowlist সাবধানে + red-team probe দিয়ে validate |
| ৪ | Red team agent নিজেই uncontrolled হয়ে যাওয়া | কম কিন্তু মারাত্মক | Kill-switch + budget cap + audit trail + staging-only rails |
| ৫ | Red team-এর false accusation (বৈধ কাজকে breach রিপোর্ট) | মাঝারি | Founder adjudication step; FP-rate metric |
| ৬ | Auth token hourly expiry | নিশ্চিত | Token-refresh loop (setsid) — প্রতিষ্ঠিত runbook |
| ৭ | Redundant double-testing pipeline regression-এ ফিরে আসা | কম | Zero-Redundancy matrix ডকুমেন্টেড + scheduled-sweeps drift audit |

---

## ✅ পর্ব ৭: Success Criteria (Validation Rubric)

1. **Step-2 সম্পূর্ণ:** #2276, #2277, #2328 close + ~−5,400 লাইন zero-loss verified
2. **Queue drained:** ১৪ held PR → ০ (সব batch-এ landed)
3. **Zero Debris:** Janitor চালানোর পর কোনো stale branch/label নেই
4. **5 Clean Files:** `.github/workflows/` = ঠিক ৫টি ফাইল
5. **3 Unwired Gates → Wired:** test_guard, post_merge_watch, self_merge — সব live
6. **Red Team Live:** প্রথম battery run-এ Level-1 probe ≥ ১০টি, ফলাফল ইস্যু-তে documented
7. **Bangla Mandate:** সব নতুন code comment `# বাংলা মন্তব্য:` ফরম্যাটে
8. **Ratchet চালু:** প্রতিটি blocked attack permanently probe battery-তে

---

## 🚀 পর্ব ৮: এক্সিকিউশন অর্ডার (Dependency Graph)

```
Phase A (এখন):
  A1 (#2277 surgical redo) ──► A2 (#2328 audit) ──► A3 (hold-release + train landing)
                                                          │
                                           A4 (janitor) ──┤
Phase B (landing-এর পরে):                                 ▼
  B1 (auditor_rule_engine) ──► B2 (orchestrator) ──► B4 (22→5 consolidation) ──► B5 (step-3 group)
  B3 (self-healing) ───────────┘ (B1-এর সাথে parallel)
                                    │
Phase C (B1-এর পরেই শুরু হতে পারে): ▼
  R1-R5 (charter docs + battery + slots + labels) ──► R6-R7 (sweeps + kill-switch hooks)
                                                          │
                                              R8 (প্রথম full battery run) ──► মাসিক ratchet cycle
```

**ক্রম-নিয়ম:**
- Phase B4 (workflow consolidation) শুরু হবে **শুধু** Phase A3 landing-এর পরে
- Phase C (red team) B1 (rule engine)-এর পরে শুরু হবে — probe-গুলো rule engine-এর উপর দাঁড়ায়
- প্রতিটি Phase-এর শেষে 4-Pillar audit + janitor (মানে Phase নিজেই GSPQ অনুসরণ করবে)

---

## 📎 পরিশিষ্ট: Implementation Issue Backlog (তৈরি হবে `create_group_issue.py` দিয়ে)

| Phase | Issue শিরোনাম | Group/Seq | Priority |
|---|---|---|---|
| A1 | `chore(cleanup): [Step-2.4-redo] surgical retire ephemeral_synthesizer` | group:step-2 / seq:4b | P1 |
| A2 | *(existing #2328)* Step-2.5 harvest audit | group:step-2 / seq:5 | P1 |
| B1 | `feat(ci): build auditor_rule_engine.py — 10 pluggable rule modules` | group:engine-1 / seq:1 | P0 |
| B2 | `feat(ci): build group_batch_orchestrator.py — group lifecycle state machine` | group:engine-1 / seq:2 | P1 |
| B3 | `feat(agents): self-healing has-pr writeback + seq unblock in acquire_role_slot` | group:engine-1 / seq:3 | P1 |
| B4 | `refactor(ci): 22→5 canonical workflow consolidation (phased)` | group:engine-2 / seq:1-4 | P0 |
| B5 | `chore(cleanup): [Step-3] duplicate/confusing-name file consolidation` | group:step-3 / seq:1..N | P1 |
| C/R1 | `docs: OPS-10 Adversarial Red Team Protocol` | group:red-team / seq:0 | P1 |
| C/R2 | `feat(ci): rules/red_team_battery.py — probe battery` | group:red-team / seq:1 | P1 |
| C/R3-R7 | সংবিধান Protocol 11 + slot + labels + sweeps + kill-switch | group:red-team / seq:2-6 | P2 |
| C/R8 | `chore(red-team): first full battery run + report` | group:red-team / seq:7 | P2 |

---

*এই ডকুমেন্ট Founder-অনুমোদিত মাস্টার রোডম্যাপ। পরিবর্তন প্রস্তাব ইস্যুতে ট্যাগ করুন `ARCH-10`। সব এজেন্ট এই প্ল্যানকে `AGENTS.md` Living Protocols-এর সম্প্রসারণ হিসেবে মানবে।*
