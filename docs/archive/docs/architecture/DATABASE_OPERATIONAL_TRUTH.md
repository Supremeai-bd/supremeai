# Database as Operational Truth + Documents as Context
## (Policy DB & Capability Lifecycle Framework — Issue #2377, seq:2, group:arch-foundation)

> **ডকুমেন্ট আইডি:** ARCH-OPTRUTH-01
> **তারিখ:** ২০২৬-০৯-২৮ · **স্ট্যাটাস:** Active Standard (bilingual — বাংলা প্রধান)
> **প্রযোজ্য ইস্যু:** [#2377](https://github.com/SaifulHaqueNiloy/supremeai/issues/2377)
> **পূর্বসূরি:** [#2399 Ecosystem Graph Registry](./ECOSYSTEM_GRAPH_REGISTRY.yaml) (seq:1 — সম্পন্ন, PR #2400)
> **উত্তরসূরি:** #2378 Flexible Group Branching (seq:3)

---

## 🎯 ১. মূল দর্শন — তিন স্তরের সত্য (Three Layers of Truth)

| স্তর | ভূমিকা | প্রশ্ন যার উত্তর দেয় | উদাহরণ |
| :--- | :--- | :--- | :--- |
| **DATABASE (Supabase/Postgres)** | Live Operational Truth | *এখন কী সত্য? কী allowed? কার অবস্থা কী?* | `agent_leases`, `capabilities`, `operational_tasks` |
| **GIT (GitHub)** | Architectural Blueprint & Code Contract | *কেন এমন? ডিজাইন, সংবিধান, কোড* | `AGENTS.md`, `rules.yml`, এই ডকুমেন্ট |
| **VECTOR DB (ChromaDB/RAG)** | Deep Knowledge & Historical Context | *অতীতে এমন কী হয়েছিল? কীভাবে সমাধান হয়েছিল?* | ৩১০টি plan/archive ডকুমেন্ট |

**মূল নীতি:** *"Agent freedom inside, strong system boundary outside"* — এজেন্টকে
৫০টি রুলস ফাইল মুখস্থ করানোর বদলে সিস্টেম নিজে ডাটাবেস-স্টেট থেকে বাউন্ডারি এনফোর্স করে।

---

## 📊 ২. ডকুমেন্ট অডিট ম্যাট্রিক্স (৪৫১+ ফাইলের পূর্ণাঙ্গ বিভাজন)

| ক্যাটাগরি | গন্তব্য | উদাহরণ | সংখ্যা | কারণ |
| :--- | :--- | :--- | :--- | :--- |
| **A** | Git (থাকবে) | `AGENTS.md`, `rules.yml`, `docs/master_docs/`, `docs/architecture/` | ~৪৫ | সংবিধান ও ব্লুপ্রিন্ট কোডের সাথে version-controlled থাকবে |
| **B** | Supabase (DB-হবে) | `MODULE_STATUS_REGISTRY.md`, `AGENT_SLOT_REGISTRY.yaml`, `ACTIVE_ISSUES_AND_PRIORITY_ROADMAP.md`, `ACTIVE_AUDIT_QUEUE.md`, `TOKEN_ROTATION_VERIFICATION.md` | ~৩০ | প্রতিনিয়ত পরিবর্তনশীল; DB-তে ০% PR-conflict |
| **C** | RAG (ইনজেস্ট হবে) | `docs/plans/` (161), `docs/archive/` (98), `docs/plan-network/` (52) | ~৩১০ | অতীত প্ল্যান — semantic search-এ থাকবে, context-এ নয় |
| **D** | Git-ignore (on-demand) | `docs/generated/*.json` (667KB + 533KB + ...) | ~১০ | CI/runtime-এ regenerate হবে; ভারী ফাইল গিটে নয় |

**⚠️ Category D সতর্কতা:** বর্তমানে tracked `docs/generated/*.json` ফাইলগুলো
`ci-advanced-checks.yml`-এর drift-gate (L123/L136) সরাসরি পড়ে — তাই untracking
**এই কাজে করা হয়নি** এবং forward-policy `.gitignore` entry-ও **Follow-up A-এ
deferred** (Scope Gate-এর declared-path parser extension-less dotfile
`.gitignore`-কে declare করতে পারে না — path_re limitation; এন্ট্রি যোগ হবে
rules.yml allowlist + dotfile support সহ আলাদা governance PR-এ)।
Untracking করা হবে drift-gate regen-on-demand-এ রূপান্তরের পরে।

---

## 🗄️ ৩. কোর টেবিল স্পেসিফিকেশন (Alembic: `op_truth_0001`)

Canonical migration: `backend/alembic_migrations/versions/2026_09_28_194500_database_operational_truth.py`
(chains from `merge_learn_0001`, single-head guard বজায়)। Defense-in-depth:
`scripts/operations/operational_truth_db.py`-এর `ensure_schema()` একই DDL
idempotent ভাবে চালাতে পারে — alembic না চলা পরিবেশেও bridge self-heal করবে।

| টেবিল | PK | মূল কলাম | উৎস (sync) | লাইভ লেখক (bridge) |
| :--- | :--- | :--- | :--- | :--- |
| `system_modules` | id | name(uniq), kind(domain/module/node/db-model/resource), layer, domain_id, status, owning_paths(JSON) | `sync_operational_truth.py` ← ECOSYSTEM_GRAPH_REGISTRY.yaml | `tower_db_bridge.py` ← tower `resource.status` |
| `capabilities` | capability_id (CAP-XX-NN) | status(6-state), tier(1-4), evidence, canonical_path, preserve, verification_proof | ← CAPABILITY_LEDGER.md | auditor প্রক্রিয়া (verification_proof পূরণ) |
| `agent_leases` | slot_id | agent_name, role, issue_number, branch_name, heartbeat_at, expires_at, state | ← AGENT_SLOT_REGISTRY.yaml (pool templates) | ← tower `agent_status`/`agent_heartbeat` mirror |
| `operational_tasks` | issue_number | group_name, sequence, ripple_effect_score, priority_tier, status, assigned_slot | ← ACTIVE_ISSUES_AND_PRIORITY_ROADMAP.md | issue lifecycle প্রক্রিয়া |
| `secret_rotations` | id | secret_name, scope, rotated_at, verified_at, status | ← TOKEN_ROTATION_VERIFICATION.md | rotation রানবুক |
| `audit_queue` | finding_id (GAP-NNN) | category, target_path, status, added_date, resolved_at | ← ACTIVE_AUDIT_QUEUE.md | audit প্রক্রিয়া |

### Capability Lifecycle (৬-স্টেট — CAPABILITY_LEDGER taxonomy)

```text
PROPOSED → PLANNED → IN_PROGRESS → PARTIAL → VERIFIED → DEPRECATED
```

- `tier` derivation (evidence-hierarchy থেকে, sync script-এ ডকুমেন্টেড):
  **4** = CODE+TEST+RUNTIME · **3** = CODE+TEST · **2** = CODE/CI · **1** = DOCUMENT/PLAN_ONLY
- সিস্টেম পার্স করতে পারবে: *"planned ছিল, implementation হয়নি"*, *"implemented,
  কিন্তু verification হয়নি"* — Zero Loss Invariant।

---

## 🔄 ৪. সিঙ্ক ও ব্রিজ প্রোটোকল

### 4.1 `scripts/operations/sync_operational_truth.py` (Registry → DB)

- **Idempotent upsert** (`ON CONFLICT DO UPDATE`) — যতবার চালান, truth converge হয়
- **Dual target:** `--db-url` (canonical Supabase Postgres) বা `--sqlite` (local mirror/verification)
- **Dry-run default:** DB target না দিলে parse-report only (CI-safe, credential-free)
- নতুন doc → DB মাইগ্রেশন ক্রমে ধীরে ধীরে (no dumping ground): প্রথমে sync, তারপর
  source doc-এ "DB-backed" মার্কার, সবশেষে owner-decision-এ doc অবসর

### 4.2 `scripts/operations/tower_db_bridge.py` (MCP Tower ↔ DB)

```text
Tower (Redis fast-path)                    Operational Truth DB (persistent)
─────────────────────────                  ──────────────────────────────────
agent_status   ──sync pull──►  agent_leases (slot, heartbeat_at, state)
resource.list + resource.status ──sync pull──►  system_modules (kind=resource)
agent_heartbeat ──mirror──►  agent_leases (tower ping + DB truth একসাথে)
```

- Tower URL resolution: `MCP_TOWER_URL` env → `mcp.json` (fail-closed —
  `scripts/agents/mcp_tower_client.py`-র চুক্তি অপরিবর্তিত)
- `--dry-run`: tower থেকে পড়ে planned upsert দেখায়, DB ছোঁয় না
- Follow-up (tower-side): TS `agent_heartbeat.ts`-এ Supabase adapter mirror —
  tower নিজে পুশ করবে; ততক্ষণ Python bridge pull/mirror করে

### 4.3 `scripts/operations/ingest_plans_to_rag.py` (Category C → RAG)

- Engine: `backend/memory/rag_pipeline.py` — MCP tool `ingest_document_rag`-এর
  একই pipeline (chunk → embed → ChromaDB index)
- Collection: `supremeai_plans_rag` (KG collection থেকে আলাদা)
- **Resumable:** content-hash manifest `data/rag_ingest_manifest.json` —
  unchanged ফাইল পুনরায় ইনজেস্ট হয় না; 2MB+ ফাইল skip (dumping-ground guard)
- doc_id: `docrag::<category>::<sha12>` — content-addressed, stable

---

## 🛡️ ৫. এনফোর্সমেন্ট পথ (Policy DB → MCP Enforcement)

```text
agent_leases + capabilities (কে কী করতে পারে)
        ↓ (tower_db_bridge sync)
MCP Tower policy layer (mcp-access.ts) + core/mcp_policy.py (RiskEngine R0-R6)
        ↓
Tool call evaluate → ALLOW / REQUIRE_APPROVAL / DENY
```

বর্তমান PR স্তর ১ স্থাপন করে (truth tables + bridge)। স্তর ২ — `system_policies`
টেবিল থেকে tower-এর role→permission ম্যাপিং ডাইনামিক লোড — follow-up
(issue #2377-এর "Policy DB" পূর্ণ বিস্তার; এখন বিদ্যমান `AGENT_SLOT_REGISTRY.yaml`
mapping-ই tower ব্যবহার করে)।

---

## ⚠️ ৬. No-Dumping-Ground নিয়মাবলি

1. প্রতিটি টেবিলের **সংজ্ঞায়িত লাইভ লেখক** থাকবে (sync / bridge / auditor) —
   "যে কেউ যা খুশি লিখবে" নয়
2. ডকুমেন্টের গল্প/ব্যাখ্যা (Why) কখনো DB-তে যাবে না — শুধু state (What is true now)
3. ২MB+ কনটেন্ট DB/RAG-উভয় স্তরেই আটকে দেওয়া
4. নতুন "status ফাইল" তৈরি **নিষিদ্ধ** — নতুন live-state মানে নতুন টেবিল/কলাম,
   নতুন markdown নয়
5. `verification_proof`, `ripple_effect_score`-এর মতো quality ফিল্ড শুধু
   auditor-প্রক্রিয়া পূরণ করবে — sync কখনো নয়

---

## 📋 ৭. Deliverables চেকলিস্ট (Issue #2377)

- [x] **DB Schema Migration:** `op_truth_0001` — ৬টি টেবিল + ১২ ইনডেক্স (Alembic canonical)
- [x] **Sync Script:** `sync_operational_truth.py` — ৬ source parser, dual-target, dry-run
- [x] **MCP Tower Adapter Bridge:** `tower_db_bridge.py` — agent_status/resource.status
      pull + agent_heartbeat mirror
- [x] **Vector Ingestion:** `ingest_plans_to_rag.py` — ৩ ক্যাটাগরি, resumable manifest
- [x] **Duplicate status file audit:** §8-এ Category B মাইগ্রেশন ক্রম + retirement
      owner-decision টেবিল (কোনো ফাইল এই কাজে ডিলিট হয়নি — Zero Loss Invariant)
- [ ] **Follow-up A:** `.gitignore` Category D forward-policy entry (Scope Gate
      dotfile-declare limitation সমাধানের পর) → drift-gate regen-on-demand →
      তারপর `git rm --cached docs/generated/*.json`
- [ ] **Follow-up B:** TS tower-side Supabase mirror (`agent_heartbeat.ts`)
- [ ] **Follow-up C:** `system_policies` টেবিল + tower dynamic permission load (Policy DB স্তর ২)

---

## 📁 ৮. Duplicate Status File Audit (Category B মাইগ্রেশন ক্রম)

| ফাইল | বর্তমান ভূমিকা | DB টেবিল | মাইগ্রেশন ধাপ |
| :--- | :--- | :--- | :--- |
| `docs/operations/ACTIVE_ISSUES_AND_PRIORITY_ROADMAP.md` | রোডম্যাপ truth | `operational_tasks` | sync ✅ → owner marker → retire |
| `docs/audits/ACTIVE_AUDIT_QUEUE.md` | অডিট findings | `audit_queue` | sync ✅ → owner marker → retire |
| `docs/security/TOKEN_ROTATION_VERIFICATION.md` | রোটেশন রানবুক | `secret_rotations` | sync ✅ (runbook অংশ Git-এ থাকবে) |
| `docs/master_docs/AGENT_SLOT_REGISTRY.yaml` | slot/pool সংজ্ঞা | `agent_leases` (templates) | sync ✅ — সংজ্ঞা (charter) Git-এ থাকবে, live lease DB-তে |
| `docs/operations/MODULE_STATUS_REGISTRY.md` | owner decision sheet | `system_modules` (decision অংশ) | sync (graph registry হয়ে) ✅ — decision sheet হিসেবে Git-এ থাকবে |
| `docs/architecture/CAPABILITY_LEDGER.md` | capability inventory | `capabilities` | sync ✅ — reasoning/refactor-matrix অংশ Git-এ থাকবে |
| `STATUS.md` / `CHECKPOINT.md` | সামগ্রিক অবস্থা | (view-layer; টেবিল থেকে generate হবে) | deferred — generator follow-up |

**নিয়ম:** কোনো ফাইল এই PR-এ ডিলিট হয়নি — প্রতিটি retirement owner-decision
(Zero Loss Invariant + MODULE_STATUS_REGISTRY decision-sheet প্রথার সাথে সঙ্গতিপূর্ণ)।

---

## 🔗 ৯. সংযোগ ও রেফারেন্স

- Ecosystem Graph: [`ECOSYSTEM_GRAPH_REGISTRY.yaml`](./ECOSYSTEM_GRAPH_REGISTRY.yaml) (#2399)
- MCP Tower client: `scripts/agents/mcp_tower_client.py` (bootstrap + graph CLI)
- RAG engine: `backend/memory/rag_pipeline.py` · MCP tool: `ingest_document_rag`
- Tower tools: `infrastructure/mcp-control-plane/src/tools/agent.tools.ts`
  (`agent_heartbeat`, `agent_status`), `system.tools.ts` (`resource.list`, `resource.status`)
- Audit chain (উদাহরণ প্রথা): `backend/core/mcp_audit.py` + `mcp_audit_events` (#928)
